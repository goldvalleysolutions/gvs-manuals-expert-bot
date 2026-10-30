"""Access policy (core 'Who can use this bot?'), desktop + mobile.

Anyone: chat and the bot's user pages open logged out. Signed-in users only: they
redirect to /login, then open after a bot user signs in. No CSP console errors.
Kept identical across the bot repos; the pages come from ``bot_profile.BOT_PAGES``.
"""

from __future__ import annotations

import re

from bot_profile import BOT_PAGES, HTTP_SETUP  # noqa: F401  (HTTP_SETUP read by ready_bot)
from playwright.sync_api import Page, expect
from ui import USER, USER_PASSWORD, admin_web, user_login

PATHS = ["/", *BOT_PAGES]


def test_anyone_opens_logged_out(page: Page, ready_bot) -> None:
    admin_web(ready_bot.base).set_policy("anyone")
    for path in PATHS:
        resp = page.goto(ready_bot.base + path)
        assert resp.status == 200, (path, resp.status)
        assert "/login" not in page.url, path
    assert not page.csp_errors, page.csp_errors
    assert not page.js_errors


def test_signed_in_redirects_then_user_opens(page: Page, ready_bot) -> None:
    admin = admin_web(ready_bot.base)
    admin.set_policy("signed_in")
    admin.add_user(USER, USER_PASSWORD)
    try:
        for path in PATHS:
            page.goto(ready_bot.base + path)
            expect(page).to_have_url(re.compile(r"/login(\?next=|$)"))
        page.goto(ready_bot.base + PATHS[-1])
        user_login(page)
        for path in PATHS:
            resp = page.goto(ready_bot.base + path)
            assert resp.status == 200 and "/login" not in page.url, (path, resp.status)
        assert not page.csp_errors, page.csp_errors
        assert not page.js_errors
    finally:
        admin.set_policy("anyone")
