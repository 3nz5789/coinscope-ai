"""
Palace Store — Native MemPalace Drawer Operations
===================================================
All CoinScopeAI memory stores share a **single** ChromaDB collection
(``mempalace_drawers``), exactly as MemPalace's own MCP server and
search tools expect.  Every drawer carries ``wing``, ``room``, and
optionally ``hall`` metadata so the palace graph, Layer 1-3 stack,
and semantic search all work natively.

Design:
  - One PersistentClient per process (cached).
  - One collection: ``mempalace_drawers``.
  - Each store subclass sets ``_wing`` and ``_default_room``.
  - Drawers are filed with deterministic IDs (content-hash) for
    idempotency — re-filing the same content is a no-op.
"""

import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import chromadb

from .config import MemoryConfig, COLLECTION_NAME

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


class PalaceStore:
    """
    Base class for all CoinScopeAI memory stores.

    Subclasses set:
      - ``_wing``          e.g. "wing_trading"
      - ``_default_room``  e.g. "signals"
      - ``_default_hall``  e.g. "hall_events"

    All operations go through the single ``mempalace_drawers`` collection.
    """

    _wing: str = "wing_system"
    _default_room: str = "general"
    _default_hall: str = "hall_events"

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self._col = _get_collection(self.config.palace_path)

    # ------------------------------------------------------------------
    # Write — file a drawer
    # ------------------------------------------------------------------

    def file_drawer(
        self,
        content: str,
        room: str = "",
        hall: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        added_by: str = "engine",
    ) -> str:
        """
        File a drawer into the palace.

        Parameters
        ----------
        content : str      The verbatim text to store.
        room : str         Room within this store's wing (default: _default_room).
        hall : str         Hall category (default: _default_hall).
        metadata : dict    Additional metadata (flattened, scalar values only).
        added_by : str     Who filed this drawer.

        Returns
        -------
        str  The drawer ID.
        """
        room = room or self._default_room
        hall = hall or self._default_hall
        now = datetime.now(timezone.utc)

        # Deterministic ID: wing + room + content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
        drawer_id = f"drawer_{self._wing}_{room}_{content_hash}"

        # Build metadata
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

        self._col.upsert(
            ids=[drawer_id],
            documents=[content],
            metadatas=[meta],
        )

        if self.config.verbose:
            logger.info("[%s/%s] filed %s (%d chars)", self._wing, room, drawer_id, len(content))

        return drawer_id

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
