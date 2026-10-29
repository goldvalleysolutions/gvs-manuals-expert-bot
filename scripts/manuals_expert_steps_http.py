"""Drive the Manuals Expert walkthrough against a running image (CI + make)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any

BRAND = "Manuals Expert Bot"
QUERY = "descale espresso"
MCP_ACCEPT = "application/json, text/event-stream"
TOKEN_RE = re.compile(
    r"(?:token|secret)['\"]?\s*[:=]\s*['\"]([A-Za-z0-9._\-]{12,})['\"]",
    re.I,
)
CODE_RE = re.compile(r"<code[^>]*>\s*([A-Za-z0-9._\-]{12,})\s*</code>", re.I)


def mcp_url(base: str) -> str:
    return base.rstrip("/") + "/mcp/"


def origin_of(base: str) -> str:
    parsed = urllib.parse.urlparse(base)
    return f"{parsed.scheme}://{parsed.netloc}"


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def request(
    opener: urllib.request.OpenerDirector,
    base: str,
    method: str,
    path: str,
    data: dict[str, str] | bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    body: bytes | None = None
    hdrs = dict(headers or {})
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif isinstance(data, bytes):
        body = data
    req = urllib.request.Request(base + path, data=body, headers=hdrs, method=method)
    try:
        resp = opener.open(req, timeout=20)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def csrf_from(html: str) -> str:
    match = re.search(r"name=csrf value='([^']+)'", html)
    if not match:
        raise SystemExit("no csrf field in " + html[:400])
    return match.group(1)


def post_form(
    opener: urllib.request.OpenerDirector,
    base: str,
    path: str,
    fields: dict[str, str],
    html: str | None = None,
) -> tuple[int, str]:
    if html is None:
        _, html = request(opener, base, "GET", path)
    payload = dict(fields)
    payload["csrf"] = csrf_from(html)
    return request(opener, base, "POST", path, payload)


def ask(opener: urllib.request.OpenerDirector, base: str, text: str) -> dict:
    code, raw = request(
        opener,
        base,
        "POST",
        "/api/ask",
        json.dumps({"text": text}).encode(),
        {"Content-Type": "application/json"},
    )
    if code != 200:
        raise SystemExit(f"/api/ask {code}: {raw[:300]}")
    return json.loads(raw)


def _token_from(body: str) -> str | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        for key in ("token", "mcp_token", "secret"):
            value = payload.get(key)
            if isinstance(value, str) and len(value) >= 12:
                return value
    match = TOKEN_RE.search(body) or CODE_RE.search(body)
    return match.group(1) if match else None


def enable_mcp(opener: urllib.request.OpenerDirector, base: str, name: str = "manuals") -> str:
    code, body = request(
        opener,
        base,
        "POST",
        "/api/admin/mcp/tokens",
        json.dumps({"mode": "read_only", "name": name}).encode(),
        {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": origin_of(base),
        },
    )
    token = _token_from(body)
    if not token:
        raise SystemExit(f"could not mint MCP token ({code}): {body[:400]}")
    return token


def _mcp_rpc(url: str, token: str, method: str, params: dict[str, Any] | None = None) -> Any:
    if not url.endswith("/"):
        url += "/"
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": MCP_ACCEPT,
            "Origin": origin_of(url),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"MCP {method} {exc.code}: {exc.read().decode()[:300]}") from exc
    if raw.startswith("event:") or raw.startswith("data:"):
        lines = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        raw = lines[-1] if lines else raw
    body = json.loads(raw)
    if body.get("error"):
        raise SystemExit(f"MCP {method} error: {body['error']}")
    return body.get("result")


def list_tools(url: str, token: str) -> list[str]:
    result = _mcp_rpc(url, token, "tools/list")
    tools = result.get("tools", result) if isinstance(result, dict) else result
    names: list[str] = []
    for item in tools or []:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def call_tool(url: str, token: str, name: str, arguments: dict[str, Any]) -> str:
    result = _mcp_rpc(url, token, "tools/call", {"name": name, "arguments": arguments})
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        if "result" in result and isinstance(result["result"], str):
            return result["result"]
        content = result.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "text" in first:
                return str(first["text"])
        return json.dumps(result)
    return json.dumps(result)


def main() -> None:
    base, _repo, cname = sys.argv[1:4]
    opener = _opener()

    print("step 1 setup")
    code, html = request(opener, base, "GET", "/setup")
    assert code == 200, code
    assert "SMTP_HOST" not in html
    code, _ = post_form(
        opener,
        base,
        "/setup",
        {
            "step": "bot_admin",
            "username": "admin",
            "password": "secret12",
            "email": "admin@example.com",
        },
        html,
    )
    assert code in {200, 303}, code
    code, html = request(opener, base, "GET", "/setup")
    code, _ = post_form(
        opener,
        base,
        "/setup",
        {"step": "model", "provider": "stub", "model": "stub", "spend_cap": "25"},
        html,
    )
    assert code in {200, 303}, code
    code, html = request(opener, base, "GET", "/setup")
    if "value=wizard" in html:
        raise SystemExit("manuals-expert must not add a wizard step")
    if "value=connectors" in html:
        code, html = post_form(opener, base, "/setup", {"step": "connectors"}, html)
        assert code in {200, 303}, code
        code, html = request(opener, base, "GET", "/setup")
    code, _ = post_form(opener, base, "/setup", {"step": "self_test"}, html)
    assert code in {200, 303}, code
    code, home = request(opener, base, "GET", "/")
    assert code == 200 and BRAND in home
    assert "Powered by Gold Valley Solutions" in home

    print("step 2 clock")
    assert ask(opener, base, "CALL clock.now {}")["blocked"] is False

    print("step 3 search_manuals")
    tool_hit = ask(opener, base, 'CALL search_manuals {"query":"' + QUERY + '"}')
    assert tool_hit["blocked"] is False

    print("step 4 REST parity")
    code, raw = request(
        opener, base, "GET", "/r/manuals-expert/search?q=" + urllib.parse.quote(QUERY)
    )
    assert code == 200, (code, raw[:300])
    rest = json.loads(raw)
    titles = [hit["title"] for hit in rest["results"]]
    assert "Maple Espresso E-20" in titles, titles
    assert "descale" in rest["text"].lower()

    listed = subprocess.check_output(
        ["docker", "exec", cname, "ls", "/data/manuals-expert"],
        text=True,
    )
    assert "maple-espresso-e20.md" in listed, listed

    print("step 5 web blocked")
    assert ask(opener, base, "CALL web.browse {}")["blocked"] is True

    print("step 6 bot admin 404")
    admin = _opener()
    code, login_html = request(admin, base, "GET", "/admin/login")
    assert code == 200
    code, _ = post_form(
        admin,
        base,
        "/admin/login",
        {"username": "admin", "password": "secret12"},
        login_html,
    )
    assert code in {200, 303}, code
    for path in ("/gvs/role", "/gvs/skills", "/gvs/memory", "/gvs/activity"):
        code, body = request(admin, base, "GET", path)
        assert code == 404, (path, code)
        assert BRAND in body

    print("step 7 mcp")
    code, mcp_off = request(opener, base, "GET", "/mcp")
    assert code == 404, (code, mcp_off[:200])
    token = enable_mcp(admin, base, name="manuals")
    names = list_tools(mcp_url(base), token)
    assert "ask" in names and "search_manuals" in names, names
    assert "email.send" not in names, names
    found = call_tool(mcp_url(base), token, "search_manuals", {"query": QUERY})
    assert "Maple Espresso E-20" in found, found
    mcp_body = json.loads(found)
    assert mcp_body["status"] == "ok", mcp_body
    assert mcp_body["result"] == rest["text"], (mcp_body["result"], rest["text"])
    asked = call_tool(mcp_url(base), token, "ask", {"text": "ping"})
    assert "(stub)" in asked or "ping" in asked, asked
    print("OK manuals-expert-steps")


if __name__ == "__main__":
    main()
