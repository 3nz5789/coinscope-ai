"""
Memory API Endpoints
=====================
FastAPI router that exposes the MemPalace as REST endpoints.
Mount on the existing CoinScopeAI engine API or run standalone.

Usage (mount)::

    from memory.api import router as memory_router
    app.include_router(memory_router, prefix="/memory", tags=["memory"])

Usage (standalone)::

    uvicorn memory.api:app --port 8002
"""

import time
from typing import List, Optional

from fastapi import APIRouter, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .manager import MemoryManager

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str
    n_results: int = 10
    wing: Optional[str] = None
    room: Optional[str] = None


class SearchHit(BaseModel):
    wing: str
    room: str
    text: str
    similarity: float
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    results: List[SearchHit]
    count: int
    timestamp: float


class WakeUpResponse(BaseModel):
    wing: Optional[str]
    context: str
    token_estimate: int
    timestamp: float


class KGFactResponse(BaseModel):
    entity: str
    facts: list
    count: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()
_mm: Optional[MemoryManager] = None


def _get_mm() -> MemoryManager:
    global _mm
    if _mm is None:
        _mm = MemoryManager()
    return _mm


@router.get("/health")
async def memory_health():
    mm = _get_mm()
    st = mm.status()
    return {
        "status": "ok",
        "total_drawers": st.get("total_drawers", 0),
        "timestamp": time.time(),
    }


@router.post("/search", response_model=SearchResponse)
async def memory_search_post(req: SearchRequest):
    mm = _get_mm()
    results = mm.search(req.query, wing=req.wing, room=req.room, n_results=req.n_results)
    return SearchResponse(
        query=req.query,
        results=[
            SearchHit(
                wing=h.get("wing", h.get("metadata", {}).get("wing", "")),
                room=h.get("room", h.get("metadata", {}).get("room", "")),
                text=h.get("text", ""),
                similarity=h.get("similarity", 0),
                metadata=h.get("metadata", {}),
            )
            for h in results
        ],
        count=len(results),
        timestamp=time.time(),
    )


@router.get("/search")
async def memory_search_get(
    q: str = Query(..., description="Search query"),
    n: int = Query(10, description="Max results"),
    wing: Optional[str] = Query(None, description="Wing filter"),
    room: Optional[str] = Query(None, description="Room filter"),
):
    mm = _get_mm()
    results = mm.search(q, wing=wing, room=room, n_results=n)
    return {
        "query": q,
        "results": results,
        "count": len(results),
        "timestamp": time.time(),
    }


@router.get("/status")
async def memory_status():
    mm = _get_mm()
    return mm.status()


@router.get("/taxonomy")
async def memory_taxonomy():
    mm = _get_mm()
    return mm.taxonomy()


@router.get("/wake-up", response_model=WakeUpResponse)
async def agent_wakeup(wing: Optional[str] = Query(None, description="Wing filter")):
    mm = _get_mm()
    context = mm.wake_up(wing=wing)
    return WakeUpResponse(
        wing=wing,
        context=context,
        token_estimate=len(context) // 4,
        timestamp=time.time(),
    )


@router.get("/signals")
async def get_signals(
    symbol: str = Query("", description="Symbol filter"),
    n: int = Query(20, description="Max results"),
):
    mm = _get_mm()
    results = mm.trading.signals_only(symbol=symbol, n=n)
    return {"results": results, "count": len(results)}


@router.get("/regimes")
async def get_regimes(
    symbol: str = Query("", description="Symbol filter"),
    n: int = Query(20, description="Max results"),
):
    mm = _get_mm()
    results = mm.system.regime_changes(symbol=symbol, n=n)
    return {"results": results, "count": len(results)}


@router.get("/risks")
async def get_risks(n: int = Query(20, description="Max results")):
    mm = _get_mm()
    return {
        "failed_checks": mm.risk.failed_checks(n=n),
        "drawdowns": mm.risk.drawdowns(n=5),
        "kill_switch_events": mm.risk.kill_switch_events(n=5),
    }


@router.get("/decisions")
async def get_decisions(
    agent: str = Query("", description="Agent role filter"),
    n: int = Query(20, description="Max results"),
):
    mm = _get_mm()
    results = mm.agents.decisions(agent_role=agent, n=n)
    return {"results": results, "count": len(results)}


@router.get("/knowledge")
async def get_knowledge(
    category: str = Query("", description="Category filter"),
    component: str = Query("", description="Component filter"),
    n: int = Query(20, description="Max results"),
):
    mm = _get_mm()
    if category:
        results = mm.knowledge.by_category(category, n=n)
    elif component:
        results = mm.knowledge.by_component(component, n=n)
    else:
        results = mm.knowledge.architecture_decisions(n=n)
    return {"results": results, "count": len(results)}


@router.get("/lessons")
async def get_lessons(n: int = Query(20, description="Max results")):
    mm = _get_mm()
    results = mm.tasks.lessons(n=n)
    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Knowledge graph endpoints
# ---------------------------------------------------------------------------

@router.get("/kg/query")
async def kg_query(
    entity: str = Query(..., description="Entity to query"),
    as_of: Optional[str] = Query(None, description="Date filter YYYY-MM-DD"),
):
    mm = _get_mm()
    facts = mm.kg_query(entity, as_of=as_of)
    return KGFactResponse(entity=entity, facts=facts, count=len(facts))


@router.get("/kg/timeline")
async def kg_timeline(
    entity: Optional[str] = Query(None, description="Entity filter"),
):
    mm = _get_mm()
    timeline = mm.kg_timeline(entity)
    return {"entity": entity, "timeline": timeline, "count": len(timeline)}


@router.get("/kg/stats")
async def kg_stats():
    mm = _get_mm()
    return mm.kg_stats()


# ---------------------------------------------------------------------------
# Standalone app
# ---------------------------------------------------------------------------

app = FastAPI(title="CoinScopeAI Memory API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/memory", tags=["memory"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=False)
