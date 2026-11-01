# Manuals Expert Bot

Ask your manuals, get the page, not a guess. A small-business equipment clerk that
answers only from the manuals you load (Markdown or PDF), cites the manual and
section, and says "Not in your manuals" instead of guessing. One Docker image,
built on Gold Valley Bot Core. It does not browse the web.

## Up and running in 5 minutes

Step 1 needs only Docker (Docker Desktop, Colima or Linux; amd64 or arm64):

```bash
docker pull goldvalleysolutions/manuals-expert-bot:0.1.0
docker run -d --name manuals-expert -p 8085:8080 -v manuals-expert-data:/data goldvalleysolutions/manuals-expert-bot:0.1.0
```

No clone, no build, no compose, no login to any registry. (Port 8085 on your machine
is just an example.) **If port 8085 is taken** (`port is already allocated`), run
`docker rm manuals-expert` and repeat with another left side, e.g. `-p 8095:8080`, then
use that port in the links below.

> **Before the 0.1 release:** the image appears on Docker Hub when Manuals 0.1 is
> released (after Bot Core 0.3). Until then `docker pull` fails; build both images
> locally under the published names, then run the same `docker run` line:
>
> ```bash
> git clone https://github.com/goldvalleysolutions/gvs-core-bot.git
> docker build -t goldvalleysolutions/core-bot:0.3 gvs-core-bot
> git clone https://github.com/goldvalleysolutions/gvs-manuals-expert-bot.git
> cd gvs-manuals-expert-bot
> docker build -f bot/Dockerfile -t goldvalleysolutions/manuals-expert-bot:0.1.0 .
> ```

Step 2: open <http://localhost:8085>. Every page redirects to **`/setup`** until you
finish it: create the bot-admin password, choose who can use the bot, pick the AI
model, then run the self-test. `curl -f http://localhost:8085/health` works before and
after setup and shows the bot version (`"bot": {"version": "0.1.0"}`).

### Demo mode vs. real answers

**Real answers need your own AI provider key** (Anthropic, OpenAI, xAI or
OpenRouter). You pay the provider directly; the bot itself is free.

Without a key the bot runs in **demo mode**: the model is the built-in stub ($0),
the Manuals page shows a **Demo mode** label, and you get search results (manual,
section and the matching text), not written answers. A small set of demo coffee-shop
manuals is loaded so you can try it right away. Add a key any time in
**Admin > Settings**; new setups get the current default model for your provider from
Bot Core, so you do not need to know model names.

### Sign in to search

Searching the manuals always needs an account, even when chat is open to "Anyone":
the bot admin, or a user you add under **Admin > Users**. Logged out, the search
endpoint answers `401` and the Manuals page says "Sign in to search your manuals."
with a link to `/login`. There is no public
search endpoint.

### Load your manuals (.md or .pdf)

As soon as you add one manual of your own, the demo coffee-shop manuals drop out of
every result.

- **Find it:** the Manuals page is <http://localhost:8085/r/manuals-expert/>. Every
  manual search result the model receives ends with "Browse or add manuals:
  /r/manuals-expert/", and the bot is told to end its answers with that line (most
  answers do; it is a model instruction, not a guarantee). **Admin > Settings** always
  shows a Manuals pointer.
- **Upload in the browser:** sign in as bot admin and open
  <http://localhost:8085/r/manuals-expert/> > **Add a manual**. Markdown (`.md`) or text PDF
  (`.pdf`), up to 10 MB each.
- **Or copy files in with Docker** (for a folder of files):

  ```bash
  docker cp ./my-manuals/. manuals-expert:/data/manuals-expert/
  ```

  Search picks them up on the next question; no restart needed. They live in the
  `manuals-expert-data` volume with everything else.

PDFs must contain real text: a scanned (image-only) PDF or an unsupported text
encoding is refused at upload with "No readable text found in this PDF (scanned or
unsupported encoding)." PDF text comes from Core's `core.pdf` (a separate process
with a 5 s timeout and memory limits); its refusals are shown as-is, for example
"Could not read 'x.pdf': it is too large or complex to process. Try a smaller file, or
split it into parts." Text PDFs from LibreOffice, Word and similar tools (embedded
subset fonts with a ToUnicode map) are read. Any
file that would give nothing searchable (0 sections indexed) is refused at upload
with "<file>: no searchable text found in this file (0 sections indexed), so it was
not added." A file copied in with `docker cp` that indexes to nothing is skipped and
logged as a warning (`docker logs manuals-expert`).

Manual text is treated as **untrusted reference data**. Excerpts reach the model
fenced as quoted reference text, never as instructions, and the role tells it never
to follow directions written inside a manual. A best-effort filter also strips HTML
and blanks some instruction-like lines, but it will not catch every phrasing, so do
not rely on it alone; only add manuals you trust.

### Try it

1. **`/setup`**: leave the model on **stub** for demo mode.
2. **Manuals page**: sign in and open `/r/manuals-expert/`. You see the **Demo mode**
   label. Search "descale espresso": the Maple Espresso E-20 > Descale section.
3. **Not in your manuals**: search "warranty period". You get "Not in your manuals".
4. **Your own manual**: upload one. The demo manuals disappear from the list and results.
5. **Chat**: with a key set, ask a question in chat; the bot calls `search_manuals`
   and cites the manual. Logged-out chat visitors are asked to sign in before searching.
6. **Web browse blocked**: ask it to search the web. The call is refused and logged.
7. **MCP**: off until the bot admin turns it on (read only) and issues a token.
   An MCP client at `/mcp` can `ask`, `search`, `list_items` and `search_manuals`.

## What it can do

- Answer from your equipment manuals (.md and PDF), citing manual and section
- Say "Not in your manuals" when nothing relevant matches
- Tell the time (`clock.now`)
- Search the manuals (`search_manuals`) in chat and MCP, and on the signed-in Manuals page
- Remember facts across a container restart
- **Tools it's allowed to use:** `clock.now`, `search_manuals`. It refuses anything else.

## Prerequisites

| Item | Needed? | Where to get it | Cost |
|---|---|---|---|
| Docker | Yes | docker.com or Colima | Free |
| AI provider key (Anthropic, OpenAI, xAI or OpenRouter) | For real answers (without one: demo mode, search results only) | The provider's website | Pay per use; see below |

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
| Pages | `services/search.py` | `/r/manuals-expert/` (Manuals page + upload), `/search` (JSON); sign-in required |
| Demo manuals | `demo/manuals/` | In the image; used only until you add your own |
| Your manuals | `/data/manuals-expert/` | `.md` and `.pdf`; upload or `docker cp` |
| Theme | `theme.yaml` | GVS gold/white/Inter defaults |
| Data | `/data/bot.db` + `/data/bot.key` | One SQLite DB; key is 0600 |
| Port | `8080` inside the container | Map it with `-p <host-port>:8080`; non-root user |

Add your own manuals with the upload on the Manuals page or `docker cp` (see above).

## Updates and backups

- Update: `docker pull` the new tag, `docker rm -f manuals-expert`, then the same `docker run` with the new tag and the same volume.
- Back up: copy the `manuals-expert-data` volume. It holds `bot.db`, `bot.key`, and `/data/manuals-expert/`; keep them together.

## FAQ

- **Working with health records?** When you run a project yourself, you choose an AI provider and host that fit your compliance needs. Our hosting and builds don't process patient health information.
- **Can it browse the web?** No. That is not on `tools_allowed` and a call is refused and logged.
- **Where do the manuals live?** Yours: `/data/manuals-expert/` in the volume. The demo coffee-shop set ships inside the image and is ignored once you add one of your own.
- **Does this bot send email?** No. It does not include `email.send` or SMTP.

## Help and paid services

Gold Valley Solutions offers paid **setup, configuration, training and hosting** for every bot. Setup and configuration cost the same for every bot.
See **Gold Valley Bots pricing:** https://www.goldvalleysolutions.com/pricing/gold-valley-bots.html

## License

Apache 2.0. See `LICENSE` and `NOTICE`. Powered by Gold Valley Solutions.

## For developers: build and test

The image is `FROM goldvalleysolutions/core-bot:0.3` (Docker Hub) plus this `bot/` folder,
copy-only. Build: `docker build -f bot/Dockerfile -t goldvalleysolutions/manuals-expert-bot:0.1.0 .`
Publishing: `.github/workflows/publish.yml` pushes `goldvalleysolutions/manuals-expert-bot`
as `X.Y.Z` and `X.Y` (from `version:` in `bot/bot.yaml`, never `latest`; linux/amd64 + linux/arm64)
only on push to `main`, i.e. when test is merged into main. It needs the `DOCKERHUB_USERNAME`
and `DOCKERHUB_TOKEN` secrets and fails naming any that is missing. A manual run is a build-only dry run.
Unit tests: `GVS_CORE_DIR=<core checkout> python -m pytest tests/unit`.
All checks: `GVS_E2E_REQUIRED=1 scripts/verify-local.sh`.

## End-to-end tests (Playwright)

`tests/e2e/` starts the bot on core from source (pinned to gvs-core-bot `a04a736`) with
uvicorn, a temp `/data` and the stub model, then drives it in Chromium at desktop
(1280x800) and mobile (390x844) sizes. `verify-local.sh` runs it through
`.verify-local.env`, and it must pass before merge.

```bash
git clone https://github.com/goldvalleysolutions/gvs-core-bot.git ../gvs-core-bot
git -C ../gvs-core-bot checkout a04a736
pip install -r ../gvs-core-bot/requirements.txt -r tests/e2e/requirements.txt
python -m playwright install chromium
GVS_CORE_DIR=../gvs-core-bot python -m pytest tests/e2e -q
```

When a test fails, a screenshot and a trace go to `tests/e2e/artifacts/` (gitignored).
Open the trace with `python -m playwright show-trace <file>.trace.zip`.
