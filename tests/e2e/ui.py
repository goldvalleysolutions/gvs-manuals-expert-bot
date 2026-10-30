"""UI helpers for the e2e suite: drive pages the way a person does."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

ADMIN_PASSWORD = "secret12"


def setup_ui(
    page: Page,
    base: str,
    smtp: dict[str, str] | None = None,
    wizard: dict[str, str] | None = None,
) -> list[str]:
    """Walk /setup through the browser; returns the step names seen."""
    page.goto(base + "/setup")
    seen: list[str] = []
    for _ in range(8):
        step_input = page.locator("form input[name=step]")
        if step_input.count() == 0:
            break
        step = step_input.first.get_attribute("value") or ""
        seen.append(step)
        form = page.locator("form", has=page.locator(f"input[name=step][value={step}]"))
        if step == "bot_admin":
            form.locator("#password").fill(ADMIN_PASSWORD)
            form.locator("#email").fill("admin@example.com")
        elif step == "model":
            form.locator("#provider").select_option("stub")
            form.locator("#test-model").click()
            page.wait_for_load_state()
            form = page.locator(
                "form", has=page.locator("input[name=step][value=model]")
            )
            expect(form.locator("#save-model")).to_be_enabled()
            form.locator("#save-model").click()
            page.wait_for_load_state()
            continue
        elif step == "connectors":
            for name, value in (smtp or {}).items():
                form.locator(f"[name={name}]").fill(value)
        elif step == "wizard":
            for name, value in (wizard or {}).items():
                form.locator(f"[name={name}]").fill(value)
        form.locator("button:not([type=button])").last.click()
        page.wait_for_load_state()
        if step == "self_test":
            break
    return seen


def chat(page: Page, text: str) -> Locator:
    """Send one chat message from the visitor's view; return the reply bubble's <li>."""
    replies = page.locator("li.msg.bot:not(.thinking)")
    before = replies.count()
    page.fill("#chat-form textarea", text)
    page.locator("#chat-send").click()
    page.wait_for_function(
        "n => document.querySelectorAll('li.msg.bot:not(.thinking)').length > n"
        " && !document.querySelector('li.msg.thinking')",
        arg=before,
        timeout=20000,
    )
    return replies.last


def admin_login(page: Page, base: str) -> None:
    page.goto(base + "/admin/login")
    page.fill("#password", ADMIN_PASSWORD)
    page.locator("form button:not([type=button])").last.click()
    page.wait_for_load_state()
    expect(page).to_have_url(re.compile(r"/admin(\?|$)"))


def mcp_initialize(base: str, token: str) -> dict:
    """Raw MCP ``initialize`` over streamable HTTP; returns the JSON-RPC result."""
    import json
    import urllib.request

    req = urllib.request.Request(
        base + "/mcp/",
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e", "version": "1"},
                },
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode()
    for line in body.splitlines():
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    return json.loads(body)["result"]


def admin_web(base: str):
    """An HTTP admin session (forms + CSRF) for setting up MCP tokens."""
    from steps_web import Web

    web = Web(base)
    web.admin_login()
    return web
