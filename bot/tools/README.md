Custom tools for this bot (0–3 `*.py` files), registered through `core.sdk`.

`search_manuals` (read, chat + MCP) looks up the role-owned manuals under
`/data/manuals-expert/`. The matching REST route is
`GET /r/manuals-expert/search` in `services/`; both call the same function in
`tools/search.py`. The allowlist is `clock.now` and `search_manuals`.
Web browsing is not allowed and is refused + logged as `blocked`.
