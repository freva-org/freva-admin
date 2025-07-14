"""Command line interface for creating compose files."""

from __future__ import annotations

import argparse
import base64
import json
from base64 import b64encode
from pathlib import Path
from typing import Optional

import namegenerator
import yaml
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from freva_deployment import __version__

from ..deploy import DeployFactory
from ..logger import logger, set_log_level
from ..utils import RichConsole, asset_dir, config_dir

COMPOSE_TASK = """---
- name: Render compose file locally only
  hosts: all
  connection: local
  gather_facts: no

  tasks:
    - name: Template out docker-compose.yml
      template:
        src: {asset_dir}/playbooks/templates/service-compose.yml.j2
        dest: {pwd}/{project_name}-compose.yml
"""

SYSTEMD_TMPL = """
[Unit]
Description=Start/Stop freva services containers
After=network-online.target
Wants=network-online.target
[Service]
TimeoutStartSec=35s
TimeoutStopSec=35s
ExecStartPre=/usr/bin/env sh -c "{engine} compose --project-name {project_name} -f <compose-dir>/{project_name}-compose.yml down --remove-orphans"
ExecStart=/usr/bin/env sh -c "{engine} compose --project-name {project_name} -f <compose-dir>/{project_name}-compose.yml up --remove-orphans"
ExecStop=/usr/bin/env sh -c "{engine} compose --project-name {project_name} -f <compose-dir>/{project_name}-compose.yml down --remove-orphans"
Restart=on-failure
RestartSec=5
StartLimitBurst=5
[Install]
WantedBy=default.target

"""

import re


def comment_entries(toml_str, entries_to_comment):
    lines = toml_str.splitlines()
    result = []
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


def create_compose(args: argparse.Namespace) -> None:
    """Create a compose file."""
    set_log_level(args.verbose)
    with DeployFactory(
        steps=None,
        config_file=args.config_file,
        local_debug=False,
        gen_keys=True,
    ) as DF:

        eval_conf_enc = b64encode(
            DF.create_eval_config().read_text().encode()
        ).decode()
        extra = {
            "eval_config_content": eval_conf_enc,
            "use_core": args.no_plugins is False,
            "uid": args.user,
            "redis_password": DF._create_random_passwd(30, 10),
            "redis_username": namegenerator.gen(),
        }
        logger.info("Parsing configurations")
        inventory = yaml.safe_load(DF.parse_config(DF.steps, **extra))
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
                "[b]EVALUATIO_SYSTEM_CONFIG_FILE[/b] env varaiable "
                "for the [b]web-server[/b] section in the compose file to the "
                "config file that was installed by conda/pip - e.g\n\n  "
                "<base-path-to-python-env>/freva/"
                "evaluation_system.conf\n"
                "This path also needs to be mounted as a volume into the "
                "container.\n"
            )

        playbook = COMPOSE_TASK.format(
            pwd=Path.cwd(), project_name=DF.project_name, asset_dir=asset_dir
        )
        web_conf = (
            Path(inventory["core"]["vars"]["core_root_dir"])
            / "share"
            / "freva"
            / "web"
            / "freva_web.toml"
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
        yml_file = Path.cwd() / f"{DF.project_name}-compose.yml"
        service_file = yml_file.with_suffix(".service")
        config_path = (
            Path(inventory["core"]["vars"]["core_root_dir"])
            / "freva"
            / "web"
            / "freva_web.toml"
        )

        RichConsole.rule("")
        RichConsole.print(
            (
                f"The compose file ({yml_file.name}) has been created. "
                "You can copy the file to your server and start "
                f"the compose command.\n\n{plugin_note}"
                "The web config file will be located in the "
                f"[b]{config_path}[/b] you can ajust it's settings there and"
                " restart the compose."
            )
        )

        if args.systemd_service:

            service_file.write_text(
                SYSTEMD_TMPL.format(
                    project_name=DF.project_name, engine=args.container_engine
                )
            )
        RichConsole.print(
            (
                "\n\nA systemd service file was created. Set the path"
                " to the compose file on the server and place it "
                f"into [b]/etc/systemd/system/{service_file.name}[/]"
                "\n"
                "then use:\n\n"
                "  [b]sudo systemctl daemon-reload\n"
                f"  sudo systemctl enable --now {service_file.name}[/b]\n"
            )
        )


def compose_parser(
    epilog: str = "", parser: Optional[argparse.ArgumentParser] = None
) -> None:
    """Construct command line argument parser."""
    parser = parser or argparse.ArgumentParser(
        prog="deploy-freva-compose",
        description="Create and inspect freva configuration.",
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
        "--host",
        type=str,
        help="Host name where the compose service should be running.",
    )
    parser.add_argument(
        "-u",
        "--user",
        type=str,
        help="User name that should run the services insight the container.",
        default="root",
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="Do not setup core library to use plugins.",
    )
    parser.add_argument(
        "-e",
        "--container-engine",
        help="Create a compose file for docker or podman.",
        default="docker",
        choices=["docker", "podman"],
        type=str,
    )
    parser.add_argument(
        "-s",
        "--systemd-service",
        help="Create a systemd-service file.",
        action="store_true",
    )
    parser.set_defaults(cli=create_compose)
