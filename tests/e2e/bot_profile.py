"""This bot's pages and HTTP setup for the shared e2e tests (test_access_policy.py).

The manuals pages under /r/manuals-expert/ always need a signed-in account (even under
the Anyone policy), so they are not "open logged out" pages; test_manuals_expert.py
covers them (401 logged out, login, demo label, upload).
"""

BOT_PAGES: list[str] = []
HTTP_SETUP: dict = {}
