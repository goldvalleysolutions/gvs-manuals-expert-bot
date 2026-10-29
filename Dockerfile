# syntax=docker/dockerfile:1
# Manuals Expert Bot: pinned bot-core + this bot folder.
# Copy-only: no RUN that changes core. CORE pins bot-core as X.Y (never latest)
# and must equal `core:` in bot.yaml. Published 0.2 includes sha-922f8dc.
ARG CORE=0.2
FROM ghcr.io/goldvalleysolutions/bot-core:${CORE}
ARG CORE
ARG IMAGE_TAG=ghcr.io/goldvalleysolutions/manuals-expert-bot:dev
LABEL org.opencontainers.image.title="Manuals Expert Bot" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="bot-core:${CORE}" \
      org.opencontainers.image.ref.name="${IMAGE_TAG}"
ENV GVS_IMAGE_TAG=${IMAGE_TAG} \
    GVS_BOT_DIR=/bot
COPY bot/ /bot/
