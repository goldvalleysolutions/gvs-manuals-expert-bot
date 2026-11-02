Custom tools for this bot (0–3 `*.py` files), registered through `core.sdk`.

`search_manuals` (read, chat + MCP) searches the owner's manuals under
`/data/manuals-expert/` (`.md` and `.pdf`). Until the owner adds one, it searches the
demo coffee-shop set in `demo/manuals/`; after that the demo set is excluded. Manual
text is cleaned and fenced as untrusted data. Anonymous chat visitors are asked to sign in.
The signed-in pages in `services/` (`/r/manuals-expert/`, `/search`, `/upload`) call the
same functions. The allowlist is `clock.now` and `search_manuals`.
Web browsing is not allowed and is refused + logged as `blocked`.
