# Manuals Expert Bot

A small-business equipment clerk that answers from the manuals on the bot:
seeded demo docs plus any `.md` files you drop in `/data/manuals-expert/`.
One image, `/setup`, memory, allowlisted tools, and the Gold Valley Solutions
gold theme. It does not browse the web.

_Screenshot: first-boot `/setup` and the chat page after the self-test (this PR)._

## Up and running in 5 minutes

The core image `ghcr.io/goldvalleysolutions/core-bot` is private on GHCR. Create a GitHub
token with `read:packages`, then build this bot `FROM ghcr.io/goldvalleysolutions/core-bot:${CORE}`
(`CORE=0.3`, never `latest`) from the repo root (Docker or Colima, arm64 or amd64):

```bash
echo YOUR_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

git clone git@github.com:goldvalleysolutions/gvs-manuals-expert-bot.git
cd gvs-manuals-expert-bot
docker build -f bot/Dockerfile --build-arg CORE=0.3 -t manuals-expert-bot:dev .
docker run -d --name manuals-expert -p 8080:8080 -v manuals-expert-data:/data manuals-expert-bot:dev
```

The Dockerfile copies `bot/` to `/bot/` on top of the pinned core; no RUN steps.

Open <http://localhost:8080>. Every page redirects to **`/setup`** until you finish
it. Create the bot-admin login, leave the LLM on **stub** (no key, $0), then run
the self-test. `curl -f http://localhost:8080/health` works before and after setup.

There is no published image for this bot yet; build it locally as above.

That's it. Everything you enter stays in the `manuals-expert-data` volume on your
machine, with keys encrypted.

### Try it (stub, CI)

Do these on the running image. CI runs the walkthrough on amd64 and arm64.
Stub LLM only — no provider keys.

1. **`/setup`** — stub model, no LLM key. No tool credentials on this bot.
2. **Clock** — ask the time. `clock.now` runs and is logged.
3. **Search** — ask how to descale the Maple Espresso E-20. `search_manuals`
   returns the seeded page.
4. **REST** — `GET /r/manuals-expert/search?q=descale` returns the same hits.
5. **Web browse blocked** — ask it to search the web. The call is refused and
   logged `blocked` / `not_allowed`.
6. **Bot admin 404** — as bot admin, `/gvs/role`, `/gvs/skills`, `/gvs/memory`
   and `/gvs/activity` are 404.
7. **MCP** — MCP is **off** until you turn it on in **read only** and issue a
   token. An MCP client at `/mcp` can `ask`, `search`, `list_items`, and
   `search_manuals`. See [docs/mcp.md](../../docs/mcp.md).

## What it can do

- Answer from seeded (and owner-added) equipment manuals
- Tell the time (`clock.now`)
- Search the role store (`search_manuals`) and the matching REST route
- Remember facts across a container restart
- **Tools it's allowed to use:** `clock.now`, `search_manuals`. It refuses anything else.

## Prerequisites

| Item | Needed? | Where to get it | Cost |
|---|---|---|---|
| Docker | Yes | docker.com or Colima | Free |
| AI provider key (OpenRouter, OpenAI, xAI or Anthropic) | For real answers (the stub works without one) | The provider's website | Pay per use; see below |

Default spend cap is **$25/month**. At the cap the bot falls back to stub.

## Estimated monthly cost

You pay your AI provider directly. The bot itself is free. A spend cap
(**$25/month by default**, change it in admin) stops paid calls and falls back
to the stub when reached.

**Formula:** monthly cost ≈ chats per month × turns per chat × cost per turn × 1.1 (memory summaries).
**Cost per turn** ≈ (input tokens × input price) + (output tokens × output price). A typical turn for this bot: **~2,000** input + **~300** output tokens.

This role's `bot.yaml` profile is **10 chats/day** and **4 turns/chat**. On
the stub model that is **$0**.

| Usage (this role) | How often it runs | How chatty | Turns / month | Small model* | Mid model* |
|---|---|---|---|---|---|
| Light | 10 chats/day | 4 turns/chat | 1,200 | ~$1 | ~$14 |
| Typical | 40 chats/day | 6 turns/chat | 7,200 | ~$7 | ~$83 |
| Busy | 150 runs/day | 2 turns/run | 9,000 | ~$9 | ~$104 |

\*Example prices: small model $0.25 in / $1.25 out per million tokens (≈ $0.0009 per turn); mid model $3 / $15 (≈ $0.0105 per turn). Check your provider's current prices. Stub mode: $0. Hosting on your own machine: $0; managed hosting by Gold Valley Solutions is quoted separately.

## Admin

- **Bot admin** (you): AI provider, key and model; tool credentials; theme (name, logo, colors); spend cap; health.
- **You get bot admin; that's the top level for self-hosted bots.** Root (role, skills, memory, logs) is held by Gold Valley Solutions only and is never handed out. It needs a token signed by GVS, so GVS can only use it if you give GVS access to your bot (e.g. a setup or hosting engagement).

## Configuration

| Item | Where | Notes |
|---|---|---|
| Manifest | `bot/bot.yaml` | `make lint-bot BOT=<this repo>/bot (in gvs-core-bot)` |
| Role / skills | `role.md`, `skills/lookup/SKILL.md` | Seeded into `bot.db` on first boot |
| Tools | `tools/search.py` | `search_manuals` (read; chat + MCP) |
| REST | `services/search.py` | `GET /r/manuals-expert/search` |
| Manuals | `/data/manuals-expert/` | Role-owned store; core never writes here |
| Theme | `theme.yaml` | GVS gold/white/Inter defaults |
| Data | `/data/bot.db` + `/data/bot.key` | One SQLite DB; key is 0600 |
| Port | `8080` | Non-root user in the image |

Add your own manuals by copying `.md` files into the `manuals-expert-data`
volume under `manuals-expert/`. Search picks them up on the next query.

## Updates and backups

- Update: `rebuild `manuals-expert-bot:dev` (`git pull`, then the `docker build` above)`, then re-run the `docker run` with the same volume.
- Back up: copy the `manuals-expert-data` volume. It holds `bot.db`, `bot.key`, and `/data/manuals-expert/`; keep them together.

## FAQ

- **Working with health records?** When you run a project yourself, you choose an AI provider and host that fit your compliance needs. Our hosting and builds don't process patient health information.
- **Can it browse the web?** No. That is not on `tools_allowed` and a call is refused and logged.
- **Where do the manuals live?** In the role store `/data/manuals-expert/`. A tiny demo corpus is copied there on first search. The core SQLite DB is not used for the pages.
- **Does this bot send email?** No. It does not include `email.send` or SMTP.

## Help and paid services

Gold Valley Solutions offers paid **setup, configuration, training and hosting** for every bot. Setup and configuration cost the same for every bot.
See **Gold Valley Bots pricing:** https://www.goldvalleysolutions.com/pricing/gold-valley-bots.html

## License

Apache 2.0. See `LICENSE` and `NOTICE`. Powered by Gold Valley Solutions.

## End-to-end tests (Playwright)

`tests/e2e/` starts the bot on core from source (pinned to gvs-core-bot `a1a5b5d`) with
uvicorn, a temp `/data` and the stub model, then drives it in Chromium at desktop
(1280x800) and mobile (390x844) sizes. `verify-local.sh` runs it through
`.verify-local.env`, and it must pass before merge.

```bash
git clone https://github.com/goldvalleysolutions/gvs-core-bot.git ../gvs-core-bot
git -C ../gvs-core-bot checkout a1a5b5d
pip install -r ../gvs-core-bot/requirements.txt -r tests/e2e/requirements.txt
python -m playwright install chromium
GVS_CORE_DIR=../gvs-core-bot python -m pytest tests/e2e -q
```

When a test fails, a screenshot and a trace go to `tests/e2e/artifacts/` (gitignored).
Open the trace with `python -m playwright show-trace <file>.trace.zip`.
