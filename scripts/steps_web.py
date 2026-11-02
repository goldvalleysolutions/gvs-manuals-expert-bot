"""Web + MCP helpers for the step scripts (core 0.3, no REST API).

Core removed ``/api/*``. The step scripts talk to a bot the way people and agents do:

* visitors use web chat: ``POST /`` with cookies (``Accept: application/json`` or
  ``text/event-stream``, the same requests ``bot.js`` makes);
* the bot admin signs in at ``/admin/login`` and uses the admin forms, each with the
  ``csrf`` field, for MCP access, tokens and approvals;
* tool calls from outside go through MCP with the official SDK client.

Runs inside the bot image (core, ``mcp``, ``httpx2`` and ``cryptography`` come from
core) or from a core source checkout. Kept identical across the bot repos.
"""

from __future__ import annotations

import asyncio
import html as html_lib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

ADMIN = {"username": "admin", "password": "gvs-admin-pass-12"}  # core: 12+ characters
CSRF_RE = re.compile(r"name=csrf value='([^']+)'")
NEW_TOKEN_RE = re.compile(r"id=new-token-value>([^<]+)<")


def fail(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


class Web:
    """One browser: a cookie jar plus GET, form POST (with CSRF) and web chat."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    def request(
        self,
        method: str,
        path: str,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, str, dict[str, str]]:
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        hdrs = dict(headers or {})
        if body is not None:
            hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        req = urllib.request.Request(
            self.base + path, data=body, headers=hdrs, method=method
        )
        try:
            resp = self.opener.open(req, timeout=30)
            meta = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp.read().decode(), meta
        except urllib.error.HTTPError as exc:
            meta = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            return exc.code, exc.read().decode(), meta

    def get(self, path: str) -> tuple[int, str]:
        code, text, _ = self.request("GET", path)
        return code, text

    def csrf(self, page: str) -> str:
        found = CSRF_RE.search(page)
        if found:
            return html_lib.unescape(found.group(1))
        for cookie in self.jar:
            if cookie.name == "gvs_csrf":
                return cookie.value
        fail("no csrf field or cookie; page: " + page[:300])
        return ""

    def form(
        self, path: str, fields: dict[str, str], page_path: str | None = None
    ) -> tuple[int, str]:
        """GET the page the form lives on, then POST the form with its CSRF field."""
        code, page = self.get(page_path or path)
        if code != 200:
            fail(f"GET {page_path or path} {code}")
        code, text, _ = self.request("POST", path, {**fields, "csrf": self.csrf(page)})
        if code not in {200, 303}:
            fail(f"POST {path} {code}: {text[:300]}")
        return code, text

    # Visitor web chat (what bot.js does) -------------------------------------------
    def ask(self, text: str) -> dict[str, Any]:
        code, raw, _ = self.request(
            "POST", "/", {"text": text}, {"Accept": "application/json"}
        )
        if code != 200:
            fail(f"web chat POST / {code}: {raw[:300]}")
        return json.loads(raw)

    def ask_stream(self, text: str) -> tuple[list[dict[str, Any]], str]:
        """Streamed web chat: returns (events, reply text) from the SSE body."""
        code, raw, meta = self.request(
            "POST", "/", {"text": text}, {"Accept": "text/event-stream"}
        )
        if code != 200 or "text/event-stream" not in meta.get("content-type", ""):
            fail(f"web chat SSE {code} {meta.get('content-type')}: {raw[:300]}")
        events = []
        for line in raw.splitlines():
            if line.startswith("data:") and line[5:].strip():
                try:
                    events.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    continue
        reply = ""
        for ev in events:
            if isinstance(ev, dict) and isinstance(ev.get("text"), str):
                reply = ev["text"]
        return events, reply

    # Setup wizard and bot admin -------------------------------------------------
    def setup(
        self, smtp: dict[str, str] | None = None, wizard: dict[str, str] | None = None
    ) -> str:
        code, page = self.get("/setup")
        if code != 200:
            fail(f"GET /setup {code}")
        self.form(
            "/setup", {"step": "bot_admin", **ADMIN, "email": "admin@example.com"}
        )
        self.form(
            "/setup",
            {"step": "model", "provider": "stub", "model": "stub", "spend_cap": "25"},
        )
        _, page = self.get("/setup")
        if "value=connectors" in page:
            self.form("/setup", {"step": "connectors", **(smtp or {})})
            _, page = self.get("/setup")
        if "value=wizard" in page:
            if wizard is None:
                fail("unexpected wizard step")
            self.form("/setup", {"step": "wizard", **(wizard or {})})
        elif wizard:
            fail("expected a wizard step")
        self.form("/setup", {"step": "self_test"})
        return page

    def admin_login(self) -> None:
        self.form(
            "/admin/login", dict(ADMIN)
        )  # a wrong password is a 401, so form() fails
        code, page = self.get("/admin")
        if code != 200 or "Social login is planned later" in page:
            fail(f"admin login did not take ({code})")

    def set_policy(self, policy: str) -> None:
        """Admin -> Users: 'anyone' or 'signed_in'."""
        self.form(
            "/admin/users",
            {"action": "policy", "access_policy": policy},
            "/admin?tab=users",
        )

    def add_user(self, name: str, password: str) -> None:
        self.form(
            "/admin/users",
            {"action": "add", "new_username": name, "new_password": password},
            "/admin?tab=users",
        )
        _, page = self.get("/admin?tab=users")
        if name not in page:
            fail(f"user {name} not listed after add")

    def user_login(self, name: str, password: str) -> None:
        self.form(
            "/login", {"username": name, "password": password, "next": "/"}
        )  # 401 fails

    def set_mcp_access(self, access: str) -> None:
        self.form("/admin/mcp", {"access": access}, "/admin?tab=mcp")

    def issue_mcp_token(self, name: str) -> str:
        _, text = self.form(
            "/admin/mcp/tokens",
            {"name": name, "scope": "", "days": "90"},
            "/admin?tab=mcp",
        )
        found = NEW_TOKEN_RE.search(text)
        if not found:
            fail("no one-time MCP token on the page")
        token = html_lib.unescape(found.group(1))
        if not token.startswith("mcp_"):
            fail("MCP token has the wrong shape")
        return token

    def enable_mcp(self, mode: str, name: str) -> str:
        self.set_mcp_access(mode)
        return self.issue_mcp_token(name)

    def approve(self, aid: str) -> str:
        """Approve in the chat UI's approval card (bot admin, CSRF); returns the new status."""
        self.form(
            f"/chat/approvals/{aid}", {"decision": "approve", "back": "chat"}, "/"
        )
        code, raw, _ = self.request(
            "GET", f"/chat/approvals/{aid}", headers={"Accept": "application/json"}
        )
        if code != 200:
            fail(f"GET /chat/approvals/{aid} {code}")
        return json.loads(raw)["status"]

    def model_switch_gated(self) -> None:
        """An untested model change is refused, the key never echoes, then back to stub."""
        _, text = self.form(
            "/admin/settings",
            {
                "provider": "openai_compat",
                "model": "gpt-4o-mini",
                "api_key": "sk-not-a-real-key",
            },
            "/admin?tab=model",
        )
        _, page = self.get("/admin?tab=model")
        if "sk-not-a-real-key" in page or "sk-not-a-real-key" in text:
            fail("API key echoed on the admin page")
        self.form(
            "/admin/settings", {"provider": "stub", "model": "stub"}, "/admin?tab=model"
        )

    def root_login(self, key_path: Path, bot_id: str) -> None:
        import secrets

        from core.auth.token import load_private_key, sign_token

        token = sign_token(load_private_key(key_path), bot_id, secrets.token_urlsafe(8))
        code, _ = self.get("/gvs/login?token=" + token)
        if code not in {200, 303}:
            fail(f"/gvs/login {code}")


def write_root_key(ctl: Path) -> None:
    """A throwaway GVS root key pair: private in ctl, public to install as keys/gvs_root.pub."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    ctl.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    (ctl / "gvs_test_ed25519").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    )
    (ctl / "gvs_root.pub").write_bytes(pub + b"\n")


# MCP (official SDK client) ---------------------------------------------------------
async def _mcp(
    url: str, token: str, name: str | None, args: dict[str, Any] | None
) -> Any:
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    async with (
        httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx2.Timeout(30.0, read=60.0),
        ) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        if name is None:
            listed = await client.list_tools()
            return [t.name for t in listed.tools]
        result = await client.call_tool(name, args or {})
        parts = [getattr(c, "text", "") for c in (result.content or [])]
        return "\n".join(p for p in parts if p)


def _run(coro: Any) -> Any:
    """asyncio.run in a worker thread, so it also works under Playwright's sync API loop."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


def mcp_list(base: str, token: str) -> list[str]:
    return _run(_mcp(base.rstrip("/") + "/mcp", token, None, None))


def mcp_call(
    base: str, token: str, name: str, args: dict[str, Any] | None = None
) -> str:
    return _run(_mcp(base.rstrip("/") + "/mcp", token, name, args))


def save_cookies(web: Web, path: Path) -> None:
    rows = [
        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
        for c in web.jar
    ]
    path.write_text(json.dumps(rows))


def load_cookies(web: Web, path: Path) -> None:
    from http.cookiejar import Cookie

    for row in json.loads(path.read_text()):
        web.jar.set_cookie(
            Cookie(
                0,
                row["name"],
                row["value"],
                None,
                False,
                row["domain"],
                True,
                row["domain"].startswith("."),
                row["path"],
                True,
                False,
                None,
                True,
                None,
                None,
                {},
            )
        )


def check_access_policy(base: str, admin: Web, paths: list[str]) -> None:
    """Anyone: paths open logged out. Signed-in users only: login page, then they open."""
    admin.set_policy("anyone")
    visitor = Web(base)
    for path in paths:
        code, page = visitor.get(path)
        if code != 200 or "Sign in to" in page:
            fail(f"Anyone: {path} did not open logged out ({code})")
    admin.set_policy("signed_in")
    admin.add_user("dana", "dana-pass-12345")
    try:
        visitor = Web(base)
        for path in paths:
            code, page = visitor.get(path)
            if "Sign in to" not in page:
                fail(f"Signed-in: {path} did not redirect to /login ({code})")
        visitor.user_login("dana", "dana-pass-12345")
        for path in paths:
            code, page = visitor.get(path)
            if code != 200 or "Sign in to" in page:
                fail(f"Signed-in: {path} did not open for the user ({code})")
    finally:
        admin.set_policy("anyone")
