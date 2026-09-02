"""Create local Compose bundles for development and release testing."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from base64 import b64encode
from pathlib import Path
from typing import Sequence

import dns.resolver
import petname
import yaml
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from freva_deployment import __version__

from ..deploy import DeployFactory
from ..error import ConfigurationError
from ..logger import logger, set_log_level
from ..utils import RichConsole, asset_dir, config_dir
from ..versions import get_versions

COMPOSE_TASK = """---
- name: Render compose file locally only
  hosts: all
  connection: local
  gather_facts: false

  tasks:
    - name: Render the development Compose bundle
      template:
        src: {template_path}
        dest: {output_file}
      vars:
        deploy_web: {{ ({deploy_web}|int) != 0 }}
"""


def comment_entries(toml_str: str, entries_to_comment: Sequence[str]) -> str:
    """Comment selected list entries in TOML text.

    Parameters
    ----------
    toml_str : str
        TOML document to modify.
    entries_to_comment : Sequence[str]
        First values of list entries that should be commented.

    Returns
    -------
    str
        Modified TOML document.
    """
    lines = toml_str.splitlines()
    result: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        # If line starts with one of the target entries, comment it
        for entry in entries_to_comment:
            if re.match(rf'^\["{re.escape(entry)}",', stripped):
                indent = line[: len(line) - len(stripped)]
                result.append(f"{indent}#    {stripped}")
                break
        else:
            result.append(line)
    return "\n".join(result)


def _get_nameservers() -> str:
    """Return local IPv4 resolvers as a space-separated string."""
    nameservers = dns.resolver.Resolver().nameservers
    nameservers_list: Sequence[str] = (
        list(map(str, nameservers))
        if isinstance(nameservers, list)
        else [str(nameservers)]
    )
    return " ".join(
        s for s in nameservers_list if re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", s)
    )


def create_compose(args: argparse.Namespace) -> None:
    """Create a development-only Compose bundle.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.
    """
    set_log_level(args.verbose)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with DeployFactory(
        steps=None,
        config_file=args.config_file,
        secrets_file=args.secrets_file,
        local_debug=False,
        gen_keys=True,
    ) as DF:
        eval_config = DF.create_eval_config()
        if eval_config is None:
            raise ConfigurationError("Unable to create the Freva configuration")
        eval_conf_enc = b64encode(eval_config.read_text().encode()).decode()
        extra = {
            **{
                "eval_config_content": eval_conf_enc,
                "use_core": args.no_plugins is False,
                "uid": args.user,
                "redis_password": DF._create_random_passwd(30, 10),
                "redis_username": petname.generate(),
                "redis_version": get_versions()["redis"],
                "current_nameservers": " ".join(args.dns_nameservers or []),
                "ansible_python_interpreter": sys.executable,
                "data_loader_volumes": DF.cfg["freva_rest"].get("data_loader_volumes")
                or [],
            },
        }
        level = logger.getEffectiveLevel()
        logger.info("Parsing configurations")
        try:
            logger.setLevel(0)
            inventory = yaml.safe_load(DF.parse_config(DF.steps, **extra))
        finally:
            logger.setLevel(level)
        if args.no_plugins is True:
            web_config = base64.b64decode(
                inventory["web"]["vars"]["web_config_content"]
            ).decode()
            to_comment = ["Plugins", "History", "Result-Browser"]
            web_config = comment_entries(web_config, to_comment)
            inventory["web"]["vars"]["web_config_content"] = base64.b64encode(
                web_config.encode()
            ).decode()
            plugin_note = ""
        else:
            plugin_note = (
                "[b red]:bulb: NOTE:[/] If want to use plugins you"
                " should install the freva libraries via pip "
                "or conda:\n\n"
                "  [b]python -m pip install freva-client freva[/b] (or) \n"
                "  [b]conda -c conda-forge install freva-client freva [/b]\n\n"
                "You should then set the "
                "[b]EVALUATION_SYSTEM_CONFIG_FILE[/b] env variable "
                "for the [b]web-server[/b] section in the compose file to the "
                "config file that was installed by conda/pip - e.g\n\n  "
                "<base-path-to-python-env>/freva/"
                "evaluation_system.conf\n"
                "This path also needs to be mounted as a volume into the "
                "container.\n"
            )

        playbook = COMPOSE_TASK.format(
            output_file=json.dumps(str(output_dir / f"{DF.project_name}-compose.yml")),
            template_path=json.dumps(
                str(asset_dir / "playbooks/templates/service-compose.yml.j2")
            ),
            deploy_web=int(args.no_web is False),
        )
        web_conf = (
            Path(inventory["core"]["vars"]["core_root_dir"])
            / "share"
            / "freva"
            / "web"
            / "freva_web_config.toml"
        )
        for key in inventory:
            inventory[key]["hosts"] = "localhost"
        inventory["web"]["vars"]["web_config_file"] = str(web_conf)
        logger.debug(yaml.safe_dump(inventory))

        DF._td.run_ansible_playbook(
            working_dir=asset_dir / "playbooks",
            playbook=playbook,
            inventory=inventory,
            verbosity=args.verbose,
        )
        yml_file = output_dir / f"{DF.project_name}-compose.yml"
        config_path = (
            Path(inventory["core"]["vars"]["core_root_dir"])
            / "freva"
            / "web"
            / "freva_web.toml"
        )

        RichConsole.rule("")
        RichConsole.print(
            (
                f"The development Compose bundle ({yml_file}) was created. "
                "It is intended for local integration and release-candidate "
                "testing, not production deployment. Start it with:\n\n"
                f"  [b]podman compose -f {yml_file} up -d[/b]\n\n{plugin_note}"
                "The web config file will be located in the "
                f"[b]{config_path}[/b]. You can adjust its settings there "
                "and restart the bundle."
            )
        )


def compose_parser(
    epilog: str = "", parser: argparse.ArgumentParser | None = None
) -> None:
    """Construct the development Compose parser.

    Parameters
    ----------
    epilog : str, default=""
        Additional help text.
    parser : argparse.ArgumentParser or None, default=None
        Existing parser to configure.
    """
    parser = parser or argparse.ArgumentParser(
        prog="deploy-freva compose",
        description="Create a local Compose bundle for development testing.",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
        epilog=epilog,
    )
    parser.add_argument(
        "-v", "--verbose", action="count", help="Verbosity level", default=0
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=__version__),
    )
    parser.add_argument(
        "-c",
        "--config-file",
        type=Path,
        help="Path to ansible inventory file.",
        default=config_dir / "config" / "inventory.toml",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory receiving the generated Compose bundle.",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Do not deploy the web service.",
        default=False,
    )
    parser.add_argument(
        "-u",
        "--user",
        type=str,
        help="User name that should run the services inside the container.",
        default="root",
    )
    parser.add_argument(
        "--dns-nameservers",
        type=str,
        default=_get_nameservers().split(),
        nargs="+",
        help="Set dns nameserver entries for the nginx reverse proxy",
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="Do not setup core library to use plugins.",
    )
    parser.add_argument(
        "--secrets-file",
        "--secrets_file",
        "--secrets",
        type=Path,
        default=None,
        help="Set a secrets file to read sensitive variables from.",
    )
    parser.set_defaults(cli=create_compose)
