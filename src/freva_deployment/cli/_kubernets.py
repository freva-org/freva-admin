"""Command line interface for creating k8s manifest files."""

from __future__ import annotations

import argparse
import base64
import re
from base64 import b64encode
from pathlib import Path
from typing import Any, Dict, List, Optional

import namegenerator
import yaml
from freva_deployment import __version__
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from ..deploy import DeployFactory
from ..logger import logger, set_log_level
from ..utils import RichConsole, asset_dir, config_dir

TASK = """---
- name: Render compose file locally only
  hosts: all
  connection: local
  gather_facts: yes

  tasks:

    - name: Render k8s manifests
      loop:
        "{{{{ templates }}}}"
      loop_control:
        loop_var: t
      template:
        src: "{asset_dir}/k8s-deployment/templates/{{{{ t }}}}"
        dest: "{{{{ out_dir }}}}/{{{{ t | basename | regex_replace('\\\\.j2$', '') }}}}"
"""


def get_ingress_hosts(
    services: List[str],
    domain: str,
    config: Dict[str, Any],
) -> List[Dict[str, str | int]]:
    """Define the ingress hosts."""
    lookup = {
        "freva-rest": [
            {
                "fqdn": f"freva-api.{domain}",
                "service": "freva-rest-server",
                "port": config["freva_rest"]["freva_rest_port"],
            },
            {
                "fqdn": f"freva-solr.{domain}",
                "service": "search-server",
                "port": 8983,
            },
        ],
        "web": [
            {
                "fqdn": f"freva-vault.{domain}",
                "service": "vault-server",
                "port": 5002,
            }
        ],
    }
    fqdns: List[Dict[str, str | int]] = []
    for service in services:
        for cfg in lookup.get(service, []):
            if cfg not in fqdns:
                fqdns.append(cfg)
    return fqdns


def get_pvcs_from_services(
    services: List[str], config: Dict[str, str]
) -> List[Dict[str, str]]:
    """Define the pvcs needed for each service."""
    lookup = {
        "freva-rest": [
            {
                "name": "solr-data",
                "mode": "ReadWriteOnce",
                "storage": config["solr"]["data_size"],
                "instance": "rest-api",
                "tier": "database",
                "component": "data",
            },
            {
                "name": "mongo-data",
                "mode": "ReadWriteOnce",
                "storage": config["mongo"]["data_size"],
                "instance": "mongo-server",
                "tier": "database",
                "component": "data",
            },
        ],
        "web": [
            {
                "name": "db-data",
                "mode": "ReadWriteOnce",
                "storage": config["mysql"]["data_size"],
                "instance": "database-server",
                "tier": "database",
                "component": "data",
            },
            {
                "name": "vault-data",
                "mode": "ReadWriteOnce",
                "storage": "500Mi",
                "instance": "web-app",
                "component": "data",
                "tier": "backend",
            },
        ],
    }
    lookup["web"] += lookup["freva-rest"]
    pvcs: List[Dict[str, str]] = []
    for service in services:
        for pvc_settings in lookup.get(service, []):
            if pvc_settings not in pvcs:
                pvcs.append(pvc_settings)
    return pvcs


def get_service_templates(services: List[str]) -> List[str]:
    """Assignes the templates needed for each the services."""
    lookup = {
        "freva-rest": ["12-solr.yaml.j2", "14-mongo.yaml.j2", "20-rest.yaml.j2"],
        "data-loader": ["11-redis.yaml.j2", "22-data-loader.yaml.j2"],
    }
    lookup["web"] = lookup["freva-rest"] + [
        "10-mysql.yaml.j2",
        "11-redis.yaml.j2",
        "13-vault.yaml.j2",
        "31-proxy.yaml.j2",
        "32-web-app.yaml.j2",
    ]
    templates: List[str] = [
        "00-namespace.yaml.j2",
        "01-secrets.yaml.j2",
        "02-pvcs.yaml.j2",
        "30-ingress.yaml.j2",
    ]
    for service in services:
        if service in lookup:
            templates += lookup[service]
    return sorted(set(templates))


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


def create_manifest(args: argparse.Namespace) -> None:
    """Create the k8s manifests."""
    set_log_level(args.verbose)
    services = args.services
    with DeployFactory(
        steps=None,
        config_file=args.config_file,
        local_debug=False,
        gen_keys=True,
    ) as DF:
        out_dir = (
            (args.output or Path.cwd() / DF.project_name).expanduser().absolute()
        )
        out_dir.mkdir(exist_ok=True, parents=True)
        eval_conf_enc = b64encode(
            DF.create_eval_config().read_text().encode()
        ).decode()
        extra = {
            **{
                "eval_config_content": eval_conf_enc,
                "use_core": args.no_plugins is False,
                "redis_password": DF._create_random_passwd(30, 10),
                "redis_username": namegenerator.gen(),
                "ingress_enabled": True,
                "ingress_fqdns": [DF.cfg["web"]["project_website"]],
                "out_dir": str(out_dir),
                "image_pull_policy": "IfNotPresent",
                "templates": get_service_templates(services),
                "pvcs": get_pvcs_from_services(
                    services, DF.cfg["kubernetes"]["pvc"]
                ),
                "resources": DF.cfg["kubernetes"]["resources"],
                "ingress_hosts": get_ingress_hosts(
                    services, DF.cfg["kubernetes"]["ingress"]["fqdn"], DF.cfg
                ),
            },
            **DF.cfg["kubernetes"],
        }
        logger.info("Parsing configurations")
        logger.debug("Extra args for playbooks:\n%s", extra)
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
                "[b]EVALUATION_SYSTEM_CONFIG_FILE[/b] env varaiable "
                "for the [b]web-server[/b] section in the compose file to the "
                "config file that was installed by conda/pip - e.g\n\n  "
                "<base-path-to-python-env>/freva/"
                "evaluation_system.conf\n"
                "This path also needs to be mounted as a volume into the "
                "container.\n"
            )

        playbook = TASK.format(asset_dir=asset_dir)
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
        config_path = (
            Path(inventory["core"]["vars"]["core_root_dir"])
            / "freva"
            / "web"
            / "freva_web.toml"
        )

        RichConsole.rule("")
        RichConsole.print(
            (
                "The k8s directory has been created. "
                f"\n\n{plugin_note}"
                "The web config file will be located in the "
                f"[b]{config_path}[/b] you can adjust it's settings there and"
                "restart the service."
            )
        )


def kubernetes_parser(
    epilog: str = "", parser: Optional[argparse.ArgumentParser] = None
) -> None:
    """Construct command line argument parser."""
    parser = parser or argparse.ArgumentParser(
        prog="deploy-freva-kubernetes",
        description="Creat and inspect k8s manifests for freva deployment.",
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
        "-s",
        "--services",
        nargs="+",
        default=["db", "freva-rest", "web", "data-loader"],
        choices=["web", "db", "freva-rest", "data-loader"],
        help="The services to be deployed.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory where the manifests should be located.",
        default=None,
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="Do not setup core library to use plugins.",
    )
    parser.set_defaults(cli=create_manifest)
