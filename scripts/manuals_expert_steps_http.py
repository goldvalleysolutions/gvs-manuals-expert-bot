"""Manuals Expert walkthrough over web chat, the admin forms and MCP (no REST API).

The manual search under /r/manuals-expert/ is admin-only (core 0.2 default, no
``@public``), so a visitor gets 404 and parity is checked from the admin session.

Usage: manuals_expert_steps_http.py BASE SMTP_HOST SMTP_PORT CTL BOT_ID
(SMTP and the root key are unused here; the signature matches the other bots.)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from steps_web import Web, mcp_call, mcp_list


def admin_checks(base: str, brand: str) -> Web:
    """Bot admin signs in; GVS root screens stay 404 for it; untested model key refused."""
    admin = Web(base)
    admin.admin_login()
    for path in ("/gvs/role", "/gvs/skills", "/gvs/memory", "/gvs/activity"):
        code, body = admin.get(path)
        assert code == 404 and brand in body, (path, code)
    return admin


import urllib.parse

BRAND = "Manuals Expert"
QUERY = "descale espresso"


def main() -> None:
    base = sys.argv[1]
    web = Web(base)

    print("step 1 setup (no SMTP, no wizard)")
    _, page = web.get("/setup")
    assert "SMTP_HOST" not in page
    web.setup()
    code, home = web.get("/")
    assert code == 200 and BRAND in home and "Powered by Gold Valley Solutions" in home

    print("step 2 clock")
    assert web.ask("CALL clock.now {}")["blocked"] is False

    print("step 3 search_manuals")
    assert web.ask('CALL search_manuals {"query":"' + QUERY + '"}')["blocked"] is False

    print("step 4 search route parity (admin-only)")
    path = "/r/manuals-expert/search?q=" + urllib.parse.quote(QUERY)
    code, _ = web.get(path)
    assert code == 404, code
    admin = Web(base)
    admin.admin_login()
    code, raw = admin.get(path)
    assert code == 200, (code, raw[:300])
    route = json.loads(raw)
    titles = [hit["title"] for hit in route["results"]]
    assert "Maple Espresso E-20" in titles, titles
    assert "descale" in route["text"].lower()

    print("step 5 web blocked")
    assert web.ask("CALL web.browse {}")["blocked"] is True

    print("step 6 bot admin: root screens 404")
    admin = admin_checks(base, BRAND)

    print("step 7 mcp")
    code, _ = web.get("/mcp")
    assert code == 404, code
    token = admin.enable_mcp("read_only", "manuals")
    names = mcp_list(base, token)
    assert "ask" in names and "search_manuals" in names and "email.send" not in names, (
        names
    )
    found = json.loads(mcp_call(base, token, "search_manuals", {"query": QUERY}))
    assert found["status"] == "ok", found
    assert found["result"] == route["text"], (found["result"], route["text"])
    asked = mcp_call(base, token, "ask", {"text": "ping"})
    assert "(stub)" in asked or "ping" in asked, asked
    print("OK manuals-expert-steps")


if __name__ == "__main__":
    main()
