# syntax=docker/dockerfile:1
# Manuals Expert Bot = the pinned Bot Core image + this /bot folder. Copy-only, no RUN.
# Published as goldvalleysolutions/manuals-expert-bot:<version> (Docker Hub) on merge to main.
#   Build from the repo root: docker build -f bot/Dockerfile -t goldvalleysolutions/manuals-expert-bot:0.1.0 .
#   The base is goldvalleysolutions/core-bot:${CORE} on Docker Hub. Until it is published,
#   build gvs-core-bot locally and tag it with that name (no CORE_IMAGE override needed).
# CORE pins the core as X.Y (never latest); it must equal `core:` in bot.yaml.
# VERSION must equal `version:` in bot.yaml (tests/test_manuals.py checks it); /health shows it.
ARG CORE=0.3
ARG CORE_IMAGE=goldvalleysolutions/core-bot:${CORE}
FROM ${CORE_IMAGE}
ARG CORE=0.3
ARG VERSION=0.1.0
ARG IMAGE_TAG=goldvalleysolutions/manuals-expert-bot:${VERSION}
LABEL org.opencontainers.image.title="Manuals Expert Bot" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.base.name="goldvalleysolutions/core-bot:${CORE}"
ENV GVS_IMAGE_TAG=${IMAGE_TAG}
COPY bot/ /bot/
