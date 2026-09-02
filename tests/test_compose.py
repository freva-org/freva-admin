"""Tests for local development Compose generation."""

from __future__ import annotations

import json

import yaml

from freva_deployment.cli._compose import COMPOSE_TASK


def test_compose_playbook_is_strictly_local() -> None:
    """Keep Compose generation independent from remote deployment hosts."""
    playbook = yaml.safe_load(
        COMPOSE_TASK.format(
            output_file=json.dumps("/tmp/freva demo/demo-compose.yml"),
            template_path=json.dumps("/tmp/freva assets/service-compose.yml.j2"),
            deploy_web=1,
        )
    )

    assert playbook[0]["hosts"] == "all"
    assert playbook[0]["connection"] == "local"
    assert playbook[0]["gather_facts"] is False
    assert playbook[0]["tasks"][0]["template"]["dest"] == (
        "/tmp/freva demo/demo-compose.yml"
    )


def test_compose_playbook_does_not_install_a_runtime() -> None:
    """Prevent the development command from becoming a deployment path."""
    lowered = COMPOSE_TASK.lower()

    assert "systemd" not in lowered
    assert "docker" not in lowered
    assert "ssh" not in lowered
