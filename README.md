# Manuals Expert Bot

Ask your equipment manuals and get the page, not a guess.

## What it is

A small-business equipment clerk that answers only from the manuals you load
(Markdown or text PDF), cites the manual and section, and says "Not in your manuals"
instead of guessing. It does not browse the web. It is one Docker image built `FROM`
Gold Valley Bot Core (`goldvalleysolutions/core-bot:0.3`), adding the
`search_manuals` tool and a signed-in Manuals page at `/r/manuals-expert/`.

## Quick start

Only Docker is needed (Docker Desktop, Colima or Linux; amd64 or arm64):

```bash
docker pull goldvalleysolutions/manuals-expert-bot:0.1
docker run -d --name manuals-expert -p 8080:8080 -v manuals-expert-data:/data goldvalleysolutions/manuals-expert-bot:0.1
```

Open <http://localhost:8080> and complete setup (`/setup`: bot-admin password, who can
use the bot, AI model, self-test). `curl -f http://localhost:8080/health` works before
and after setup and shows the bot version. If host port 8080 is taken, change the left
side, e.g. `-p 8081:8080`.

Without an AI provider key the bot runs in demo mode (stub model, search results only,
demo coffee-shop manuals). Sign in, open <http://localhost:8080/r/manuals-expert/> and
use **Add a manual** to upload your own `.md` or `.pdf`, or copy a folder in:

```bash
docker cp ./my-manuals/. manuals-expert:/data/manuals-expert/
```

Full walkthrough: [bot/README.md](https://github.com/goldvalleysolutions/gvs-manuals-expert-bot/blob/main/bot/README.md).

## Configuration

| Item | Value | Notes |
|---|---|---|
| Port | `8080` (container) | Map with `-p <host>:8080` |
| Volume | `/data` | `bot.db` + `bot.key` (settings, encrypted keys, memory, chats, logs); back up both; delete the volume to start over |
| Your manuals | `/data/manuals-expert/` | `.md` and text `.pdf`, up to 10 MB each; upload in the browser or `docker cp` |
| AI provider key | `/setup` or **Admin > Settings** | Anthropic, OpenAI, xAI or OpenRouter; stored encrypted in `/data`. Core also reads `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `XAI_API_KEY` to preselect a provider |
| `GVS_TRUSTED_PROXIES` | optional (Core) | Comma-separated proxy IPs trusted for `X-Forwarded-Proto`; default `127.0.0.1,::1` |
| `GVS_LLM_MAX_TOKENS` | optional (Core) | Max reply tokens, 1-8192, default 1024 |

## Repo contents

| Path | What is in it |
|---|---|
| `bot/` | The bot pack copied onto Core: `Dockerfile`, `bot.yaml`, `role.md`, `skills/lookup/`, `tools/search.py`, `services/search.py` (Manuals page), `admin/`, `theme.yaml`, `demo/` (demo manuals) |
| `scripts/` | `verify-local.sh` (all local checks) and `manuals-expert-steps.sh` (walkthrough against a built image) with helpers |
| `tests/` | `unit/` (pytest), `e2e/` (Playwright, stub LLM), `fixtures/` |
| `.github/workflows/` | `publish.yml` (main-only Docker Hub publish), `dockerhub-description.yml` (Docker Hub overview from this README) |

## Build and test from source

The image is built on Core, pulled from Docker Hub (`goldvalleysolutions/core-bot:0.3`):

```bash
git clone https://github.com/goldvalleysolutions/gvs-manuals-expert-bot.git
cd gvs-manuals-expert-bot
docker build -f bot/Dockerfile -t goldvalleysolutions/manuals-expert-bot:0.1.0 .
scripts/verify-local.sh          # all checks; prints the Local verification block for the PR
```

The tests run this repo's `bot/` on Core from source. Point `GVS_CORE_DIR` at a
gvs-core-bot checkout at the pinned `CORE_SHA` (in `tests/e2e/conftest.py`) with its
requirements installed, or leave it unset and the e2e suite clones it into `.e2e/core`:

```bash
python -m pip install -r "$GVS_CORE_DIR/requirements.txt" -r tests/e2e/requirements.txt
python -m pytest tests/unit -q
python -m pytest tests/e2e -q -p no:cacheprovider
scripts/manuals-expert-steps.sh goldvalleysolutions/manuals-expert-bot:0.1.0   # walkthrough on the built image
```

Validate the manifest from a gvs-core-bot checkout: `make lint-bot BOT=<path to this repo>/bot`.

## Versioning and releases

PRs go to `test`; only Mike merges `test` into `main`. A merge to `main` publishes
`goldvalleysolutions/manuals-expert-bot` as `X.Y.Z` and `X.Y` (never `latest`), creates
GitHub release `vX.Y.Z`. A README change merged to `main` updates this Docker Hub description (`dockerhub-description.yml`). The version is
`version:` in `bot/bot.yaml`; the Core pin is `core:` there and `ARG CORE` in `bot/Dockerfile`.

## License

Apache License 2.0 (declared in the image labels). Core: [gvs-core-bot LICENSE](https://github.com/goldvalleysolutions/gvs-core-bot/blob/main/LICENSE).
