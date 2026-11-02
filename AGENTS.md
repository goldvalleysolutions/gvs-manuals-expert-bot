# AGENTS.md

## Bot architecture rules (review gate)

Source: dev-team standard bot-architecture.md (Mike, Nov 1 2026).

1. **One image per bot.** Each bot ships as a single Docker Hub image. No compose file, no sidecar services, no separate database server, no complex config.
2. **Pull and run.** The user's whole setup is `docker pull` then `docker run`. Nothing is needed beyond Docker running: no cloning, no building, no exotic setup.
3. **Built on Core.** Every bot is `FROM` the common Bot Core (gvs-core-bot) image.
4. **Core + job layer.** A bot adds only what its job needs: role prompt, skills, tools, and the third-party integrations its job requires. Anything generic (chat, approvals, memory, admin, scheduling, storage, logging) belongs in Core.
5. **Same shape everywhere.** All bots share the same structure and patterns (the `bot/` pack: role.md, bot.yaml, skills/, tools/, theme). There are no one-off architectures.

Every bot plan and PR must pass this gate. The gvs-factory review panel checks it.
