"""Typed configuration primitives for Freva deployments."""

from __future__ import annotations

import warnings
from enum import Enum

from .error import ConfigurationError


class LegacyDeploymentMethodWarning(FutureWarning):
    """Warn that a legacy deployment method was migrated automatically."""


class DeploymentMethod(str, Enum):
    """Supported service deployment methods.

    The core client is always installed from conda-forge. This value controls
    how the Freva services are deployed.
    """

    QUADLET = "quadlet"
    CONDA = "conda"
    KUBERNETES = "k8s"

    @classmethod
    def from_config(cls, value: object) -> DeploymentMethod:
        """Parse and migrate a configured deployment method.

        Parameters
        ----------
        value : object
            Value read from the deployment configuration.

        Returns
        -------
        DeploymentMethod
            The normalized deployment method.

        Raises
        ------
        ConfigurationError
            If the value selects Docker or is otherwise unsupported.
        """
        if value == "podman":
            warnings.warn(
                "deployment_method='podman' is deprecated and now means "
                "'quadlet'. Update the configuration file.",
                LegacyDeploymentMethodWarning,
                stacklevel=2,
            )
            return cls.QUADLET
        if value == "docker":
            raise ConfigurationError(
                "deployment_method='docker' is no longer supported. "
                "Install Podman with Quadlet support and set "
                "deployment_method='quadlet'."
            )
        if not isinstance(value, str):
            raise ConfigurationError(
                "deployment_method must be one of: "
                f"{', '.join(method.value for method in cls)}"
            )
        try:
            return cls(value)
        except ValueError as error:
            valid = ", ".join(method.value for method in cls)
            raise ConfigurationError(
                f"Deployment method '{value}' is invalid. Choose one of: {valid}"
            ) from error
