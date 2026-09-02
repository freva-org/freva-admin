"""Tests for typed deployment configuration primitives."""

from __future__ import annotations

import warnings

import pytest

from freva_deployment.config import (
    DeploymentMethod,
    LegacyDeploymentMethodWarning,
)
from freva_deployment.error import ConfigurationError


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("quadlet", DeploymentMethod.QUADLET),
        ("conda", DeploymentMethod.CONDA),
        ("k8s", DeploymentMethod.KUBERNETES),
    ],
)
def test_supported_deployment_method(
    configured: str, expected: DeploymentMethod
) -> None:
    """Parse every supported deployment method."""
    assert DeploymentMethod.from_config(configured) is expected


def test_podman_is_migrated_to_quadlet() -> None:
    """Keep old Podman configurations usable during the migration period."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        method = DeploymentMethod.from_config("podman")

    assert method is DeploymentMethod.QUADLET
    assert len(caught) == 1
    assert caught[0].category is LegacyDeploymentMethodWarning


@pytest.mark.parametrize("configured", ["docker", "compose", "", None, 1])
def test_unsupported_deployment_method(configured: object) -> None:
    """Reject deployment methods without an implementation."""
    with pytest.raises(ConfigurationError):
        DeploymentMethod.from_config(configured)
