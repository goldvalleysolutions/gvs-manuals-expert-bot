"""Publish workflow guardrails: main-only push, dispatch never pushes, no latest, no GHCR,
both Docker Hub secrets named, version read from bot/bot.yaml."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
WF = REPO / ".github" / "workflows" / "publish.yml"
TEXT = WF.read_text()
DOC = yaml.safe_load(TEXT)
ON = DOC.get("on", DOC.get(True))  # PyYAML parses bare `on:` as True
STEPS = DOC["jobs"]["publish"]["steps"]


def test_triggers_main_only_plus_dispatch() -> None:
    assert set(ON) == {"push", "workflow_dispatch"}
    assert ON["push"]["branches"] == ["main"]
    assert {"docs/**", "**/*.md"} <= set(ON["push"]["paths-ignore"])
    assert "pull_request" not in ON and "tags" not in ON["push"]


def test_dispatch_never_pushes() -> None:
    mode = next(s for s in STEPS if s.get("id") == "mode")["run"]
    assert '"$EVENT" != "push" || "$REF" != "refs/heads/main"' in mode
    dispatch_branch = mode.split("fi", 1)[0]
    assert "push=false" in dispatch_branch and "push=true" not in dispatch_branch
    for s in STEPS:
        w = s.get("with") or {}
        if w.get("push") is True:
            assert s["if"] == "steps.mode.outputs.push == 'true'"


def test_no_latest_no_ghcr_no_variables() -> None:
    # Header comments may say "no GHCR"; check the workflow itself.
    low = "\n".join(
        ln for ln in TEXT.lower().splitlines() if not ln.lstrip().startswith("#")
    )
    assert ":latest" not in low and "type=raw,value=latest" not in low
    for s in STEPS:
        assert "latest" not in str((s.get("with") or {}).get("tags", ""))
    assert "ghcr" not in low and "publish_enabled" not in low and "vars." not in low
    assert DOC["permissions"] == {"contents": "read"}
    assert DOC["jobs"]["publish"]["permissions"] == {"contents": "write"}
    assert "goldvalleysolutions/manuals-expert-bot" in TEXT


def test_both_secrets_named_in_preflight() -> None:
    mode = next(s for s in STEPS if s.get("id") == "mode")["run"]
    for name in ("DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN"):
        assert f'missing+=("{name}")' in mode
    assert "::error" in mode and "exit 1" in mode


def test_actions_pinned_by_sha_and_multiarch() -> None:
    for s in STEPS:
        if "uses" in s:
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", s["uses"]), s["uses"]
    builds = [s for s in STEPS if "build-push-action" in s.get("uses", "")]
    assert builds
    for b in builds:
        w = b["with"]
        assert w["platforms"] == "linux/amd64,linux/arm64"
        assert w["context"] == "." and w["file"] == "bot/Dockerfile"
        for arg in ("CORE=", "VERSION=", "IMAGE_TAG="):
            assert arg in w["build-args"]


def test_version_comes_from_bot_yaml() -> None:
    assert "bot/bot.yaml" in next(s for s in STEPS if s.get("id") == "version")["run"]
    assert re.search(
        r"^version:\s*\d+\.\d+\.\d+",
        (REPO / "bot" / "bot.yaml").read_text(),
        re.MULTILINE,
    )


def test_github_release_only_on_publish_with_image_tags() -> None:
    rel = next(s for s in STEPS if s.get("name") == "Create GitHub release")
    assert rel["if"] == "steps.mode.outputs.push == 'true'"
    run = rel["run"]
    assert 'gh release create "v$VERSION"' in run
    assert "$IMAGE:$VERSION" in run and "$IMAGE:$MINOR" in run
    assert ":latest" not in run
    mode = next(s for s in STEPS if s.get("id") == "mode")["run"]
    assert 'gh release view "$TAG"' in mode


def test_dockerhub_description_workflow_is_single_owner() -> None:
    path = REPO / ".github" / "workflows" / "dockerhub-description.yml"
    text = path.read_text()
    wf = yaml.safe_load(text)
    on = wf[True]
    assert set(on) == {"push", "workflow_dispatch"}
    assert on["push"]["branches"] == ["main"]
    assert set(on["push"]["paths"]) == {
        "README.md",
        ".github/workflows/dockerhub-description.yml",
    }
    assert wf["permissions"] == {"contents": "read"}
    assert (
        "DOCKERHUB_USERNAME" in text and "DOCKERHUB_TOKEN" in text and "exit 1" in text
    )
    assert "readme-filepath: ./README.md" in text
    uses = [s["uses"] for j in wf["jobs"].values() for s in j["steps"] if "uses" in s]
    assert any(u.startswith("peter-evans/dockerhub-description@") for u in uses)
    for u in uses:
        assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u), u
    assert "dockerhub-description" not in TEXT
