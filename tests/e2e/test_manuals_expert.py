"""Manuals Expert Bot e2e: setup, chat with search, the manual search page, MCP.

The search route is ``@user_level``: it follows the bot's access policy
(test_access_policy.py covers Anyone and Signed-in users only).
"""

from __future__ import annotations

import json
import urllib.parse

from playwright.sync_api import Page, expect
from steps_web import mcp_call, mcp_list
from ui import admin_web, chat, mcp_initialize, setup_ui

BRAND = "Manuals Expert Bot"
HTTP_SETUP: dict = {}
QUERY = "descale espresso"
SEARCH = "/r/manuals-expert/search?q=" + urllib.parse.quote(QUERY)


def test_setup(page: Page, fresh_bot) -> None:
    page.goto(fresh_bot.base + "/setup")
    assert "SMTP_HOST" not in page.content()
    seen = setup_ui(page, fresh_bot.base)
    assert (
        "wizard" not in seen and seen[0] == "bot_admin" and seen[-1] == "self_test"
    ), seen
    page.goto(fresh_bot.base + "/")
    expect(page.locator("body")).to_contain_text(BRAND)
    expect(page.locator("body")).not_to_contain_text("in a Box")
    assert not page.js_errors


def test_chat_tools(page: Page, ready_bot) -> None:
    page.goto(ready_bot.base + "/")
    for call in ("CALL clock.now {}", 'CALL search_manuals {"query":"' + QUERY + '"}'):
        reply = chat(page, call)
        assert "error" not in (reply.get_attribute("class") or ""), call
        expect(reply.locator("summary")).to_have_count(1)
    expect(chat(page, "CALL web.browse {}")).to_contain_text("not allowed")
    assert not page.js_errors


def test_search_page(page: Page, ready_bot) -> None:
    """/search is @user_level: under the default Anyone policy it opens logged out."""
    resp = page.goto(ready_bot.base + SEARCH)
    assert resp.status == 200
    data = json.loads(page.locator("body").inner_text())
    assert "Maple Espresso E-20" in [hit["title"] for hit in data["results"]]
    assert "descale" in data["text"].lower()
    assert not page.csp_errors, page.csp_errors


def test_mcp_initialize_and_tools(ready_bot) -> None:
    assert admin_web(ready_bot.base).get("/mcp")[0] == 404  # off until enabled
    token = admin_web(ready_bot.base).enable_mcp("read_only", "e2e")
    assert mcp_initialize(ready_bot.base, token)["serverInfo"]["name"]
    names = mcp_list(ready_bot.base, token)
    assert {"ask", "search_manuals"} <= set(names) and "email.send" not in names, names
    found = json.loads(
        mcp_call(ready_bot.base, token, "search_manuals", {"query": QUERY})
    )
    route = json.loads(admin_web(ready_bot.base).get(SEARCH)[1])
    assert found["status"] == "ok" and found["result"] == route["text"]
