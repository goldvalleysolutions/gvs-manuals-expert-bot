"""Manuals pages under ``/r/manuals-expert/``. Every route needs a signed-in account.

* ``GET  /search``  JSON search (same text as the ``search_manuals`` tool). Logged out: 401.
* ``GET  /``        Manuals page: demo-mode label, search box, manuals in use, upload.
* ``POST /upload``  Bot admin only: add a ``.md`` or ``.pdf`` manual (CSRF-checked).

Routes are ``@user_level`` so signed-in users can reach them under either access
policy; the handlers then refuse anyone who is not signed in, so there is no public
search endpoint even when the bot's chat is open to "Anyone".
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from core.auth import csrf
from core.auth.users import current_actor
from core.sdk import user_level
from core.ui.html import bot_name, esc, page
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

_TOOLS = Path(__file__).resolve().parent.parent / "tools" / "search.py"
BASE = "/r/manuals-expert/"


def _search_mod() -> Any:
    spec = importlib.util.spec_from_file_location("manuals_expert_search_tool", _TOOLS)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tools/search.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_search = _search_mod()
router = APIRouter()


def _signed_in(request: Request) -> Any:
    return current_actor(request)


def _to_login(request: Request) -> Response:
    """Logged out: say why before sending them to sign in (Core's /login has no hint hook)."""
    nxt = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    href = "/login?" + urlencode({"next": nxt})
    body = (
        "<h1>Manuals</h1><p id=signin-hint>Sign in to search your manuals.</p>"
        f"<p><a class=button id=signin href='{esc(href)}'>Sign in</a></p>"
    )
    return page("Manuals", body, bot=bot_name(request), nav="<a href='/'>Chat</a>")


@router.get("/search")
@user_level
def search(
    request: Request,
    q: str = Query(default="", description="Words to find in the manuals"),
    limit: int = Query(default=5, ge=1, le=20),
) -> Response:
    if _signed_in(request) is None:
        return JSONResponse(
            {"error": "Sign in to search the manuals."}, status_code=401
        )
    return JSONResponse(_search.run_search(request.app.state.store, q, limit))


def safe_name(name: str) -> str:
    base = Path(name or "").name
    stem, dot, ext = base.rpartition(".")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem if dot else base).strip(".-")[:80]
    ext = ext.lower() if dot else ""
    return f"{stem or 'manual'}.{ext}" if ext else ""


@router.get("/")
@user_level
def manuals_page(request: Request, q: str = "", msg: str = "") -> Response:
    actor = _signed_in(request)
    if actor is None:
        return _to_login(request)
    store = request.app.state.store
    files, is_demo = _search.corpus(Path(store.data_dir))
    bits: list[str] = ["<h1>Manuals</h1>"]
    if _search.is_demo_mode(store):
        bits.append(
            "<p class='toast demo-mode' id=demo-mode role=status><strong>Demo mode</strong>: "
            "no AI key is set, so you get search results, not written answers. "
            "Real answers need your own AI provider key (Admin &gt; Settings).</p>"
        )
    if is_demo:
        bits.append(
            "<p id=demo-manuals><strong>Demo manuals</strong>: these coffee-shop manuals "
            "are examples. Add your own and they drop out of results.</p>"
        )
    if msg:
        bits.append(f"<p class=toast role=status id=upload-msg>{esc(msg)}</p>")
    bits.append(
        f"<form method=get action={BASE} class=manual-search>"
        "<label for=q>Ask your manuals</label>"
        f"<input id=q name=q value='{esc(q)}' placeholder='e.g. descale espresso'>"
        "<button>Search</button></form>"
    )
    if q:
        result = _search.run_search(store, q)
        if result["results"]:
            items = "".join(
                f"<li><strong>{esc(h['title'])}</strong>"
                f"{' &gt; ' + esc(h['section']) if h.get('section') else ''}"
                f"<br><span class=snippet>{esc(h['snippet'])}</span></li>"
                for h in result["results"]
            )
            bits.append(f"<ol id=results>{items}</ol>")
        else:
            bits.append(
                f"<p id=results>Not in your manuals: nothing matched {esc(q)!s}.</p>"
            )
    names = "".join(f"<li>{esc(p.name)}</li>" for p in files)
    label = "Demo manuals in use" if is_demo else "Your manuals"
    bits.append(f"<h2>{label}</h2><ul id=manual-list>{names}</ul>")
    if actor.is_admin:
        bits.append(
            f"<h2 id=add-manual>Add a manual</h2><form method=post action={BASE}upload "
            f"enctype=multipart/form-data id=upload-form>{csrf.field(request)}"
            "<label for=manual>Markdown (.md) or PDF (.pdf), up to 10 MB</label>"
            "<input type=file id=manual name=manual accept='.md,.pdf' required>"
            "<button id=upload>Upload</button></form>"
        )
    return page(
        "Manuals",
        "".join(bits),
        csrf=csrf.token(request),
        bot=bot_name(request),
        nav="<a href='/'>Chat</a> <a href='/admin'>Admin</a>",
    )


@router.post("/upload")
@user_level
async def upload(request: Request) -> Response:
    actor = _signed_in(request)
    if actor is None:
        return JSONResponse({"error": "Sign in to add manuals."}, status_code=401)
    if not actor.is_admin:
        return JSONResponse(
            {"error": "Only the bot admin can add manuals."}, status_code=403
        )
    form = await request.form()
    if not csrf.valid(request, {"csrf": str(form.get("csrf") or "")}):
        return JSONResponse(
            {"error": "Form expired; reload and try again."}, status_code=403
        )
    item = form.get("manual")
    name = safe_name(getattr(item, "filename", "") or "")
    if item is None or not hasattr(item, "read") or not name.endswith(_search.SUFFIXES):
        return _back("Only .md and .pdf files can be added.")
    data = await item.read()  # type: ignore[union-attr]
    if not data or len(data) > _search.MAX_BYTES:
        return _back("That file is empty or over 10 MB.")
    if name.endswith(".pdf") and not data.startswith(b"%PDF"):
        return _back("That file is not a PDF.")
    if name.endswith(".pdf"):
        problem = _search.check_pdf(data)
        if problem:
            return _back(problem)
    dest = _search.ensure_store(Path(request.app.state.store.data_dir)) / name
    dest.write_bytes(data)
    request.app.state.store.log(
        actor.name, "manuals.upload", f"file={name}", source="web"
    )
    return _back(f"Added {name}. Demo manuals are now out of results.")


def _back(msg: str) -> Response:
    return RedirectResponse(BASE + "?" + urlencode({"msg": msg}), status_code=303)
