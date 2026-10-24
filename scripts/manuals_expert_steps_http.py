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

import httpx2

from tests.mcp_helpers import call_tool, enable_mcp_http, list_tools

BRAND = "Manuals Expert in a Box"
QUERY = "descale espresso"


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
            "step": "box_admin",
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

    print("step 6 box admin 404")
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
    http = httpx2.Client(base_url=base, follow_redirects=True, timeout=30.0)
    token = enable_mcp_http(http, mode="read_only", name="manuals")
    names = list_tools(f"{base}/mcp", token)
    assert "ask" in names and "search_manuals" in names, names
    assert "email.send" not in names, names
    found = call_tool(f"{base}/mcp", token, "search_manuals", {"query": QUERY})
    assert "Maple Espresso E-20" in found, found
    mcp_body = json.loads(found)
    assert mcp_body["status"] == "ok", mcp_body
    assert mcp_body["result"] == rest["text"], (mcp_body["result"], rest["text"])
    asked = call_tool(f"{base}/mcp", token, "ask", {"text": "ping"})
    assert "(stub)" in asked or "ping" in asked, asked
    http.close()
    print("OK manuals-expert-steps")


if __name__ == "__main__":
    main()
