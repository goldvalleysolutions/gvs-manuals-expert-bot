"""Manuals Expert Bot e2e (desktop + mobile, stub LLM): setup, chat, signed-in manuals
page with the demo-mode label, 401 for logged-out search, upload, MCP.

Search has no public endpoint: logged out, ``/r/manuals-expert/search`` is 401 and the
manuals page asks browsers to sign in (bot hint page under Anyone, Core's /login
redirect under Signed-in users only).
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect
from steps_web import mcp_call, mcp_list
from ui import (
    ADMIN_PASSWORD,
    USER,
    USER_PASSWORD,
    admin_login,
    admin_web,
    chat,
    mcp_initialize,
    setup_ui,
)

BRAND = "Manuals Expert Bot"
HTTP_SETUP: dict = {}
QUERY = "descale espresso"
SEARCH = "/r/manuals-expert/search?q=" + urllib.parse.quote(QUERY)
MANUALS = "/r/manuals-expert/"
TABLE_MD = """# Hi-Lo treatment table TT-3

## Table will not lower
Check the foot switch cable and the hand pendant.

## Cleaning the upholstery
Wipe the vinyl with mild soap. Do not use alcohol wipes on the upholstery.
"""


def _status(url: str) -> int:
    try:
        return urllib.request.urlopen(
            urllib.request.Request(url, headers={"Accept": "application/json"}),
            timeout=10,
        ).status
    except urllib.error.HTTPError as exc:
        return exc.code


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


def test_health_bot_version(ready_bot) -> None:
    body = json.loads(urllib.request.urlopen(ready_bot.base + "/health").read())
    assert re.fullmatch(r"0\.1\.\d+", body["bot"]["version"]), body


def test_chat_tools(page: Page, ready_bot) -> None:
    page.goto(ready_bot.base + "/")
    reply = chat(page, "CALL clock.now {}")
    assert "error" not in (reply.get_attribute("class") or "")
    expect(reply.locator("summary")).to_have_count(1)
    # Anonymous chat visitors cannot search the manuals.
    reply = chat(page, 'CALL search_manuals {"query":"' + QUERY + '"}')
    expect(reply).to_contain_text("Sign in to search the manuals")
    expect(chat(page, "CALL web.browse {}")).to_contain_text("not allowed")
    assert not page.js_errors


@pytest.mark.parametrize("policy", ["anyone", "signed_in"])
def test_logged_out_search_is_401(page: Page, ready_bot, policy: str) -> None:
    admin = admin_web(ready_bot.base)
    admin.set_policy(policy)
    try:
        assert _status(ready_bot.base + SEARCH) == 401
        resp = page.request.get(ready_bot.base + SEARCH)
        assert resp.status == 401 and "Maple" not in resp.text()
        page.goto(ready_bot.base + MANUALS)
        if policy == "anyone":
            expect(page.locator("#signin-hint")).to_have_text(
                "Sign in to search your manuals."
            )
            page.locator("#signin").click()
        expect(page).to_have_url(re.compile(r"/login\?next="))
    finally:
        admin.set_policy("anyone")


def test_chat_search_manuals_cited(page: Page, ready_bot) -> None:
    """Signed in: chat -> search_manuals tool -> cited answer (stub emits the tool call)."""
    admin_login(page, ready_bot.base)
    page.goto(ready_bot.base + "/")
    reply = chat(page, 'CALL search_manuals {"query":"' + QUERY + '"}')
    expect(reply.locator("summary")).to_have_count(1)  # the tool step is shown
    expect(reply).to_contain_text("Maple Espresso E-20")
    expect(reply).to_contain_text("Browse or add manuals: /r/manuals-expert/")
    shots = os.environ.get("GVS_SHOTS_DIR")
    if shots:
        page.screenshot(
            path=str(Path(shots) / "e2e-stub-chat-search.png"), full_page=True
        )
    page.goto(ready_bot.base + "/admin")
    expect(page.locator("body")).to_contain_text("/r/manuals-expert/")
    assert not page.js_errors


def test_user_login_sees_demo_mode(page: Page, ready_bot) -> None:
    admin = admin_web(ready_bot.base)
    _code, users = admin.get("/admin?tab=users")
    if USER not in users:
        admin.add_user(USER, USER_PASSWORD)
    page.goto(ready_bot.base + MANUALS + "?q=" + urllib.parse.quote(QUERY))
    page.locator("#signin").click()
    expect(page).to_have_url(re.compile(r"/login"))
    page.fill("#username", USER)
    page.fill("#password", USER_PASSWORD)
    page.locator("form[action='/login'] button:not(.password-toggle)").click()
    page.wait_for_load_state()
    page.goto(ready_bot.base + MANUALS + "?q=" + urllib.parse.quote(QUERY))
    expect(page.locator("#demo-mode")).to_be_visible()
    expect(page.locator("#demo-mode")).to_contain_text("Demo mode")
    expect(page.locator("#demo-mode")).to_contain_text("your own AI provider key")
    expect(page.locator("#demo-manuals")).to_be_visible()
    expect(page.locator("#results")).to_contain_text("Maple Espresso E-20")
    expect(page.locator("#upload-form")).to_have_count(0)  # users cannot upload
    resp = page.request.get(ready_bot.base + SEARCH)
    assert resp.status == 200 and json.loads(resp.text())["demo_mode"] is True
    assert not page.csp_errors, page.csp_errors
    assert not page.js_errors


def test_mcp_initialize_and_tools(ready_bot) -> None:
    assert admin_web(ready_bot.base).get("/mcp")[0] == 404  # off until enabled
    token = admin_web(ready_bot.base).enable_mcp("read_only", "e2e")
    assert mcp_initialize(ready_bot.base, token)["serverInfo"]["name"]
    names = mcp_list(ready_bot.base, token)
    assert {"ask", "search_manuals"} <= set(names) and "email.send" not in names, names
    found = json.loads(
        mcp_call(ready_bot.base, token, "search_manuals", {"query": QUERY})
    )
    code, raw = admin_web(ready_bot.base).get(SEARCH)
    assert code == 200, code
    assert found["status"] == "ok" and found["result"] == json.loads(raw)["text"]


def test_admin_upload_replaces_demo_manuals(
    page: Page, ready_bot, tmp_path: Path
) -> None:
    """Runs last in this module: after the upload, the demo set is out of results."""
    page.goto(ready_bot.base + "/admin/login")
    page.fill("#password", ADMIN_PASSWORD)
    page.locator("form button:not([type=button])").last.click()
    page.wait_for_load_state()
    page.goto(ready_bot.base + MANUALS)
    expect(page.locator("#demo-mode")).to_contain_text("Demo mode")
    expect(page.locator("#add-manual")).to_be_visible()
    scanned = tmp_path / "scanned.pdf"
    scanned.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Subtype/Image>>\nstream\n"
        + zlib.compress(bytes(4096))
        + b"\nendstream\n"
    )
    page.set_input_files("#manual", str(scanned))
    page.locator("#upload").click()
    page.wait_for_load_state()
    expect(page.locator("#upload-msg")).to_contain_text(
        "No readable text found in this PDF"
    )
    expect(page.locator("#manual-list")).not_to_contain_text("scanned.pdf")
    md = tmp_path / "treatment-table.md"
    md.write_text(TABLE_MD, encoding="utf-8")
    page.set_input_files("#manual", str(md))
    page.locator("#upload").click()
    page.wait_for_load_state()
    expect(page.locator("#upload-msg")).to_contain_text("Added treatment-table.md")
    expect(page.locator("#demo-manuals")).to_have_count(0)
    expect(page.locator("#manual-list")).to_contain_text("treatment-table.md")
    expect(page.locator("#manual-list")).not_to_contain_text("maple-espresso")
    page.goto(
        ready_bot.base
        + MANUALS
        + "?q="
        + urllib.parse.quote("can I clean the table with alcohol")
    )
    expect(page.locator("#results li").first).to_contain_text("Cleaning the upholstery")
    page.goto(ready_bot.base + MANUALS + "?q=" + urllib.parse.quote(QUERY))
    expect(page.locator("#results")).to_contain_text("Not in your manuals")
    resp = page.request.get(ready_bot.base + SEARCH)
    data = json.loads(resp.text())
    assert data["results"] == [] and data["demo_manuals"] is False
    assert not page.csp_errors, page.csp_errors
    assert not page.js_errors
