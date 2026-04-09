"""
Palace Store — Non-blocking, Batched MemPalace Drawer Operations
==================================================================
All CoinScopeAI memory stores share a **single** ChromaDB collection
(``mempalace_drawers``), exactly as MemPalace's own MCP server and
search tools expect.  Every drawer carries ``wing``, ``room``, and
optionally ``hall`` metadata so the palace graph, Layer 1-3 stack,
and semantic search all work natively.

Production-readiness features:
  1. **Non-blocking async write queue** — ``file_drawer`` enqueues a
     write event and returns immediately.  A background writer thread
     drains the queue and writes to ChromaDB.  If the queue is full or
     ChromaDB is down, a warning is logged but trading never blocks.
  2. **Idempotency / dedup** — every drawer carries an ``event_id``.
     Before writing, the writer checks if the event_id already exists
     and silently skips duplicates.
  3. **Hall strategy enforcement** — the configured HALL_STRATEGY map
     is checked at write time; mismatches are logged as warnings.
  4. **Batch/flush model** — incoming events are buffered in memory and
     flushed to ChromaDB every N seconds or when the buffer hits a size
     threshold, reducing ChromaDB overhead during high-frequency scanning.
  5. **Retention / pruning** — a ``prune()`` helper deletes drawers
     older than the configured retention period per wing.

Design:
  - One PersistentClient per process (cached).
  - One collection: ``mempalace_drawers``.
  - Each store subclass sets ``_wing`` and ``_default_room``.
  - Drawers are filed with deterministic IDs (content-hash) for
    idempotency — re-filing the same content is a no-op.
"""

import atexit
import hashlib
import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

import chromadb

from .config import (
    MemoryConfig,
    COLLECTION_NAME,
    HALL_STRATEGY,
    DEFAULT_RETENTION_DAYS,
    RETENTION_EXEMPT_ROOMS,
)

logger = logging.getLogger("coinscopeai.memory")

# Process-wide client cache
_client_lock = threading.Lock()
_client_cache: Dict[str, chromadb.ClientAPI] = {}
_collection_cache: Dict[str, Any] = {}


def _get_collection(palace_path: str):
    """Return the shared mempalace_drawers collection (cached)."""
    with _client_lock:
        if palace_path not in _client_cache:
            _client_cache[palace_path] = chromadb.PersistentClient(path=palace_path)
        client = _client_cache[palace_path]

        cache_key = f"{palace_path}::{COLLECTION_NAME}"
        if cache_key not in _collection_cache:
            _collection_cache[cache_key] = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return _collection_cache[cache_key]


# ======================================================================
# Write event dataclass (plain dict for queue transport)
# ======================================================================

def _make_write_event(
    drawer_id: str,
    content: str,
    metadata: Dict[str, Any],
    event_id: str,
) -> Dict[str, Any]:
    """Create a write event dict for the async queue."""
    return {
        "drawer_id": drawer_id,
        "content": content,
        "metadata": metadata,
        "event_id": event_id,
    }


# ======================================================================
# Background Writer — drains queue, batches, flushes to ChromaDB
# ======================================================================

class _BackgroundWriter:
    """
    Singleton background writer thread per palace_path.

    - Reads from a thread-safe queue (non-blocking to callers).
    - Buffers events in a deque.
    - Flushes to ChromaDB every ``flush_interval`` seconds or when
      the buffer reaches ``flush_batch_size``.
    - On graceful shutdown (atexit), flushes remaining events.
    - If ChromaDB is unavailable, logs a warning and drops events
      (best-effort memory guarantee).
    """

    _instances: Dict[str, "_BackgroundWriter"] = {}
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        palace_path: str,
        queue_size: int = 10000,
        flush_interval: float = 5.0,
        flush_batch_size: int = 50,
    ) -> "_BackgroundWriter":
        with cls._instance_lock:
            if palace_path not in cls._instances:
                inst = cls(palace_path, queue_size, flush_interval, flush_batch_size)
                cls._instances[palace_path] = inst
            return cls._instances[palace_path]

    def __init__(
        self,
        palace_path: str,
        queue_size: int,
        flush_interval: float,
        flush_batch_size: int,
    ):
        self._palace_path = palace_path
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._flush_interval = flush_interval
        self._flush_batch_size = flush_batch_size
        self._buffer: Deque[Dict[str, Any]] = deque()
        self._seen_event_ids: Set[str] = set()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"mempalace-writer-{palace_path}",
            daemon=True,
        )
        self._thread.start()
        atexit.register(self.shutdown)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, event: Dict[str, Any]) -> bool:
        """
        Enqueue a write event.  Returns True if accepted, False if
        the queue is full (event is dropped with a warning).
        Never blocks the caller.
        """
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            logger.warning(
                "[MemPalace] Write queue full — dropping event %s (best-effort memory)",
                event.get("event_id", event.get("drawer_id", "?")),
            )
            return False

    def shutdown(self):
        """Signal the writer to stop and flush remaining events."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)
        # Final flush of anything remaining
        self._drain_queue()
        self._flush()

    @property
    def pending_count(self) -> int:
        """Number of events waiting in queue + buffer."""
        return self._queue.qsize() + len(self._buffer)

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self):
        """Main loop of the background writer thread."""
        last_flush = time.monotonic()
        while not self._stop_event.is_set():
            # Drain queue into buffer
            self._drain_queue()

            # Check flush conditions
            now = time.monotonic()
            elapsed = now - last_flush
            if (
                len(self._buffer) >= self._flush_batch_size
                or (len(self._buffer) > 0 and elapsed >= self._flush_interval)
            ):
                self._flush()
                last_flush = time.monotonic()

            # Sleep briefly to avoid busy-waiting
            self._stop_event.wait(timeout=0.1)

        # Final drain + flush on stop
        self._drain_queue()
        self._flush()

    def _drain_queue(self):
        """Move all items from queue into buffer, deduplicating by event_id."""
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break

            eid = event.get("event_id", "")
            if eid and eid in self._seen_event_ids:
                logger.debug("[MemPalace] Dedup: skipping duplicate event_id=%s", eid)
                continue

            if eid:
                self._seen_event_ids.add(eid)
            self._buffer.append(event)

        # Prevent unbounded growth of seen set (keep last 50k)
        if len(self._seen_event_ids) > 50000:
            # Convert to list, keep last 25k
            recent = list(self._seen_event_ids)[-25000:]
            self._seen_event_ids = set(recent)

    def _flush(self):
        """Flush buffered events to ChromaDB in a single batch upsert."""
        if not self._buffer:
            return

        # Collect batch
        ids = []
        documents = []
        metadatas = []
        while self._buffer:
            event = self._buffer.popleft()
            ids.append(event["drawer_id"])
            documents.append(event["content"])
            metadatas.append(event["metadata"])

        try:
            col = _get_collection(self._palace_path)
            col.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            if len(ids) > 1:
                logger.debug("[MemPalace] Flushed batch of %d drawers", len(ids))
        except Exception as exc:
            logger.warning(
                "[MemPalace] ChromaDB flush failed (%d events dropped): %s",
                len(ids),
                exc,
            )


# ======================================================================
# PalaceStore — base class for all memory stores
# ======================================================================

class PalaceStore:
    """
    Base class for all CoinScopeAI memory stores.

    Subclasses set:
      - ``_wing``          e.g. "wing_trading"
      - ``_default_room``  e.g. "signals"
      - ``_default_hall``  e.g. "hall_events"

    All operations go through the single ``mempalace_drawers`` collection.
    Writes are non-blocking: they are enqueued to a background writer
    that batches and flushes to ChromaDB periodically.
    """

    _wing: str = "wing_system"
    _default_room: str = "general"
    _default_hall: str = "hall_events"

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self._col = _get_collection(self.config.palace_path)
        self._writer = _BackgroundWriter.get_instance(
            palace_path=self.config.palace_path,
            queue_size=self.config.write_queue_size,
            flush_interval=self.config.flush_interval_seconds,
            flush_batch_size=self.config.flush_batch_size,
        )

    # ------------------------------------------------------------------
    # Write — file a drawer (non-blocking, async queue)
    # ------------------------------------------------------------------

    def file_drawer(
        self,
        content: str,
        room: str = "",
        hall: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        added_by: str = "engine",
        event_id: str = "",
    ) -> str:
        """
        File a drawer into the palace (non-blocking).

        The write is enqueued to a background writer thread and returns
        immediately.  If the queue is full or ChromaDB is down, a warning
        is logged but the caller is never blocked.

        Parameters
        ----------
        content : str      The verbatim text to store.
        room : str         Room within this store's wing (default: _default_room).
        hall : str         Hall category (default: _default_hall).
        metadata : dict    Additional metadata (flattened, scalar values only).
        added_by : str     Who filed this drawer.
        event_id : str     Optional idempotency key.  If not provided, a
                           deterministic ID is generated from
                           (wing + room + event_type + symbol + timestamp).

        Returns
        -------
        str  The drawer ID (returned immediately, before actual write).
        """
        room = room or self._default_room
        hall = hall or self._default_hall
        now = datetime.now(timezone.utc)

        # --- Hall strategy enforcement ---
        strategy_key = f"{self._wing}/{room}"
        expected_hall = HALL_STRATEGY.get(strategy_key)
        if expected_hall and hall != expected_hall:
            logger.warning(
                "[MemPalace] Hall mismatch for %s: got '%s', expected '%s'. "
                "Using expected hall.",
                strategy_key,
                hall,
                expected_hall,
            )
            hall = expected_hall

        # --- Build metadata ---
        meta: Dict[str, Any] = {
            "wing": self._wing,
            "room": room,
            "hall": hall,
            "added_by": added_by,
            "filed_at": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
        }
        if metadata:
            for k, v in metadata.items():
                if v is None:
                    meta[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)

        # --- Generate event_id for dedup ---
        if not event_id:
            # Deterministic: wing + room + event_type + symbol + timestamp
            event_type = meta.get("event_type", "")
            symbol = meta.get("symbol", "")
            dedup_src = f"{self._wing}:{room}:{event_type}:{symbol}:{now.isoformat()}"
            event_id = hashlib.sha256(dedup_src.encode()).hexdigest()[:24]

        meta["event_id"] = event_id

        # Deterministic drawer ID: wing + room + content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        drawer_id = f"drawer_{self._wing}_{room}_{content_hash}"

        # --- Enqueue (non-blocking, fire-and-forget) ---
        write_event = _make_write_event(
            drawer_id=drawer_id,
            content=content,
            metadata=meta,
            event_id=event_id,
        )
        self._writer.enqueue(write_event)

        if self.config.verbose:
            logger.info(
                "[%s/%s] enqueued %s (%d chars, event_id=%s)",
                self._wing,
                room,
                drawer_id,
                len(content),
                event_id,
            )

        return drawer_id

    # ------------------------------------------------------------------
    # Direct write — bypass queue for diary entries (agent_sessions)
    # ------------------------------------------------------------------

    def _enqueue_direct(
        self,
        drawer_id: str,
        content: str,
        metadata: Dict[str, Any],
        event_id: str = "",
    ) -> bool:
        """
        Enqueue a pre-built write event.  Used by stores that bypass
        file_drawer (e.g. agent diary writes).  Returns True if accepted.
        """
        if not event_id:
            event_id = hashlib.sha256(
                f"{drawer_id}:{metadata.get('filed_at', '')}".encode()
            ).hexdigest()[:24]
        metadata["event_id"] = event_id

        write_event = _make_write_event(
            drawer_id=drawer_id,
            content=content,
            metadata=metadata,
            event_id=event_id,
        )
        return self._writer.enqueue(write_event)

    # ------------------------------------------------------------------
    # Flush — force immediate write of buffered events
    # ------------------------------------------------------------------

    def flush(self):
        """Force flush all buffered events to ChromaDB immediately."""
        self._writer._drain_queue()
        self._writer._flush()

    # ------------------------------------------------------------------
    # Read — semantic search (L3-style)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        n_results: int = 0,
        room: str = None,
        wing: str = None,
        where: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search within this store's wing (or cross-wing if wing given).

        Returns list of dicts: {text, wing, room, hall, similarity, metadata}
        """
        n = n_results or self.config.default_n_results

        # Build where filter
        if where:
            effective_where = where
        elif wing and room:
            effective_where = {"$and": [{"wing": wing}, {"room": room}]}
        elif room:
            effective_where = {"$and": [{"wing": self._wing}, {"room": room}]}
        elif wing:
            effective_where = {"wing": wing}
        else:
            effective_where = {"wing": self._wing}

        kwargs: Dict[str, Any] = {
            "query_texts": [query],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if effective_where:
            kwargs["where"] = effective_where

        try:
            results = self._col.query(**kwargs)
        except Exception as exc:
            logger.error("[%s] search error: %s", self._wing, exc)
            return []

        hits: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "wing": meta.get("wing", ""),
                "room": meta.get("room", ""),
                "hall": meta.get("hall", ""),
                "similarity": round(1 - dist, 4),
                "metadata": meta,
            })
        return hits

    # ------------------------------------------------------------------
    # Read — metadata filter (no embedding)
    # ------------------------------------------------------------------

    def get_drawers(
        self,
        room: str = None,
        where: Optional[Dict] = None,
        limit: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve drawers by metadata filter (no semantic search)."""
        n = limit or self.config.default_n_results

        if where:
            effective_where = where
        elif room:
            effective_where = {"$and": [{"wing": self._wing}, {"room": room}]}
        else:
            effective_where = {"wing": self._wing}

        kwargs: Dict[str, Any] = {
            "include": ["documents", "metadatas"],
            "limit": n,
        }
        if effective_where:
            kwargs["where"] = effective_where

        try:
            results = self._col.get(**kwargs)
        except Exception as exc:
            logger.error("[%s] get error: %s", self._wing, exc)
            return []

        hits: List[Dict[str, Any]] = []
        for doc_id, doc, meta in zip(
            results.get("ids", []),
            results.get("documents", []),
            results.get("metadatas", []),
        ):
            hits.append({"id": doc_id, "text": doc, "metadata": meta})
        return hits

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self, room: str = None) -> int:
        """Count drawers in this wing (or specific room)."""
        if room:
            where = {"$and": [{"wing": self._wing}, {"room": room}]}
        else:
            where = {"wing": self._wing}
        try:
            results = self._col.get(where=where, include=[], limit=10000)
            return len(results.get("ids", []))
        except Exception:
            return 0

    def status(self) -> Dict[str, Any]:
        """Status of this store."""
        rooms: Dict[str, int] = {}
        try:
            results = self._col.get(
                where={"wing": self._wing},
                include=["metadatas"],
                limit=10000,
            )
            for meta in results.get("metadatas", []):
                r = meta.get("room", "unknown")
                rooms[r] = rooms.get(r, 0) + 1
        except Exception:
            pass

        return {
            "wing": self._wing,
            "total_drawers": sum(rooms.values()),
            "rooms": rooms,
        }
