"""Keyword search over role-owned manuals under ``/data/manuals-expert/``.

Chat and MCP call ``search_manuals``. REST ``GET /r/manuals-expert/search``
imports ``search_corpus`` from this file (architecture §16.4).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    from gvs_bot_core.tools import tool
    from gvs_bot_core.tools.registry import registered
except ImportError:  # bot-core image also exposes the runtime package as `core`
    from core.sdk import tool
    from core.tools.registry import registered

SLUG = "manuals-expert"
TOKEN = re.compile(r"[a-z0-9]+")
DEFAULT_LIMIT = 5
CHUNK = 500


def role_store(data_dir: Path) -> Path:
    return Path(data_dir) / SLUG


def seed_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "seed"


def ensure_seeded(data_dir: Path) -> Path:
    """Copy the image seed corpus into the role store on first use."""
    dest = role_store(data_dir)
    dest.mkdir(parents=True, exist_ok=True)
    if any(path.is_file() and path.suffix.lower() == ".md" for path in dest.iterdir()):
        return dest
    src = seed_dir()
    if src.is_dir():
        for path in sorted(src.glob("*.md")):
            target = dest / path.name
            if not target.exists():
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def title_of(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem.replace("-", " ").title()


def chunks_of(text: str) -> list[str]:
    paras = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    out: list[str] = []
    for para in paras:
        if len(para) <= CHUNK:
            out.append(para)
            continue
        out.extend(para[i : i + CHUNK] for i in range(0, len(para), CHUNK))
    return out or [text[:CHUNK]]


def search_corpus(query: str, data_dir: Path, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Score seeded (and owner-added) ``.md`` files with term frequency + title bonus."""
    dest = ensure_seeded(data_dir)
    q_tokens = tokenize(query)
    cap = max(1, min(int(limit or DEFAULT_LIMIT), 20))
    hits: list[dict[str, Any]] = []
    for path in sorted(dest.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = title_of(path, text)
        title_tokens = set(tokenize(title))
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if not q_tokens:
            hits.append(
                {
                    "title": title,
                    "path": path.name,
                    "score": 0.0,
                    "snippet": first[:220],
                }
            )
            continue
        best = 0.0
        best_snip = ""
        for chunk in chunks_of(text):
            c_tokens = tokenize(chunk)
            tf = sum(c_tokens.count(token) for token in q_tokens)
            title_bonus = sum(2 for token in q_tokens if token in title_tokens)
            score = float(tf + title_bonus)
            if score > best:
                best = score
                best_snip = " ".join(chunk.split())[:220]
        if best > 0:
            hits.append(
                {
                    "title": title,
                    "path": path.name,
                    "score": best,
                    "snippet": best_snip,
                }
            )
    hits.sort(key=lambda hit: (-float(hit["score"]), str(hit["title"])))
    return hits[:cap]


def format_hits(query: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return f"No manuals matched {query!r}."
    lines = [f"Found {len(hits)} hit(s) for {query!r}:"]
    for i, hit in enumerate(hits, 1):
        lines.append(f"{i}. {hit['title']} ({hit['path']}, score={hit['score']:g})")
        if hit.get("snippet"):
            lines.append(f"   {hit['snippet']}")
    return "\n".join(lines)


def search_manuals(
    store: Any = None,
    actor: str = "",
    query: str = "",
    limit: int = DEFAULT_LIMIT,
    **_: Any,
) -> str:
    data_dir = Path(store.data_dir) if store is not None else Path("/data")
    hits = search_corpus(query, data_dir, limit=limit)
    return format_hits(query, hits)


if "search_manuals" not in registered():
    tool(
        "search_manuals",
        schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Words to find in the manuals",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max hits (1-20)",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
        kind="read",
        expose=["chat", "mcp"],
    )(search_manuals)
