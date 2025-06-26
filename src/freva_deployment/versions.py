"""Define the version of the microservices."""

import argparse
import json
import os
import ssl
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import urlopen

from appdirs import user_cache_dir
from packaging.version import Version
from rich import print as pprint
from rich.prompt import Prompt

from .error import ConfigurationError, handled_exception

ssl_context = ssl._create_unverified_context()


class VersionAction(argparse._VersionAction):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string=None,
    ):
        version = self.version or "%(prog)s"
        pprint(version % {"prog": parser.prog or sys.argv[1]})
        parser.exit()


def display_versions() -> str:
    """Get all service versions for display."""
    minimum_version = get_versions()
    lookup = {
        "freva_rest": "freva-rest API",
        "core": "freva-core",
        "solr": "Apache Solr",
        "web": "webUI",
        "vault": "Freva Vault",
        "mongodb_server": "MongoDB",
        "db": "MySQL",
    }
    versions = ""
    for service, version in minimum_version.items():
        service_name = lookup.get(service, service)
        versions += f"\n   [b][green]{service_name}[/b][/green] {version}"
    return versions


@handled_exception
def get_versions(_versions: List[Dict[str, str]] = []) -> Dict[str, str]:
    """Read the neccesary versions of microservices."""
    if _versions:
        return _versions[0]
    version_file = Path(user_cache_dir("freva-deployment")) / "versions.json"
    now = datetime.now()
    service_version = json.loads(
        (Path(__file__).parent / "versions.json").read_text()
    )
    if (
        version_file.exists()
        and (
            now - datetime.fromtimestamp(version_file.stat().st_mtime)
        ).total_seconds()
        < 3600 * 1000
    ):
        versions = json.loads(version_file.read_text())
        versions.update(service_version)
        _versions.append(versions)
        return _versions[0]
    version_file.parent.mkdir(exist_ok=True, parents=True)
    _versions.append(
        json.loads((Path(__file__).parent / "versions.json").read_text())
    )
    url = (
        "https://raw.githubusercontent.com/freva-org/freva-service-config"
        "/refs/heads/main/{service}/requirements.txt"
    )

    for service in ("mongo", "solr", "nginx", "redis"):
        try:
            with urlopen(url.format(service=service), context=ssl_context) as res:
                text = res.read().decode()
        except Exception as error:
            raise ConfigurationError(
                f"Could not read version for service {service}: {error}"
            )
        for line in text.splitlines():
            if not line.startswith("#") and "=" in line:
                version = line.strip().split("=")[-1]
                _versions[0][service] = version
                break
    _versions[0]["mongodb_server"] = _versions[0].pop("mongo")
    version_file.write_text(json.dumps(_versions[0]))
    return _versions[0]


def get_steps_from_versions(detected_versions: Dict[str, str]) -> List[str]:
    """Decide on services the should be deployed, based on thier versions.

    Parameters
    ----------
    detected_versions: dict
        The versions that have been detected to be deployed.

    Returns
    -------
    list: A list of services that should be updated.
    """
    minimum_version = get_versions()
    steps = []
    for service in ("web", "vault", "freva_rest", "core"):
        if service == "vault":
            service_name = "db"
        else:
            service_name = service
        min_version = Version(minimum_version[service].strip("v"))
        version_str = detected_versions.get(service, "").strip("v").strip()
        if service == "web" and not version_str:
            continue
        version = Version(version_str or "0.0.0")
        if version < min_version:
            steps.append(service_name)
        elif version > min_version:
            # We do have a problem: an installed version has a higher version
            # the the defined minium version, possibly the deployment
            # software is outdated.
            if os.environ.get("INTERACTIVE_DEPLOY", "1"):
                answ = (
                    Prompt.ask(
                        f"The installed version for [green]{service}[/green] is higher"
                        " than the min. defined version.\nThere might be"
                        " a chance that the current deployment software"
                        " is outdated.\nIf you continue you will "
                        f"[b]downgrade[/b] [green]{service}[/green] from "
                        f"{version} to {min_version}. "
                        "\nDo you want to continue \\[y|N]"
                    ).lower()
                    or "n"
                )
            else:
                answ = "n"
            if answ[0] == "y":
                steps.append(service_name)
            else:
                raise SystemExit(1)
    return steps
