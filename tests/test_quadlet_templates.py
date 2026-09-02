"""Tests for the generic Quadlet templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

TEMPLATE_DIR = (
    Path(__file__).parents[1]
    / "assets"
    / "share"
    / "freva"
    / "deployment"
    / "playbooks"
    / "templates"
)
PLAYBOOK_DIR = TEMPLATE_DIR.parent


def _as_bool(value: object) -> bool:
    """Convert a template value to a Boolean.

    Parameters
    ----------
    value : object
        Value passed through Ansible's ``bool`` filter.

    Returns
    -------
    bool
        Truth value of ``value``.
    """
    return bool(value)


def _render(template_name: str, **context: object) -> str:
    """Render one deployment template with strict variables.

    Parameters
    ----------
    template_name : str
        Template filename relative to ``TEMPLATE_DIR``.
    **context : object
        Values supplied to the Jinja template.

    Returns
    -------
    str
        Rendered Quadlet source.
    """
    environment = Environment(
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    environment.filters["bool"] = _as_bool
    template = environment.from_string(
        (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    )
    return template.render(**context)


def test_container_template_renders_quadlet_dependencies() -> None:
    """Render dependencies, secrets, ports, and volumes as Quadlet keys."""
    item: dict[str, object] = {
        "name": "freva-web",
        "description": "Freva web application",
        "image": "quay.io/freva/web:latest",
        "requires": ["freva-cache"],
        "environment": {"TOKEN": "secret"},
        "network": "freva-web",
        "network_aliases": ["web"],
        "ports": ["8000:8000"],
        "volumes": ["/var/lib/freva/demo/web:/data:z"],
    }

    rendered = _render(
        "freva.container.j2",
        item=item,
        quadlet_env_dir="/etc/freva/demo/env",
        quadlet_wanted_by="multi-user.target",
    )

    assert "After=freva-cache.container" in rendered
    assert "Requires=freva-cache.container" in rendered
    assert "EnvironmentFile=/etc/freva/demo/env/freva-web.env" in rendered
    assert "EnvironmentFile=/etc/freva/demo/env/freva-web.local.env" in rendered
    assert "Network=freva-web.network" in rendered
    assert "PublishPort=8000:8000" in rendered
    assert "Volume=/var/lib/freva/demo/web:/data:z" in rendered
    assert "WantedBy=multi-user.target" in rendered


def test_network_template_uses_a_stable_name() -> None:
    """Keep an explicit Podman network name in generated Quadlet sources."""
    network = _render(
        "freva.network.j2",
        item={"name": "freva-web", "driver": "bridge", "ipv6": True},
    )
    assert "NetworkName=freva-web" in network
    assert "IPv6=true" in network


def test_environment_template_is_deterministic() -> None:
    """Sort environment keys to avoid noisy deployment diffs."""
    rendered = _render(
        "quadlet.env.j2",
        item={"environment": {"Z_LAST": "z", "A_FIRST": "a"}},
    )

    assert rendered.index("A_FIRST=a") < rendered.index("Z_LAST=z")


def test_local_environment_template_documents_operator_ownership() -> None:
    """Render initial values for the environment file Ansible preserves."""
    rendered = _render(
        "quadlet.local.env.j2",
        item={"local_environment": {"FREVA_MAINTENANCE_MODE": "0"}},
    )

    assert "not overwritten" in rendered
    assert "FREVA_MAINTENANCE_MODE=0" in rendered


def test_quadlet_paths_use_fixed_state_and_xdg_defaults() -> None:
    """Keep persistent state independent from the TOML data path."""
    path_tasks = (PLAYBOOK_DIR / "tasks" / "set_deployment_paths.yml").read_text(
        encoding="utf-8"
    )

    assert "/var/lib/freva/" in path_tasks
    assert "/etc/freva/" in path_tasks
    assert "/.local/state/freva/" in path_tasks
    assert "/.config/freva/" in path_tasks


def test_service_quadlets_use_bind_mounts_instead_of_named_volumes() -> None:
    """Prevent persistent service data from returning to Podman storage."""
    roles = (
        "cache",
        "database",
        "freva-rest",
        "mongodb_server",
        "search_server",
        "vault",
        "web",
    )

    for role in roles:
        tasks = (
            PLAYBOOK_DIR / "roles" / role / "tasks" / "quadlet-deployment.yml"
        ).read_text(encoding="utf-8")
        assert ".volume:" not in tasks
        assert "service_state_dir" in tasks
