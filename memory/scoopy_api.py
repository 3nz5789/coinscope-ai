#!/usr/bin/env python3
import sys
import os
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Add the current directory to sys.path so we can import the memory package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.manager import MemoryManager
from memory.config import MemoryConfig
from memory.base_store import PalaceStore

app = FastAPI(title="Scoopy Memory API", description="REST API for the project coordinator memory system")

# Global MemoryManager instance
config = MemoryConfig()
mm = MemoryManager(config)

class MemoryAddRequest(BaseModel):
    content: str
    wing: str
    room: str
    hall: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CustomStore(PalaceStore):
    def __init__(self, config, wing):
        self._wing = wing
        super().__init__(config)

@app.get("/health")
def health():
    return {"status": "ok", "agent": "Scoopy"}

@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    wing: Optional[str] = None,
    room: Optional[str] = None,
    limit: int = 5
):
    results = mm.deep_search(q, wing=wing, room=room, n_results=limit)
    return {"query": q, "results": results}

@app.post("/add")
def add_memory(req: MemoryAddRequest):
    try:
        store = CustomStore(config, req.wing)
        drawer_id = store.file_drawer(
            content=req.content,
            room=req.room,
            hall=req.hall or "",
            metadata=req.metadata or {}
        )
        mm.flush()
        return {"success": True, "drawer_id": drawer_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/wake-up")
def wake_up(wing: Optional[str] = None):
    context = mm.wake_up(wing=wing)
    return {"context": context}

@app.get("/status")
def status():
    stack = mm._get_stack()
    if not stack:
        return {"error": "Memory stack not initialized"}
    return stack.status()

@app.on_event("shutdown")
def shutdown_event():
    mm.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
