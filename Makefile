# Manuals Expert Bot - build, lint, and stub walkthrough against bot-core.
CORE ?= 0.2
CORE_IMAGE ?= ghcr.io/goldvalleysolutions/bot-core:$(CORE)
IMAGE ?= ghcr.io/goldvalleysolutions/manuals-expert-bot:dev
STEPS ?= scripts/manuals-expert-steps.sh

.PHONY: build lint-bot steps

build:
	docker build --build-arg CORE=$(CORE) --build-arg IMAGE_TAG=$(IMAGE) -t $(IMAGE) .

lint-bot:
	docker run --rm \
		-e GVS_BOT_DIR=/bot \
		-v "$(CURDIR)/bot:/bot:ro" \
		"$(CORE_IMAGE)" \
		python -m core.config.lint /bot

steps:
	@if [ ! -f "$(STEPS)" ]; then \
		echo "error: $(STEPS) is missing" >&2; \
		exit 1; \
	fi; \
	"$(STEPS)" "$(IMAGE)"
