"""REST adapter: ``GET /r/manuals-expert/search`` calls ``tools/search.py``."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from core.sdk import user_level
from fastapi import APIRouter, Query, Request

_TOOLS = Path(__file__).resolve().parent.parent / "tools" / "search.py"


def _search_mod() -> Any:
    spec = importlib.util.spec_from_file_location("manuals_expert_search_tool", _TOOLS)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tools/search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_search = _search_mod()
router = APIRouter()


@router.get("/search")
@user_level  # follows the bot's access policy (Anyone / Signed-in users only)
def search(
    request: Request,
    q: str = Query(default="", description="Words to find in the manuals"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    store = request.app.state.store
    hits = _search.search_corpus(q, store.data_dir, limit=limit)
    return {"query": q, "results": hits, "text": _search.format_hits(q, hits)}
