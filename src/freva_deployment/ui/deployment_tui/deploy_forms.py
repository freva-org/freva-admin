from __future__ import annotations

from getpass import getuser
from pathlib import Path
from typing import Any, List, cast

import npyscreen

from freva_deployment import AVAILABLE_CONDA_ARCHS
from freva_deployment.utils import get_current_file_dir

from .base import (
    BaseForm,
    CheckboxInfo,
    ComboInfo,
    DictInfo,
    FileInfo,
    TextInfo,
)

DEPLOYMENT_METHODS = ["docker", "podman", "conda", "k8s"]
EXPOSE_METHODS = ["op-lb", "saas-lb", "hostport"]


def get_index(values: list[str], target: str, default: int = 0) -> int:
    """Get the target index of item in list.

    Parameters:
    ===========
    values:
        the list of values that is searched
    target:
        the item the list of values that is searched for
    default:
        if nothing is found return the default value

    Returns:
    ========
    int: Index of the the target item in the list
    """

    for n, value in enumerate(values):
        if value == target:
            return n
    return default


class CoreScreen(BaseForm):
    """Form for the core deployment configuration."""

    step: str = "core"
    """Name of this step."""
    certificates: list[str] = ["public"]
    """The type of certificate files this step needs."""

    @property
    def scheduler_systems(self):
        """Define available scheduler systems."""
        return ["local", "slurm", "pbs", "lfs", "moab", "oar", "sge"]

    def scheduler_index(self, scheduler_system: str = ""):
        """Get the index of the saved scheduler_system"""
        scheduler_system = scheduler_system or "local"
        for nn, choice in enumerate(self.scheduler_systems):
            if choice == scheduler_system:
                return nn
        return 0

    def _add_widgets(self) -> None:
        """Add widgets to the screen."""
        self.list_keys: list[str] = []
        cfg = self.get_config(self.step)
        arch = cast(str, cfg.get("arch", AVAILABLE_CONDA_ARCHS[0]))
        arch_idx = get_index(AVAILABLE_CONDA_ARCHS, arch, 0)
        self.input_fields: dict[str, tuple[npyscreen.TitleText, bool]] = dict(
            core_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="hosts",
                    name=f"{self.num}Server Name(s) where core is deployed",
                    value=cfg.get("core_host"),
                ),
                True,
            ),
            install_dir=(
                self.add_widget_intelligent(
                    FileInfo,
                    section="core",
                    key="install_dir",
                    name=f"{self.num}Anaconda installation dir. for core",
                    value=cfg.get("install_dir", ""),
                ),
                True,
            ),
            root_dir=(
                self.add_widget_intelligent(
                    FileInfo,
                    section="core",
                    key="root_dir",
                    name=(f"{self.num}Freva configuration directory"),
                    value=cfg.get("root_dir", ""),
                ),
                False,
            ),
            base_dir_location=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="base_dir_location",
                    name=(f"{self.num}User data directory"),
                    value=cfg.get("base_dir_location", ""),
                ),
                False,
            ),
            preview_path=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="preview_path",
                    name=(f"{self.num}Plugin output dir for the web UI. "),
                    value=cfg.get("preview_path", ""),
                ),
                False,
            ),
            scheduler_system=(
                self.add_widget_intelligent(
                    ComboInfo,
                    section="core",
                    key="scheduler_system",
                    name=f"{self.num}Workload manager",
                    value=self.scheduler_index(
                        cast(str, cfg.get("scheduler_system"))
                    ),
                    values=self.scheduler_systems,
                ),
                True,
            ),
            scheduler_output_dir=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="scheduler_output_dir",
                    name=f"{self.num}Output dir. of the scheduler system",
                    value=cfg.get("scheduler_output_dir", ""),
                ),
                False,
            ),
            admins=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="admins",
                    name=f"{self.num}Set the admin user(s) - comma separated",
                    value=cfg.get("admins", getuser()),
                ),
                False,
            ),
            admin_group=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="admin_group",
                    name=(
                        f"{self.num}Set the Freva admin group - "
                        "leave blank if not needed"
                    ),
                    value=cfg.get("admin_group", ""),
                ),
                False,
            ),
            ansible_become_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="ansible_become_user",
                    name=(
                        f"{self.num}Become (sudo) user name to change to on "
                        "remote machine"
                    ),
                    value=cfg.get("ansible_become_user", ""),
                ),
                False,
            ),
            arch=(
                self.add_widget_intelligent(
                    ComboInfo,
                    section="core",
                    key="arch",
                    name=(f"{self.num}Set the target architecture"),
                    value=arch_idx,
                    values=AVAILABLE_CONDA_ARCHS,
                ),
                True,
            ),
            ansible_python_interpreter=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="ansible_python_interpreter",
                    name=f"{self.num}Python path on remote machine",
                    value=cfg.get(
                        "ansible_python_interpreter", "/usr/bin/python3"
                    ),
                ),
                False,
            ),
            ansible_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="core",
                    key="ansible_user",
                    name=f"{self.num}Username for remote machine",
                    value=cfg.get("ansible_user", getuser()),
                ),
                False,
            ),
        )


class WebScreen(BaseForm):
    """Form for the web deployment configuration."""

    step: str = "web"
    certificates: list[str] = ["public", "private"]
    """The type of certificate files this step needs."""

    def get_index(self, choices: list[str], key: str):
        """Get the key value pair for a combo box"""
        for nn, choice in enumerate(choices):
            if choice == key:
                return nn
        return 0

    def _add_widgets(self) -> None:
        """Add widgets to the screen."""
        self.list_keys = "imprint", "scheduler_host", "allowed_hosts"
        cfg = self.get_config(self.step)

        for key in self.list_keys:
            if key in cfg and isinstance(cfg[key], str):
                value = cast(str, cfg[key])
                cfg[key] = [v.strip() for v in value.split(",") if v.strip()]
        self.input_fields: dict[str, tuple[npyscreen.TitleText, bool]] = dict(
            web_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="web_host",
                    name=f"{self.num}Hostname where web service is deployed on",
                    value=cfg.get("web_host"),
                ),
                True,
            ),
            data_path=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="data_path",
                    name=f"{self.num}Parent directory for any permanent data",
                    value=cast(str, cfg.get("data_path", "/opt/freva")),
                ),
                True,
            ),
            admin_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="admin_user",
                    name=(f"{self.num}User name that should own persistent data"),
                    value=cfg.get("admin_user", ""),
                ),
                False,
            ),
            project_website=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="project_website",
                    name=f"{self.num}Url of the Freva home page",
                    value=cfg.get("project_website", ""),
                ),
                True,
            ),
            chatbot_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="chatbot_host",
                    name=f"{self.num}Url to the FrevaGPT service",
                    value=cfg.get("chatbot_host", ""),
                ),
                False,
            ),
            main_color=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="main_color",
                    name=f"{self.num}Html color of the main color theme",
                    value=cfg.get("main_color", "Tomato"),
                ),
                True,
            ),
            border_color=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="border_color",
                    name=f"{self.num}Html color for the borders",
                    value=cfg.get("border_color", "#6c2e1f"),
                ),
                True,
            ),
            hover_color=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="hover_color",
                    name=f"{self.num}Html color for hover modes",
                    value=cfg.get("hover_color", "#d0513a"),
                ),
                True,
            ),
            institution_logo=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="institution_logo",
                    name=f"{self.num}Path to the institution logo",
                    value=cfg.get(
                        "institution_logo", "/path/to/logo/on/target/machine"
                    ),
                ),
                True,
            ),
            about_us_text=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="about_us_text",
                    name=f"{self.num}About us text - short blurb about Freva",
                    value=cfg.get("about_us_text", "Testing"),
                ),
                True,
            ),
            contacts=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="contacts",
                    name=f"{self.num}Contact email address",
                    value=str(cfg.get("contacts", "freva@dkrz.de")),
                ),
                True,
            ),
            imprint=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="imprint",
                    name=f"{self.num}Institution address - comma separated",
                    value=",".join(
                        cast(
                            List[str],
                            cfg.get(
                                "imprint",
                                [
                                    "freva",
                                    "German Climate Computing Centre (DKRZ)",
                                    "Bundesstr. 45a",
                                    "20146 Hamburg",
                                    "Germany",
                                ],
                            ),
                        ),
                    ),
                ),
                True,
            ),
            homepage_text=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="homepage_text",
                    name=f"{self.num}More in detail project description",
                    value=cfg.get(
                        "homepage_text",
                        (
                            "Lorem ipsum dolor sit amet, consectetur "
                            "adipiscing elit, sed do eiusmod tempor "
                            "incididunt ut labore et dolore magna aliqua. "
                            "Ut enim ad minim veniam, quis nostrud "
                            "exercitation ullamco laboris nisi ut aliquip "
                            "ex ea commodo consequat. Duis aute irure dolor "
                            "in reprehenderit in voluptate velit esse cillum "
                            "dolore eu fugiat nulla pariatur. Excepteur sint "
                            "occaecat cupidatat non proident, sunt in culpa "
                            "qui officia deserunt mollit anim id est laborum."
                        ),
                    ),
                ),
                True,
            ),
            homepage_heading=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="homepage_heading",
                    name=f"{self.num}A brief description of the project",
                    value=cfg.get(
                        "homepage_heading", "Lorem ipsum dolor sit amet"
                    ),
                ),
                True,
            ),
            scheduler_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="scheduler_host",
                    name=f"{self.num}Scheduler hostname(s) - comma separated",
                    value=",".join(
                        cast(
                            List[str],
                            cfg.get("scheduler_host", ["levante.dkrz.de"]),
                        )
                    ),
                ),
                True,
            ),
            allowed_hosts=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="allowed_hosts",
                    name=f"{self.num}Set additional hostnames django can serve",
                    value=",".join(
                        cast(
                            List[str],
                            cfg.get("allowed_hosts", ["localhost"]),
                        ),
                    ),
                ),
                True,
            ),
            ansible_become_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="ansible_become_user",
                    name=(
                        f"{self.num}Become (sudo) user name to change to on "
                        "remote machine"
                    ),
                    value=cfg.get("ansible_become_user", "root"),
                ),
                False,
            ),
            ansible_python_interpreter=(
                self.add_widget_intelligent(
                    FileInfo,
                    section="web",
                    key="ansible_python_interpreter",
                    name=f"{self.num}Pythonpath on remote machine",
                    value=cfg.get(
                        "ansible_python_interpreter", "/usr/bin/python3"
                    ),
                ),
                False,
            ),
            ansible_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="web",
                    key="ansible_user",
                    name=f"{self.num}Username for remote machine",
                    value=cfg.get("ansible_user", getuser()),
                ),
                False,
            ),
        )


class DBScreen(BaseForm):
    """Form for the core deployment configuration."""

    step: str = "db"

    def _add_widgets(self) -> None:
        """Add widgets to the screen."""
        self.list_keys: list[str] = []
        cfg = self.get_config(self.step)
        db_ports: list[int] = list(range(3300, 3320))
        port_idx = get_index(
            cast(List[str], list(map(str, db_ports))),
            str(cfg.get("port", 3306)),
            6,
        )
        self.input_fields: dict[str, tuple[npyscreen.TitleText, bool]] = dict(
            db_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="db_host",
                    name=f"{self.num}Hostname where the database service is deployed",
                    value=cfg.get("db_host"),
                ),
                True,
            ),
            vault_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="vault_host",
                    name=f"{self.num}Hostname where the vault service is deployed",
                    value=cfg.get("vault_host") or cfg.get("db_host"),
                ),
                True,
            ),
            wipe=(
                self.add_widget_intelligent(
                    CheckboxInfo,
                    section="db",
                    key="wipe",
                    max_height=2,
                    value=cfg.get("wipe", False),
                    editable=True,
                    name=(f"{self.num}Delete existing data?"),
                    scroll_exit=True,
                ),
                True,
            ),
            user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="user",
                    name=f"{self.num}Database user",
                    value=cfg.get("user", "evaluation_system"),
                ),
                True,
            ),
            db=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="db",
                    name=f"{self.num}Database name",
                    value=cfg.get("db", "evaluation_system"),
                ),
                True,
            ),
            port=(
                self.add_widget_intelligent(
                    ComboInfo,
                    section="db",
                    key="port",
                    name=f"{self.num}Database Port",
                    value=port_idx,
                    values=db_ports,
                ),
                True,
            ),
            data_path=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="data_path",
                    name=(f"{self.num}Parent directory for any permanent data"),
                    value=cast(str, cfg.get("data_path", "/opt/freva")),
                ),
                True,
            ),
            admin_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="admin_user",
                    name=(f"{self.num}User name that should own persistent data"),
                    value=cfg.get("admin_user", ""),
                ),
                False,
            ),
            ansible_become_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="ansible_become_user",
                    name=(
                        f"{self.num}Become (sudo) user name to change to on "
                        "remote machine"
                    ),
                    value=cfg.get("ansible_become_user", "root"),
                ),
                False,
            ),
            ansible_python_interpreter=(
                self.add_widget_intelligent(
                    FileInfo,
                    section="db",
                    key="ansible_python_interpreter",
                    name=f"{self.num}Pythonpath on remote machine",
                    value=cfg.get(
                        "ansible_python_interpreter", "/usr/bin/python3"
                    ),
                ),
                False,
            ),
            ansible_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="db",
                    key="ansible_user",
                    name=f"{self.num}Username for remote machine",
                    value=cfg.get("ansible_user", getuser()),
                ),
                False,
            ),
        )


class FrevaRestScreen(BaseForm):
    """Form for the freva-rest deployment configuration."""

    step: str = "freva_rest"

    def _add_widgets(self) -> None:
        """Add widgets to the screen."""
        self.list_keys: list[str] = []
        cfg = self.get_config(self.step)
        freva_rest_ports: list[int] = list(range(7770, 7780))
        solr_mem_values = [f"{i}g" for i in range(1, 10)]
        solr_mem_select = get_index(
            solr_mem_values, cast(str, cfg.get("solr_mem", "4g")), 3
        )
        freva_rest_port_idx = get_index(
            [str(p) for p in freva_rest_ports],
            str(cfg.get("freva_rest_port", 7777)),
            7,
        )
        self.input_fields: dict[str, tuple[npyscreen.TitleText, bool]] = dict(
            freva_rest_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="freva_rest_host",
                    name=(
                        f"{self.num}Server Name(s) where the "
                        "freva-rest service is deployed"
                    ),
                    value=cfg.get("freva_rest_host", ""),
                ),
                True,
            ),
            search_server_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="redis_host",
                    name=f"{self.num} Set the index server host name",
                    value=cast(
                        str,
                        cfg.get("search_server_host")
                        or cfg.get("freva_rest_host"),
                    ),
                ),
                False,
            ),
            mongodb_server_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="redis_host",
                    name=f"{self.num} Set the mongoDB host name",
                    value=cast(
                        str,
                        cfg.get("mongodb_server_host")
                        or cfg.get("freva_rest_host"),
                    ),
                ),
                False,
            ),
            redis_host=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="redis_host",
                    name=f"{self.num} Set the redis host name",
                    value=cast(
                        str,
                        cfg.get("redis_host") or cfg.get("freva_rest_host"),
                    ),
                ),
                False,
            ),
            wipe=(
                self.add_widget_intelligent(
                    CheckboxInfo,
                    section="freva_rest",
                    key="wipe",
                    max_height=2,
                    value=cfg.get("wipe", False),
                    editable=True,
                    name=(f"{self.num}Delete existing data?"),
                    scroll_exit=True,
                ),
                True,
            ),
            solr_mem=(
                self.add_widget_intelligent(
                    ComboInfo,
                    section="freva_rest",
                    key="solr_mem",
                    name=(
                        f"{self.num}Virtual memory (in GB) for the search "
                        "engine service"
                    ),
                    value=solr_mem_select,
                    values=solr_mem_values,
                ),
                True,
            ),
            freva_rest_port=(
                self.add_widget_intelligent(
                    ComboInfo,
                    section="freva_rest",
                    key="freva_rest_port",
                    name=f"{self.num}Freva-rest API port",
                    value=freva_rest_port_idx,
                    values=freva_rest_ports,
                ),
                True,
            ),
            admin_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="admin_user",
                    name=(f"{self.num}User name that should own persistent data"),
                    value=cfg.get("admin_user", ""),
                ),
                False,
            ),
            data_path=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="data_path",
                    name=f"{self.num}Parent directory for any permanent data",
                    value=cast(str, cfg.get("data_path", "/opt/freva")),
                ),
                True,
            ),
            data_loader_portal_hosts=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="data_loader_portal_hosts",
                    name=(
                        f"{self.num} ',' separated hostname(s) data-loading portal "
                        "to provide zarr. Leave blank for none"
                    ),
                    value=cast(str, cfg.get("data_loader_portal_hosts", "")),
                ),
                False,
            ),
            oidc_url=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="oidc_url",
                    name=(f"{self.num}Config url of the OIDC service"),
                    value=cast(str, cfg.get("oidc_url", "")),
                ),
                True,
            ),
            oidc_client=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="oidc_client",
                    name=(f"{self.num}Name of the OIDC client (app name)"),
                    value=cast(str, cfg.get("oidc_client", "freva")),
                ),
                True,
            ),
            oidc_client_secret=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="oidc_client_secret",
                    name=(f"{self.num}OIDC client secret. Leave blank for none"),
                    value=cast(str, cfg.get("oidc_client_secret", "")),
                ),
                False,
            ),
            oidc_token_claims=(
                self.add_widget_intelligent(
                    DictInfo,
                    section="freva_rest",
                    key="oidc_token_claims",
                    name=f"{self.num}OIDC authorization filters",
                    value=cast(
                        dict[str, list[str]], cfg.get("oidc_token_claims", {})
                    ),
                ),
                False,
            ),
            ansible_become_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="ansible_become_user",
                    name=(
                        f"{self.num}Become (sudo) user name to change to on "
                        "remote machine"
                    ),
                    value=cfg.get("ansible_become_user", "root"),
                ),
                False,
            ),
            ansible_python_interpreter=(
                self.add_widget_intelligent(
                    FileInfo,
                    section="freva_rest",
                    key="ansible_python_interpreter",
                    name=f"{self.num}Pythonpath on remote machine",
                    value=cfg.get(
                        "ansible_python_interpreter", "/usr/bin/python3"
                    ),
                ),
                False,
            ),
            ansible_user=(
                self.add_widget_intelligent(
                    TextInfo,
                    section="freva_rest",
                    key="ansible_user",
                    name=f"{self.num}Username for remote machine",
                    value=cfg.get("ansible_user", getuser()),
                ),
                False,
            ),
        )


class RunForm(npyscreen.FormMultiPageAction):
    """Definition of the form that applies the actual deployment"""

    _num: int = 0

    @property
    def num(self) -> str:
        """Calculate the number for enumerations of any input field."""
        self._num += 1
        return f"{self._num}. "

    def on_ok(self) -> None:
        """Define what happens once the `ok` for applying the deployment is hit."""

        if not self.project_name.value:
            npyscreen.notify_confirm(
                "You have to set a project name", title="ERROR"
            )
            return
        missing_form: None | str = self.parentApp.check_missing_config()
        if missing_form:
            self.parentApp.change_form(missing_form)
            return
        public_keyfile = self.public_keyfile.value
        cert_files = dict(
            public=public_keyfile or "",
            private=self.private_keyfile.value or "",
        )
        save_file = Path(
            self.parentApp.get_save_file(self.inventory_file.value or None)
        )
        if isinstance(self.gen_keys.value, list):
            gen_keys = bool(self.gen_keys.value[0])
        else:
            gen_keys = bool(self.gen_keys.value)
        for key_type, keyfile in cert_files.items():
            key_file = Path(get_current_file_dir(save_file.parent, str(keyfile)))
            for step, deploy_form in self.parentApp._forms.items():
                if not keyfile or not Path(key_file).is_file():
                    if (
                        key_type in deploy_form.certificates
                        and step in self.parentApp.steps
                        and gen_keys is False
                    ):
                        if keyfile:
                            msg = f"{key_type} certificate file `{key_file}` must exist."
                        else:
                            msg = f"You must give a {key_type} certificate file"
                        npyscreen.notify_confirm(msg, title="ERROR")
                        return
        _ = self.parentApp.save_config_to_file(
            save_file=save_file, write_toml_file=True
        )
        try:
            ssh_port = int(self.ssh_port.value)
        except ValueError:
            ssh_port = 22
        self.parentApp.setup = {
            "steps": list(set(self.parentApp.steps)),
            "ask_pass": bool(self.use_ssh_pw.value),
            "config_file": str(save_file) or None,
            "ssh_port": ssh_port,
            "skip_version_check": bool(self.skip_version_check.value),
            "local_debug": bool(self.local_debug.value),
            "gen_keys": bool(gen_keys),
        }
        self.parentApp.thread_stop.set()
        self.parentApp.exit_application(
            save_file=save_file, msg="Do you want to continue?"
        )

    def on_cancel(self) -> None:
        """Define what happens after the the cancel button is hit."""
        name = self.parentApp.current_form.lower()
        self.parentApp.setup = {}
        for step, form_name in self.parentApp._steps_lookup.items():
            if name.startswith(step):
                # Tell the MyTestApp object to change forms.
                self.parentApp.change_form(form_name)
                return
        self.parentApp.change_form("MAIN")

    def create(self) -> None:
        """Custom definitions executed when the from gets created."""
        self.how_exited_handers[npyscreen.wgwidget.EXITED_ESCAPE] = (
            self.parentApp.exit_application
        )
        self.add_handlers({"^F": self.show_info})
        self._add_widgets()

    def show_info(self, *args: Any, **kwargs: Any) -> None:
        """Display an info if present."""
        if isinstance(self.current_info, str):
            npyscreen.notify_confirm(
                self.current_info, title="Detailed Information"
            )

    def _add_widgets(self) -> None:
        """Add the widgets to the form."""

        project_name = self.parentApp.config.get(
            "project_name", self.parentApp._read_cache("project_name", "")
        )
        self.project_name = self.add_widget_intelligent(
            npyscreen.TitleText,
            name=f"{self.num}Set the name of the project",
            value=project_name,
        )
        self.deployment_method = self.add_widget_intelligent(
            ComboInfo,
            key="deployment_method",
            name=f"{self.num}Deployment Method",
            info=(
                "The `deployment_method` key sets the option of how the "
                "installation of the service is realised. `docker`, "
                "`podman` leverages podman or docker, `conda` uses "
                "conda-forge to install the service while `k8s` "
                "involves a kubernetes based deployment "
                'Chosse between: "docker", "podman", "conda", "k8s"'
            ),
            value=get_index(
                DEPLOYMENT_METHODS,
                cast(
                    str,
                    self.parentApp.config.get("deployment_method", "docker"),
                ),
            ),
            values=DEPLOYMENT_METHODS,
        )
        self.inventory_file = self.add_widget_intelligent(
            npyscreen.TitleFilename,
            name=f"{self.num}Save config as",
            value=str(self.parentApp.save_file or ""),
        )
        self.public_keyfile = self.add_widget_intelligent(
            npyscreen.TitleFilename,
            name=f"{self.num}Select a public certificate file; needed for steps web, core, db",
            value=self.parentApp.read_cert_file("public_keyfile"),
        )
        self.private_keyfile = self.add_widget_intelligent(
            npyscreen.TitleFilename,
            name=f"{self.num}Select a private certificate file; needed for steps web",
            value=self.parentApp.read_cert_file("private_keyfile"),
        )
        self.gen_keys = self.add_widget_intelligent(
            npyscreen.RoundCheckBox,
            max_height=2,
            value=self.parentApp._read_cache("gen_keys", False),
            name=f"{self.num}Generate a pair web certificates, debugging",
        )
        self.k8s_deploy_host = self.add_widget_intelligent(
            TextInfo,
            key="deploy_host",
            section="kubernetes",
            name=f"{self.num}Set a deploy host",
            value=self.parentApp.config.get("kubernetes", {}).get("deploy_host"),
        )

        self.k8s_expose_method = self.add_widget_intelligent(
            ComboInfo,
            key="expose_method",
            section="kubernetes",
            name=f"{self.num}K8s Expose Method",
            value=get_index(
                EXPOSE_METHODS,
                cast(
                    str,
                    self.parentApp.config.get("kubernetes", {}).get(
                        "expose_method",
                        "op-lb",
                    ),
                ),
            ),
            values=EXPOSE_METHODS,
        )
        self.use_ssh_pw = self.add_widget_intelligent(
            npyscreen.RoundCheckBox,
            max_height=2,
            editable=True,
            value=self.parentApp._read_cache("ssh_pw", False),
            name=f"{self.num}Use password for ssh connection",
            scroll_exit=True,
        )
        self.skip_version_check = self.add_widget_intelligent(
            npyscreen.RoundCheckBox,
            max_height=2,
            editable=True,
            value=self.parentApp._read_cache("skip_version_check", False),
            name=f"{self.num}Skip the version check, use with caution",
        )
        self.ssh_port = self.add_widget_intelligent(
            npyscreen.TitleText,
            name=f"{self.num}If you need to, you can change the ssh port here",
            value=str(self.parentApp._read_cache("ssh_port", 22)),
        )
        self.local_debug = self.add_widget_intelligent(
            npyscreen.RoundCheckBox,
            max_height=2,
            value=self.parentApp._read_cache("local_debug", False),
            editable=True,
            name=f"{self.num}Deploy services on the local machine, debug",
        )
