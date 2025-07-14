"""Module to run the freva deployment."""

from __future__ import annotations

import json
import logging
import os
import platform
import random
import shutil
import string
import sys
import time
from base64 import b64encode
from copy import deepcopy
from getpass import getuser
from pathlib import Path
from socket import gethostbyname, gethostname
from typing import Any, Dict, Optional, Union, cast
from urllib.parse import urlparse
from urllib.request import urlretrieve

import appdirs
import namegenerator
import tomlkit
import yaml
from rich import print as pprint
from rich.prompt import Prompt
from typing_extensions import NotRequired, TypedDict

import freva_deployment.callback_plugins
from freva_deployment import AUX_URL, FREVA_PYTHON_VERSION, __version__

from .error import ConfigurationError, handled_exception
from .keys import RandomKeys
from .logger import logger
from .runner import RunnerDir
from .utils import (
    RichConsole,
    asset_dir,
    config_dir,
    get_cache_information,
    get_passwd,
    load_config,
)
from .versions import get_steps_from_versions, get_versions

LOCAL_DEBUG_MSG = (
    "A freva test installation was sucessfully set up on your "
    "computer!\n\nYou can visit the freva-web app at "
    "https://localhost:8443\n"
    "You can log on with user: [b]{user}[/b], password: [b]{password}[/b]"
    "\n\nTo comepletly wipe the installation use the "
    "following commands:\n\n"
    "\tsystemctl stop --user 'freva-* data-loader* {project_name}-*' && \\ \n"
    "\trm -fr ~/.config/systemd/user/freva-*.service && \\ \n"
    "\trm -fr ~/.config/systemd/user/data-loader* && \\ \n"
    "\trm -fr ~/.config/systemd/user/{project_name}* && \\ \n"
    "\tsystemctl daemon-reload --user && \\ \n"
    "\trm -fr ~/.cache/freva-local\n\n"
    "You can omit the [i]--debug[/i] flag for a real deploymet."
)


class ConfigType(TypedDict):
    """Define the type of the yaml config dict."""

    hosts: NotRequired[str]
    vars: NotRequired[dict[str, str | int | bool | float]]


def get_current_architecture() -> str:
    """
    Determines the current architecture and operating system
    and maps it to one of the supported architectures.

    Supported architectures:
    - linux-64
    - linux-aarch64
    - linux-ppc64le
    - linux-s390x
    - osx-64
    - osx-arm64

    Returns:
        str: The corresponding architecture for mamba installation.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine == "x86_64":
            return "linux-64"
        if machine in ("aarch64", "arm64"):
            return "linux-aarch64"
        if machine == "ppc64le":
            return "linux-ppc64le"
        if machine == "s390x":
            return "linux-s390x"
    elif system == "darwin":
        if machine == "x86_64":
            return "osx-64"
        if machine == "arm64":
            return "osx-arm64"
    return "linux-64"


def mamba_to_conda_arch(arch: str) -> str:
    """Translate a mamba to a conda arch."""
    translate = {
        "linux-64": "Linux-x86_64",
        "linux-aarch64": "Linux-aarch64",
        "linux-ppc64le": "Linux-ppc64le",
        "linux-s390x": "Linux-s390x",
        "osx-64": "MacOSX-x86_64",
        "osx-arm64": "MacOSX-arm64",
    }
    if arch in translate.values():
        return arch
    return translate.get(arch, "linux-64")


class DeployFactory:
    """Apply freva deployment and its services.

    Parameters
    ----------
    project_name: str
        The name of the project to distinguish this instance from others.
    steps: list[str], default: ["core", "web", "freva_rest", "db"]
        The components that are going to be deployed.
    config_file: os.PathLike, default: None
        Path to any existing deployment configuration file.
    local_debug: bool, default: False
        Run deployment only on local machine, debug mode.
    gen_keys: bool, default: False
        Create new set of certificates, if they don't already exist.

    Examples
    --------

    >>> from freva_deployment import DeployFactory as DF
    >>> deploy = DF(steps=["freva_rest"])
    >>> deploy.play(ask_pass=True)
    """

    step_order: tuple[str, ...] = (
        "core",
        "db",
        "freva_rest",
        "web",
    )
    _steps_with_cert: tuple[str, ...] = ("core", "db", "web")

    @handled_exception
    def __init__(
        self,
        steps: list[str] | None = None,
        config_file: Path | str | None = None,
        local_debug: bool = False,
        gen_keys: bool = False,
        _cowsay: bool = False,
    ) -> None:
        self.passwords: dict[str, str] = {}
        self._no_cowsay = str(int(_cowsay is False))
        self.gen_keys = gen_keys or local_debug
        self.local_debug = local_debug
        self._config_keys: list[str] = []
        self._master_pass: str = ""
        self._td: RunnerDir = RunnerDir()
        self.eval_conf_file: Path = self._td.parent_dir / "evaluation_system.conf"
        self.web_conf_file: Path = self._td.parent_dir / "freva_web.toml"
        self._db_pass: str = ""
        self._steps = steps or ["db", "freva_rest", "web", "core"]
        if self._steps in (["auto"], "auto"):
            self._steps = []
        self._inv_tmpl = Path(config_file or config_dir / "inventory.toml")
        self._cfg_tmpl = self.aux_dir / "evaluation_system.conf.tmpl"
        self.cfg = self._read_cfg()
        self.project_name = self.cfg.pop("project_name", None)
        if not self.project_name:
            raise ConfigurationError("You must set a project name") from None
        self._random_key = RandomKeys(
            self.project_name,
            self.cfg.get("web", {}).get("web_host", "localhost"),
        )
        self.current_step = ""
        self._check_steps_()

    def _check_steps_(self) -> None:
        """Before we do anything check if something is wrong with the config."""
        # First the steps that are needed
        old_master = self._master_pass
        self._master_pass = old_master or "foo"
        not_in_use = set(["db", "freva_rest", "web", "core"]) - set(self.steps)
        for step in self.steps:
            getattr(self, f"_prep_{step.replace('-', '_')}")()
        for step in not_in_use:
            try:
                getattr(self, f"_prep_{step.replace('-', '_')}")()
            except ConfigurationError as error:
                logger.warning("Some of your config isn't valid:\n%s", error)
        self._master_pass = old_master

    @property
    def master_pass(self) -> str:
        """Define the master password."""
        if self._master_pass:
            return self._master_pass
        self._master_pass = get_passwd(os.environ.get("MASTER_PASSWD", ""))
        return self._master_pass

    @property
    def public_key_file(self) -> str:
        """Path to the public certificate file."""
        public_keyfile = self.cfg["certificates"].get("public_keyfile")
        chain_keyfile = self.cfg["certificates"].get("chain_keyfile")
        if public_keyfile:
            return str(Path(public_keyfile).expanduser().absolute())
        if chain_keyfile:
            return str(Path(chain_keyfile).expanduser().absolute())
        if self.gen_keys:
            return self._random_key.public_chain_file
        raise ConfigurationError(
            "You must give a valid path to a public key file."
        ) from None

    @property
    def private_key_file(self) -> str:
        """Path to the private key file."""
        keyfile = self.cfg["certificates"].get("private_keyfile")
        if keyfile:
            return str(Path(keyfile).expanduser().absolute())
        if self.gen_keys:
            return self._random_key.private_key_file
        raise ConfigurationError(
            "You must give a valid path to a private key file."
        ) from None

    def _prep_vault(self) -> None:
        """Prepare the vault."""
        self._config_keys.append("vault")
        self.cfg["vault"].setdefault("ansible_become_user", "root")
        self.cfg["vault"].pop("db_playbook", "")
        self.cfg["vault"]["db_port"] = self.cfg["vault"].get("port", 3306)
        self.cfg["vault"]["version"] = __version__
        self.cfg["vault"]["db_user"] = self.cfg["vault"].get("user", "")
        self.cfg["vault"]["root_passwd"] = self.master_pass
        self.cfg["vault"]["passwd"] = self.db_pass
        self.cfg["vault"]["keyfile"] = self.public_key_file
        self.cfg["vault"]["email"] = self.cfg["web"].get("contacts", "")
        self.cfg["vault"]["db_host"] = self.cfg["db"]["db_host"]

    def _prep_db(self) -> None:
        """prepare the mariadb service."""
        self._config_keys.append("db")
        self.cfg["db"].setdefault("ansible_become_user", "root")
        host = self.cfg["db"]["db_host"]
        self.cfg["db"]["root_passwd"] = self.master_pass
        self.cfg["db"]["passwd"] = self.db_pass
        self.cfg["db"]["keyfile"] = self.public_key_file
        data_path = Path(
            cast(
                str,
                self.cfg["db"].get("data_path", "/opt/freva"),
            )
        )
        self.cfg["db"]["data_path"] = str(data_path)
        for key in ("name", "user", "db"):
            self.cfg["db"][key] = self.cfg["db"].get(key) or "freva"
        db_host = self.cfg["db"].get("host", "").strip()
        if not db_host:
            self.cfg["db"]["host"] = host
        self.cfg["db"].setdefault("port", "3306")
        self.cfg["db"]["email"] = self.cfg["web"].get("contacts", "")
        self._prep_vault()
        self._prep_web(False)

    def _prep_data_loader(self) -> None:
        """Prepare the data-loader."""
        data_path = Path(
            cast(
                str,
                self.cfg["freva_rest"].get("data_path", "/opt/freva"),
            )
        )
        redis_host = (
            self.cfg["freva_rest"].get("redis_host", "")
            or self.cfg["freva_rest"]["freva_rest_host"]
        )
        data_portal_host = self.cfg["freva_rest"].get(
            "data_loader_portal_hosts", ""
        )
        data_portal_hosts = [
            d.strip() for d in data_portal_host.split(",") if d.strip()
        ]
        if data_portal_hosts:
            scheduler_host = data_portal_hosts[0]
        else:
            scheduler_host = ""
        for prefix in ("redis://", "http://", "https://", "tcp://"):
            redis_host = redis_host.removeprefix(prefix)
            scheduler_host = scheduler_host.removeprefix(prefix)

        redis_host, _, redis_port = redis_host.partition(":")
        redis_port = redis_port or "6379"
        self.cfg["freva_rest"][
            "redis_cache_url"
        ] = f"redis://{redis_host}:{redis_port}"
        self.cfg["freva_rest"]["redis_host_name"] = redis_host
        proxy_url = (
            f'http://{self.cfg["freva_rest"]["freva_rest_host"]}:'
            f'{self.cfg["freva_rest"]["freva_rest_port"]}'
        )
        proxy_url = (
            self.cfg["web"].get("project_website", "").strip() or proxy_url
        )
        scheme, _, netloc = proxy_url.rpartition("://")
        scheme = scheme or "http"
        self.cfg["freva_rest"]["proxy_url"] = f"{scheme}://{netloc}"
        scheduler_host, _, scheduler_port = scheduler_host.partition(":")
        redis_information = get_cache_information(
            redis_host,
            redis_port,
            scheduler_host,
            scheduler_port or "40000",
        )
        redis_information["passwd"] = self._create_random_passwd(30, 10)
        redis_information_enc = b64encode(
            json.dumps(redis_information).encode("utf-8")
        ).decode("utf-8")
        self._config_keys.append("redis")
        self._config_keys.append("data_portal_hosts")
        self._config_keys.append("data_portal_scheduler")
        if not scheduler_host:
            self.cfg["data_portal_scheduler"] = self.cfg["redis"] = self.cfg[
                "data_portal_hosts"
            ] = {}
            return
        # Update the config.
        self.cfg["data_portal_scheduler"] = {
            "data_portal_scheduler_host": scheduler_host or "",
            "information": redis_information_enc,
            "admin_user": self.cfg["freva_rest"].get("admin_user", ""),
            "is_worker": False,
            "ansible_become_user": self.cfg["freva_rest"].get(
                "ansible_become_user", "root"
            ),
            "ansible_user": self.cfg["freva_rest"].get("ansible_user", getuser()),
        }
        if data_portal_hosts[1:]:
            self.cfg["data_portal_hosts"] = {
                "data_portal_hosts": ",".join(data_portal_hosts[1:]),
                "information": redis_information_enc,
                "admin_user": self.cfg["freva_rest"].get("admin_user", ""),
                "ansible_become_user": self.cfg["freva_rest"].get(
                    "ansible_become_user", "root"
                ),
                "ansible_user": self.cfg["freva_rest"].get(
                    "ansible_user", getuser()
                ),
            }
        self.cfg["redis"] = {
            "redis_host": redis_host,
            "information": redis_information_enc,
            "project_name": self.project_name,
            "port": redis_port,
            "admin_user": self.cfg["freva_rest"].get("admin_user", ""),
            "data_path": str(data_path),
            "ansible_become_user": self.cfg["freva_rest"].get(
                "ansible_become_user", "root"
            ),
            "ansible_user": self.cfg["freva_rest"].get("ansible_user", getuser()),
            "information": redis_information_enc,
        }

    def _prep_freva_rest(self, prep_web=True) -> None:
        """prepare the freva_rest service."""
        self._config_keys.append("freva_rest")
        self._prep_data_loader()
        self.cfg["freva_rest"].setdefault("ansible_become_user", "root")
        self.cfg["freva_rest"]["root_passwd"] = self.master_pass
        self.cfg["freva_rest"]["db_passwd"] = self._create_random_passwd(30, 10)
        freva_rest_host = self.cfg["freva_rest"]["freva_rest_host"]
        vault_host = self.cfg["db"].get("vault_host") or self.cfg["db"]["db_host"]
        self.cfg["freva_rest"]["vault_host"] = vault_host
        self.cfg["freva_rest"]["db_host"] = freva_rest_host
        self.cfg["freva_rest"]["db_user"] = namegenerator.gen()
        self.cfg["freva_rest"].pop("core", None)
        services = ["databrowser", "stacapi"]
        if self.cfg["freva_rest"].get("data_loader_portal_hosts", "").strip():
            services.append("zarr-stream")
            self.cfg["freva_rest"]["data_loader"] = True
        else:
            self.cfg["freva_rest"]["data_loader"] = False
        data_path = Path(
            cast(
                str,
                self.cfg["freva_rest"].get("data_path", "/opt/freva"),
            )
        )
        self.cfg["freva_rest"]["data_path"] = str(data_path)
        for key, default in dict(solr_mem="4g", freva_rest_port=7777).items():
            self.cfg["freva_rest"][key] = (
                self.cfg["freva_rest"].get(key) or default
            )
        self.cfg["freva_rest"]["email"] = self.cfg["web"].get("contacts", "")
        self.cfg["freva_rest"].setdefault("oidc_url", "")
        self.cfg["freva_rest"].setdefault("oidc_client", "freva")
        self.cfg["freva_rest"].setdefault("oidc_client_secret", "")
        token_claims = self.cfg["freva_rest"].get("oidc_token_claims") or {}
        if isinstance(token_claims, str):
            self.cfg["freva_rest"]["oidc_token_claims"] = token_claims
        else:
            token_claims_str = []
            for key, values in token_claims.items():
                if isinstance(values, str):
                    values = [values]
                for v in values:
                    token_claims_str.append(f"{key}:{v}")
            self.cfg["freva_rest"]["oidc_token_claims"] = ",".join(
                token_claims_str
            )
        self.cfg["freva_rest"]["services"] = ",".join(services)
        if prep_web:
            self._prep_web(False)
        for key in ("mongodb_server", "search_server"):
            self._config_keys.append(key)
            self.cfg[key] = deepcopy(self.cfg["freva_rest"])

    def _prep_core(self) -> None:
        """prepare the core deployment."""
        self._config_keys.append("core")
        self.cfg["core"].setdefault("ansible_become_user", "")
        # Legacy args as we are going to use micromamba
        self.cfg["core"]["arch"] = mamba_to_conda_arch(
            self.cfg["core"]
            .get("arch", "linux-64")
            .lower()
            .replace("x86_", "")
            .replace("mac", "")
        )
        self.cfg["core"]["python_version"] = FREVA_PYTHON_VERSION
        self.cfg["core"]["admins"] = self.cfg["core"].get("admins") or getuser()
        if not self.cfg["core"]["admins"]:
            self.cfg["core"]["admins"] = getuser()
        install_dir = Path(self.cfg["core"]["install_dir"])
        root_dir = Path(
            self.cfg["core"].get("root_dir", "").strip() or install_dir
        )
        self.cfg["core"]["install_dir"] = str(install_dir)
        self.cfg["core"]["root_dir"] = str(root_dir)
        preview_path = self.cfg["core"].get("preview_path", "")
        base_dir_location = self.cfg["core"].get("base_dir_location", "") or str(
            root_dir / "work"
        )
        self.cfg["core"]["base_dir_location"] = base_dir_location
        scheduler_output_dir = self.cfg["core"].get("scheduler_output_dir", "")
        scheduler_system = self.cfg["core"].get("scheduler_system", "local")
        if not preview_path:
            self.cfg["core"]["preview_path"] = str(
                Path(base_dir_location) / "share" / "preview"
            )
        if not scheduler_output_dir:
            scheduler_output_dir = str(Path(base_dir_location) / "share")
        elif Path(scheduler_output_dir).parts[-1] != scheduler_system:
            scheduler_output_dir = Path(scheduler_output_dir) / scheduler_system
        self.cfg["core"]["scheduler_output_dir"] = str(scheduler_output_dir)
        self.cfg["core"]["keyfile"] = self.public_key_file
        self.cfg["core"]["git_url"] = "https://github.com/FREVA-CLINT/freva.git"

    def _prep_web(self, ask_pass: bool = True) -> None:
        """prepare the web deployment."""
        self._config_keys.append("web")

        for key in "oidc_url", "oidc_client", "oidc_client_secret":
            self.cfg["web"][key] = self.cfg["freva_rest"].get("oidc_url", "")
        self.cfg["web"].setdefault("ansible_become_user", "root")
        self._prep_core()
        freva_rest_host = (
            f'{self.cfg["freva_rest"]["freva_rest_host"]}:'
            f'{self.cfg["freva_rest"]["freva_rest_port"]}'
        )
        self.cfg["web"]["freva_rest_host"] = freva_rest_host
        self.cfg["web"].setdefault("deploy_web_server", True)
        data_path = Path(
            cast(
                str,
                self.cfg["web"].get("data_path", "/opt/freva"),
            )
        )
        self.cfg["web"]["data_path"] = str(data_path)
        admin = self.cfg["core"]["admins"]
        try:
            for k, v in self.cfg["web"].items():
                self.cfg["web"].setdefault(k, "")
        except KeyError:
            raise ConfigurationError(
                "No web config section given, please configure the web.config"
            ) from None
        if not isinstance(admin, str):
            self.cfg["web"]["admin"] = admin[0]
        else:
            self.cfg["web"]["admin"] = admin
        allowed_hosts = self.cfg["web"].get("allowed_hosts") or ["localhost"]
        if isinstance(allowed_hosts, str):
            allowed_hosts = [
                s.strip() for s in allowed_hosts.split(",") if s.strip()
            ]
        allowed_hosts.append(self.cfg["web"]["web_host"])
        allowed_hosts.append(f"{self.project_name}-httpd")
        self.cfg["web"]["allowed_hosts"] = [
            s.strip() for s in set(allowed_hosts) if s.strip()
        ]
        self.cfg["web"].setdefault("main_color", "Tomato")
        _webserver_items = {
            "institution_logo": self.cfg["web"].get("institution_logo", ""),
            "main_color": self.cfg["web"].get("main_color", "Tomato"),
            "border_color": self.cfg["web"].get("border_color", "#6c2e1f"),
            "hover_color": self.cfg["web"].get("hover_color", "#d0513a"),
            "homepage_text": self.cfg["web"].get("homepage_text", ""),
            "imprint": self.cfg["web"].get("imprint", []),
            "homepage_heading": self.cfg["web"].get("homepage_heading", ""),
            "about_us_text": self.cfg["web"].get("about_us_text", ""),
            "contacts": self.cfg["web"].get("contacts", []),
            "insitution_name": self.cfg["web"].get("insitution_name", ""),
            "menu_entries": self.cfg["web"].get("menu_entries", []),
        }
        try:
            with Path(_webserver_items["homepage_text"]).open("r") as f_obj:
                _webserver_items["homepage_text"] = f_obj.read()
        except (FileNotFoundError, IOError, KeyError):
            pass
        try:
            with Path(_webserver_items["about_us_text"]).open() as f_obj:
                _webserver_items["about_us_text"] = f_obj.read()
        except (FileNotFoundError, IOError, KeyError):
            pass
        web_config = tomlkit.dumps(_webserver_items)
        self.web_conf_file.write_text(web_config)
        self.cfg["web"]["config_content"] = b64encode(
            web_config.encode()
        ).decode()
        server_name = self.cfg["web"].pop("server_name", [])
        if isinstance(server_name, str):
            server_name = server_name.split(",")
        server_name = ",".join([a for a in server_name if a.strip()])
        if not server_name:
            server_name = self.cfg["web"]["web_host"]
        self.cfg["web"]["server_name"] = server_name
        web_host = self.cfg["web"]["web_host"]
        if web_host == "127.0.0.1":
            web_host = "localhost"
        self.cfg["web"]["host"] = web_host
        self.cfg["web"]["csrf_trusted_origins"] = []
        for url in [server_name] + self.cfg["web"]["project_website"].split(","):
            trusted_origin = urlparse(url.strip())

            if trusted_origin.scheme:
                netloc = trusted_origin.netloc.removeprefix("www.")
            else:
                netloc = trusted_origin.path.removeprefix("www.")
            for prefix in ("www.", ""):
                uri = f"https://{prefix}{netloc}"
                self.cfg["web"]["csrf_trusted_origins"].append(uri)

        self.cfg["web"]["csrf_trusted_origins"] = list(
            set(self.cfg["web"]["csrf_trusted_origins"])
        )
        self.cfg["web"]["freva_bin"] = os.path.join(
            self.cfg["core"]["install_dir"], "bin"
        )
        for key in ("core", "web"):
            self.cfg[key]["config_toml_file"] = str(self.web_conf_file)
        self._prep_vault()
        self.cfg["vault"]["ansible_python_interpreter"] = self.cfg["db"].get(
            "ansible_python_interpreter", "/usr/bin/python3"
        )
        self.cfg["web"]["root_passwd"] = self.master_pass
        self.cfg["web"]["private_keyfile"] = self.private_key_file
        self.cfg["web"]["public_keyfile"] = self.public_key_file
        self.cfg["web"]["key_content"] = b64encode(
            Path(self.private_key_file).read_bytes()
        ).decode("utf-8")
        self.cfg["web"]["cert_content"] = b64encode(
            Path(self.public_key_file).read_bytes()
        ).decode("utf-8")
        self.cfg["web"]["eval_conf_file"] = str(
            Path(self.cfg["core"]["root_dir"])
            / "freva"
            / "evaluation_system.conf"
        )
        chatbot_host = self.cfg["web"].get("chatbot_host", "") or "localhost"
        self.cfg["web"]["vault_host"] = self.cfg["db"].get(
            "vault_host"
        ) or self.cfg["db"].get("db_host", "localhost")
        self.cfg["web"]["chatbot_host"] = chatbot_host
        if self._random_key.check_cert_key_pair(
            self.public_key_file, self.private_key_file
        ):
            self.cfg["web"]["chatbot_rest_api_url"] = f"https://{web_host}"
        else:
            self.cfg["web"]["chatbot_rest_api_url"] = f"http://{freva_rest_host}"
        self.cfg["web"]["redis_username"] = namegenerator.gen()
        self.cfg["web"]["redis_password"] = self._create_random_passwd()

    def _prep_local_debug(self, cfg: dict[str, Any]) -> dict[str, Any]:
        """Prepare the system for a potential local debug."""
        self._master_pass = "secret"
        default_ports = {"db": 3306, "freva_rest": 7777}
        cfg.setdefault("project_name", "freva-test-deployment")
        cfg["deployment_method"] = "conda"
        deploy_dir = Path(appdirs.user_data_dir("freva-local"))
        deploy_dir.mkdir(exist_ok=True, parents=True)
        host = gethostbyname(gethostname())
        cfg["deployment_dir"] = str(deploy_dir)
        steps = [k for (k, v) in cfg.items() if isinstance(v, dict)]
        for step in steps:
            for var in cfg[step]:
                if var.endswith("_host") or var.endswith("_hosts"):
                    cfg[step][var] = host
                if var.endswith("admin_user"):
                    cfg[step][var] = getuser()
            cfg[step]["wipe"] = False
            if step in default_ports:
                cfg[step]["port"] = default_ports[step]
            cfg[step]["ansible_user"] = getuser()
            cfg[step]["ansible_python_interpreter"] = sys.executable
            cfg[step]["ansible_become_user"] = ""
            cfg[step]["data_path"] = str(deploy_dir)
        cfg["db"]["db_host"] = cfg["db"]["vault_host"] = host
        cfg["core"]["ansible_become_user"] = ""
        cfg["core"]["scheduler_system"] = "local"
        cfg["core"]["admins"] = getuser()
        cfg["web"]["scheduler_host"] = ["localhost"]
        cfg["web"]["allowed_hosts"] = [host, "localhost", "127.0.0.1"]
        cfg["web"]["project_website"] = "https://localhost"
        cfg["core"]["arch"] = get_current_architecture()
        cfg["freva_rest"]["oidc_url"] = (
            "http://localhost:8080/realms/freva/"
            ".well-known/openid-configuration"
        )
        cfg["freva_rest"]["oidc_client"] = "freva"
        cfg["freva_rest"]["oidc_client_secret"] = ""
        cfg["freva_rest"]["oidc_token_claims"] = ""
        for key in (
            "root_dir",
            "base_dir_location",
            "preview_path",
            "scheduler_output_dir",
            "admin_group",
            "root_dir",
        ):
            cfg["core"][key] = ""
        cfg["core"]["install_dir"] = str(
            deploy_dir / cfg["project_name"] / "freva-core"
        )
        return cfg

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._td.cleanup()

    def _read_cfg(self) -> dict[str, Any]:
        mapper = {
            "vault": "db",
            "mongodb_server": "freva_rest",
            "search_server": "freva_rest",
        }
        try:
            config = dict(load_config(self._inv_tmpl, convert=True).items())
            for dest, source in mapper.items():
                host = (
                    config[source].get(f"{dest}_host")
                    or config[source][f"{source}_host"]
                )
                config[dest] = deepcopy(config[source])
                config[dest][f"{dest}_host"] = config[source][f"{dest}_host"] = (
                    host
                )
            if self.local_debug:
                config = self._prep_local_debug(config)
            return config
        except FileNotFoundError:
            raise ConfigurationError(f"No such file {self._inv_tmpl}") from None
        except KeyError as error:
            raise ConfigurationError(str(error)) from error

    def _check_config(self) -> None:
        sections = []
        config_keys = [s for s in set(self._config_keys)]
        for section in self.cfg.keys():
            for step in config_keys:
                if section.startswith(step) and section not in sections:
                    sections.append(section)
        for section in sections:
            for key, value in self.cfg[section].items():
                if (
                    not value
                    and not self._empty_ok
                    and not isinstance(value, bool)
                ):
                    raise ConfigurationError(
                        f"{key} in {section} is empty in {self._inv_tmpl}"
                    ) from None

    @property
    def ask_become_password(self) -> bool:
        """Check if we have to ask for the sudo passwd at all."""
        cfg = deepcopy(self.cfg)
        solr_config = cfg.get("databrowser", cfg.get("solr", {}))
        cfg.setdefault("freva_rest", solr_config)
        for step in cfg:
            if isinstance(cfg[step], dict):
                ansible_become_user = cfg[step].get("ansible_become_user", "root")
                if ansible_become_user:
                    return True
        return False

    @property
    def _empty_ok(self) -> list[str]:
        """Define all keys that can be empty."""
        return [
            "admins",
            "conda_exec_path",
            "ansible_become_user",
        ]

    def _get_files_copy(self, key) -> Path | None:
        return dict(
            core=self.eval_conf_file.absolute(),
            web=self.eval_conf_file.absolute(),
        ).get(key, None)

    @staticmethod
    def _create_random_passwd(num_chars: int = 30, num_digits: int = 8) -> str:
        num_chars -= num_digits
        characters = [
            "".join(
                [random.choice(string.ascii_letters) for i in range(num_chars)]
            ),
            "".join([random.choice(string.digits) for i in range(num_digits)]),
        ]
        str_characters = "".join(characters)
        _db_pass = "".join(random.sample(str_characters, len(str_characters)))
        while _db_pass.startswith("@"):
            # Vault treats values starting with "@" as file names.
            _db_pass = "".join(random.sample(str_characters, len(str_characters)))
        return _db_pass

    @property
    def db_pass(self) -> str:
        """Create a password for the database."""
        if self._db_pass:
            return self._db_pass
        self._db_pass = self._create_random_passwd(30, 8)
        return self._db_pass

    @property
    def _needs_core(self) -> list[str]:
        """Define the steps that need the core config."""
        return ["web", "core"]

    def _set_additional_config_values(
        self,
        step: str,
        config: dict[str, ConfigType],
    ) -> None:
        """Set additional values to the configuration."""
        if step in self._needs_core:
            for key in (
                "root_dir",
                "base_dir_location",
                "preview_path",
                "scheduler_output_dir",
            ):
                value = self.cfg["core"].get(key, "")
                config[step]["vars"][f"core_{key}"] = value
        config[step]["vars"][f"{step}_name"] = f"{self.project_name}-{step}"
        config[step]["vars"]["asset_dir"] = str(asset_dir)
        config[step]["vars"]["ansible_user"] = (
            self.cfg[step].get("ansible_user") or getuser()
        )
        config[step]["vars"][f"{step}_ansible_python_interpreter"] = (
            self.cfg[step].get("ansible_python_interpreter") or "/usr/bin/python3"
        )
        dump_file = self._get_files_copy(step)
        if dump_file:
            config[step]["vars"][f"{step}_dump"] = str(dump_file)

    def parse_config(self, steps: list[str], **extra: str) -> Optional[str]:
        """Create config files for ansible and evaluation_system.conf."""
        versions = get_versions()
        additional_steps = set(steps) - set(self.steps)
        if additional_steps:
            pprint(
                "The following, [b]not selected[/b] steps will be auto "
                f"updated.\n[green]{', '.join(additional_steps)}[/]"
            )
            time.sleep(3)
        new_steps = set(steps + self.steps)
        if not new_steps:
            return None
        self._steps = list(new_steps)
        logger.info("Parsing configurations")
        self._check_config()
        _ = [getattr(self, f"_prep_{step}")() for step in self.steps]
        config: dict[str, ConfigType] = {}
        playbooks = "\n".join(
            [
                a.read_text()
                for a in (asset_dir / "playbooks").rglob("*.*")
                if a.is_file()
            ]
        )
        main_playbook = yaml.safe_load(
            (asset_dir / "playbooks" / "main-deployment.yml").read_text()
        )
        tags, hosts = [], []
        for entry in main_playbook:
            for tag in entry.get("tags", []):
                if tag in self.steps + ["vault"]:
                    tags.append(entry["hosts"])
        no_prepend = ("root_passwd", "deployment_method")
        for step in set(self._config_keys):
            config[step] = {}
            if self.cfg.get(step, {}).get(f"{step}_host"):
                config[step]["hosts"] = self.cfg[step][f"{step}_host"]
            elif self.cfg.get(step, {}).get(step):
                config[step]["hosts"] = self.cfg[step][step]
            else:
                continue
            if step != "core" and step in config:
                hosts.append(config[step]["hosts"])
            config[step]["vars"] = {}
            for key, value in self.cfg[step].items():
                if key in no_prepend + (f"{step}_host",) or key.startswith(step):
                    new_key = key
                else:
                    new_key = f"{step.replace('-', '_')}_{key}"
                if new_key in playbooks:
                    config[step]["vars"][new_key] = value
            config[step]["vars"]["project_name"] = self.project_name
            config[step]["vars"][f"{step}_admin_user"] = self.cfg[step].get(
                "admin_user", ""
            )
            config[step]["vars"]["deployment_method"] = self.cfg.get(
                "deployment_method", "docker"
            )
            if step in versions:
                config[step]["vars"][f"{step.replace('-', '_')}_version"] = (
                    versions[step]
                )
            config[step]["vars"]["debug"] = self.local_debug
            # Add additional keys
            self._set_additional_config_values(step, config)
            for k, v in extra.items():
                config[step]["vars"][k] = v
        max_width = int(max(shutil.get_terminal_size().columns * 0.75, 25))
        if "search_server" in config:
            config["search_server"]["vars"]["solr_version"] = versions["solr"]
        if "db" in config:
            config["db"]["vars"]["vault_version"] = versions["vault"]
            for key, value in config["vault"]["vars"].items():
                if key.startswith("vault_"):
                    config["db"]["vars"].setdefault(key, value)
        if "web" in config:
            config["web"]["vars"]["proxy_version"] = versions.get("nginx", "")
        info: Dict[str, Any] = {}
        for step in config:
            for key, value in config[step].get("vars", {}).items():
                if step in tags or ("db" in self.steps and step == "vault"):
                    info.setdefault(step, {})
                    info[step].setdefault("vars", {})
                    add_value: Union[str, int, float] = value
                    if isinstance(value, str) and "pass" in key:
                        add_value = "***"
                    elif isinstance(value, str) and len(value) > max_width:
                        add_value = value[:max_width] + "..."
                    info[step]["vars"][key] = add_value
        info_str = yaml.dump(json.loads(json.dumps(info)))
        for passwd in (self.master_pass,):
            if passwd:
                info_str = info_str.replace(passwd, "***")
        if logger.level > logging.DEBUG:
            RichConsole.print(info_str, style="bold", markup=True)
        core_host: Optional[str] = config.get("core", {}).get("hosts")
        if core_host in hosts:
            config["core"]["hosts"] = gethostbyname(core_host) or ""
        return yaml.dump(json.loads(json.dumps(config)))

    @property
    def python_prefix(self) -> Path:
        """Get the path of the new conda evnironment."""
        return Path(sys.exec_prefix) / "bin" / "python3"

    @property
    def aux_dir(self) -> Path:
        """Directory with auxillary files."""
        return asset_dir / "config"

    @property
    def steps(self) -> list[str]:
        """Set all the deployment steps."""
        return [s for s in self.step_order if s in self._steps]

    def _set_deployment_methods(self) -> None:
        """Check the deployment methods."""
        valid_deployment_methods = ("podman", "docker", "conda", "k8s")
        deployment_method = self.cfg.get("deployment_method")
        if deployment_method not in valid_deployment_methods:
            raise ConfigurationError(
                f"Deployment method: {deployment_method} is invalid, should be"
                f"one of {', '.join(valid_deployment_methods)}"
            )

    def create_eval_config(self) -> Optional[Path]:
        """Create and dump the evaluation_system.config."""
        logger.info("Creating evaluation_system.conf")
        keys = (
            ("core", "admins"),
            ("web", "project_website"),
            ("core", "root_dir"),
            ("core", "base_dir_location"),
            ("core", "preview_path"),
            ("core", "scheduler_output_dir"),
            ("core", "scheduler_system"),
        )
        cfg_file = asset_dir / "config" / "evaluation_system.conf.tmpl"
        if not cfg_file.is_file():
            cfg_file.parent.mkdir(exist_ok=True, parents=True)
            urlretrieve(AUX_URL, filename=str(cfg_file))

        with cfg_file.open() as f_obj:
            lines = f_obj.readlines()
            for num, line in enumerate(lines):
                if line.startswith("project_name"):
                    lines[num] = f"project_name={self.project_name}\n"
                for key, value in keys:
                    if line.startswith(value):
                        cfg = self.cfg[key].get(value, "")
                        if cfg:
                            lines[num] = f"{value}={cfg}\n"
                for step in ("freva_rest", "db"):
                    cfg = self.cfg[step].get("port", "")
                    if line.startswith(f"{step}.port"):
                        lines[num] = f"{step}.port={cfg}\n"
                    if line.startswith(f"{step}.host"):
                        lines[num] = (
                            f"{step}.host={self.cfg[step][f'{step}_host']}\n"
                        )
                if line.startswith("solr.host"):
                    lines[num] = f"solr.host={self.cfg[step][f'{step}_host']}\n"
                if line.startswith("db.host"):
                    lines[num] = f"db.host={self.cfg['db']['db_host']}\n"
        dump_file = self._get_files_copy("core")
        if dump_file:
            with dump_file.open("w") as f_obj:
                f_obj.write("".join(lines))
        return dump_file

    def get_ansible_password(self, ask_pass: bool = False) -> dict[str, str]:
        """The passwords for the ansible environments."""
        ssh_pass_msg = "Give the [b]ssh[/b] password for remote login"
        sudo_pass_msg = "Give the password elevating user privilege ([b]sudo[/b])"
        if ask_pass:
            sudo_pass_msg += ", defaults to ssh password"
        passwords = {}
        ssh_key = "ansible_ssh_pass"
        sudo_key = "ansible_become_pass"
        passwords[sudo_key] = os.environ.get("ANSIBLE_BECOME_PASSWORD", "") or ""
        passwords[ssh_key] = os.environ.get("ANSIBLE_SSH_PASSWORD", "") or ""
        if ask_pass and not passwords[ssh_key]:
            passwords[ssh_key] = Prompt.ask(
                f"[green]{ssh_pass_msg}[/green]", password=True
            )
        if not passwords[sudo_key] and self.ask_become_password:
            passwords[sudo_key] = Prompt.ask(
                f"[green]{sudo_pass_msg}[/green]", password=True
            )
            if not passwords[sudo_key]:
                passwords[sudo_key] = passwords.get(ssh_key, "")
        return passwords

    @handled_exception
    def play(
        self,
        ask_pass: bool = True,
        verbosity: int = 0,
        ssh_port: int = 22,
        skip_version_check: bool = False,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Play the ansible playbook.

        Parameters
        ----------
        ask_pass: bool, default: True
            Instruct Ansible to ask for the ssh password instead of using a
            ssh key
        verbosity: int, default: 0
            Verbosity level, default 0
        ssh_port: int, default: 22
            Set the ssh port, in 99.9% of cases this should be left at port 22
        skip_version_check: bool, default: False
            Skip the version check, use with caution
        tags: list[str], default: None
            Instead of running the steps, fine grain the deployment using this
            specific tasks.
        """
        try:
            self._play(
                ask_pass=ask_pass,
                verbosity=verbosity,
                ssh_port=ssh_port,
                skip_version_check=skip_version_check,
                tags=tags,
            )
        except KeyboardInterrupt as error:
            if str(error):
                pprint(f" [red][ERROR]: {error}[/]", file=sys.stderr)
            raise KeyboardInterrupt() from None

    def get_steps_from_versions(
        self,
        envvars: dict[str, str],
        extravars: dict[str, str],
        passwords: dict[str, str],
        verbosity: int,
    ) -> list[str]:
        """Check the versions of the different freva parts."""
        config: dict[str, ConfigType] = {}
        steps = list(set(self.step_order) - set(self.steps))
        if not steps or self.local_debug:
            # The user has selected all steps anyway, nothing to do here:
            return []
        playbook_tmpl = yaml.safe_load(
            (asset_dir / "playbooks" / "versions.yaml").read_text()
        )
        playbook = []
        cfg = deepcopy(self.cfg)
        if "web" in steps and not cfg.get("web", {}).get("web_host", "").strip():
            steps = [s for s in steps if s != "web"]
        steps.append("vault")
        version_path = self._td.parent_dir / "versions.txt"
        hosts = []
        for tasks in playbook_tmpl:
            step = tasks["hosts"]
            if step in steps:
                playbook.append(tasks)
                host_var = cfg[step][f"{step}_host"]
                if step != "core":
                    hosts.append(host_var)
                config[step] = {}
                config[step]["hosts"] = host_var
                ansible_user = cfg[step].get("ansible_user") or os.getenv(
                    "ANSIBLE_USER", getuser()
                )
                if "ansible_become_user" not in cfg[step]:
                    become_user = "root"
                else:
                    become_user = cfg[step]["ansible_become_user"]

                config[step]["vars"] = {
                    f"{step}_ansible_become_user": become_user,
                    "asset_dir": str(asset_dir),
                    "deployment_method": self.cfg.get(
                        "deployment_method", "docker"
                    ),
                    f"{step}_ansible_user": ansible_user,
                    "project_name": self.project_name,
                    f"{step}_data_path": cfg[step].get("data_path", ""),
                    "version_file_path": str(version_path),
                }
                python_exe = self.cfg[step].get("ansible_python_interpreter", "")
                config[step]["vars"][f"{step}_ansible_python_interpreter"] = (
                    python_exe or "/usr/bin/python"
                )
        config.setdefault("core", {})
        config["core"].setdefault("vars", {})
        config["core"]["vars"]["core_install_dir"] = cfg["core"]["install_dir"]
        core_host: Optional[str] = config.get("core", {}).get("hosts")
        if core_host and core_host in hosts:
            config["core"]["hosts"] = gethostbyname(core_host) or ""
        result = self._td.run_ansible_playbook(
            playbook=playbook,
            inventory=config,
            envvars=envvars,
            passwords=passwords,
            extravars=extravars,
            verbosity=verbosity,
            hide_output=True,
            text="Getting versions of micro-services ...",
        )
        versions = {}
        for line in result.splitlines():
            jline = json.loads(line)
            if "msg" in jline["result"] and jline["task"].lower().startswith(
                "display"
            ):
                service = jline["task"].split()[1].lower()
                version = jline["result"]["msg"].strip()
                versions[service.strip()] = version.strip()
        logger.debug("Detected versions: %s", versions)
        additional_steps = get_steps_from_versions(versions)
        return additional_steps

    def _play(
        self,
        ask_pass: bool = True,
        verbosity: int = 0,
        ssh_port: int = 22,
        skip_version_check: bool = False,
        tags: Optional[list[str]] = None,
    ) -> None:
        plugin_path = Path(freva_deployment.callback_plugins.__file__).parent
        envvars: dict[str, str] = {
            "ANSIBLE_CONFIG": str(self._td.ansible_config_file),
            "ANSIBLE_NOCOWS": self._no_cowsay.lower(),
            "ANSIBLE_COW_PATH": os.getenv(
                "ANSIBLE_COW_PATH", shutil.which("cowsay") or ""
            ),
            "ANSIBLE_ACTION_WARNINGS": str(int(verbosity > 0)),
            "ANSIBLE_DEVEL_WARNING": str(int(verbosity > 0)),
        }
        self._td.create_config(
            cowsay_enabled_stencils="default,sheep,moose",
            stdout_callback="deployment_plugin",
            callback_plugins=str(plugin_path),
            host_key_checking="False",
            retry_files_enabled="False",
            nocows=str(bool(int(self._no_cowsay))).lower(),
            action_warnings=str(verbosity > 0).lower(),
            devel_warning=str(verbosity > 0).lower(),
            cowpath=os.getenv("ANSIBLE_COW_PATH", shutil.which("cowsay") or ""),
            cow_selection="random",
            interpreter_python="auto_silent",
            timeout="15",
        )
        logger.debug("CONFIG\n%s", self._td.ansible_config_file.read_text())
        extravars: dict[str, str] = {
            "ansible_port": str(ssh_port),
            "ansible_config": str(self._td.ansible_config_file),
            "ansible_ssh_args": "-o ForwardX11=no -o StrictHostKeyChecking=no",
        }

        self.passwords = self.get_ansible_password(ask_pass)
        steps = [s for s in self.steps]

        self._set_deployment_methods()
        if skip_version_check is False:
            steps = list(
                set(
                    steps
                    + self.get_steps_from_versions(
                        envvars.copy(),
                        extravars.copy(),
                        self.passwords.copy(),
                        verbosity,
                    )
                )
            )
        inventory = self.parse_config(steps)
        if inventory is None:
            logger.info("Services up to date, nothing to do!")
            return None
        if self.local_debug:
            logger.info("Overriding configuration for local deployment!")
            extravars["ansible_connection"] = "local"
        logger.debug(inventory)
        self.create_eval_config()
        RichConsole.rule(
            f"[r]Playing tasks: [i]{', '.join(tags or steps)}[/] with ansible[/]"
        )
        time.sleep(3)
        self._td.run_ansible_playbook(
            working_dir=asset_dir,
            playbook=asset_dir / "playbooks" / "main-deployment.yml",
            inventory=inventory,
            envvars=envvars,
            tags=tags or steps,
            passwords=self.passwords,
            extravars=extravars,
            verbosity=verbosity,
        )
        if self.local_debug:
            RichConsole.rule("[b red]:bulb:   NOTE:[/]")
            RichConsole.print(
                LOCAL_DEBUG_MSG.format(
                    project_name=self.project_name,
                    user=getuser(),
                    password=self.master_pass,
                )
            )
            RichConsole.rule("")
