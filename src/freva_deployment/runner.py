"""Ansible runner interaction."""

import atexit
import json
import os
import sys
from copy import deepcopy
from getpass import getuser
from multiprocessing import get_context
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Dict, List, Optional, Union

import paramiko
import yaml
from rich import print as pprint
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner

from .error import DeploymentError
from .logger import logger
from .utils import is_bundeled


def _del_path(inp_path: Path) -> None:
    tmp_path = inp_path.with_suffix(".cfg.tmp")
    if inp_path.is_file():
        inp_path.unlink()
    if tmp_path.is_file():
        inp_path.write_text(tmp_path.read_text())
        tmp_path.unlink()


class SubProcess:
    """Class that holds the exitcode and the stdout of a process."""

    def __init__(
        self, exitcode: Optional[int], stdout: str = "", log: str = ""
    ) -> None:
        self.returncode = exitcode or 0
        self.stdout = stdout
        self.log = log

    @classmethod
    def run_ansible_playbook(
        cls,
        cwd: Path,
        command: List[str],
    ) -> None:
        from ansible.cli.playbook import main

        current_dir = os.path.abspath(os.curdir)
        try:
            os.chdir(cwd)
            main(command)
        finally:
            os.chdir(current_dir)


def run_command(
    cwd: str,
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = False,
):
    os_env = deepcopy(os.environ)
    env = env or {}
    stdout = sys.stdout
    with TemporaryDirectory(prefix="AnsibleRunner") as temp_dir:
        logger_file = Path(temp_dir) / "logger.log"
        logger_file.touch()
        stdout_file = Path(temp_dir) / "stdout.log"
        env["DEPLOYMENT_LOG_PATH"] = str(logger_file)
        stdout_buffer = stdout_file.open("w")
        try:
            os.environ.update(env)
            if capture_output:
                sys.stdout = stdout_buffer
            ctx = get_context()
            proc = ctx.Process(
                target=SubProcess.run_ansible_playbook, args=(cwd, command)
            )
            proc.start()
            proc.join()
        finally:
            os.environ = os_env
            sys.stdout = stdout
            stdout_buffer.close()
        return SubProcess(
            proc.exitcode,
            stdout=stdout_file.read_text(),
            log=logger_file.read_text(),
        )


def run_command_with_spinner(
    cwd: str, command: List[str], env: Dict[str, str], text: str
) -> SubProcess:
    console = Console(stderr=True)
    spinner = Spinner("weather", text=text)

    with Live(spinner, refresh_per_second=3, console=console):
        try:
            result = run_command(cwd, command, env=env, capture_output=True)
        except KeyboardInterrupt:
            spinner.update(text=text + " [yellow]canceled[/yellow]")
            raise KeyboardInterrupt("User interrupted execution") from None

        if result.returncode == 0:
            spinner.update(text=text + " [green]ok[/green]")
        else:
            spinner.update(text=text + " [red]failed[/red]")
    return result


class RunnerDir(TemporaryDirectory):
    """Define and create the Ansible runner directory."""

    def __init__(self) -> None:
        super().__init__(prefix="AnsibleRunner")
        self.parent_dir = Path(self.name)
        self.env_dir = self.parent_dir / "env"
        self.inventory_dir = self.parent_dir / "inventory"
        self.project_dir = self.parent_dir / "project"
        self.aux_file_dir = self.parent_dir / "files"
        for _dir in (self.env_dir, self.inventory_dir, self.project_dir):
            _dir.mkdir(exist_ok=True, parents=True)

        self.ansible_config_file = Path(
            os.getenv("ANSIBLE_CONFIG") or self.parent_dir / "ansible.cfg"
        )
        if self.ansible_config_file.is_file():
            self.ansible_config_file.with_suffix(".cfg.tmp").write_text(
                self.ansible_config_file.read_text()
            )
        atexit.register(_del_path, self.ansible_config_file)

    def create_config(self, **kwargs: str) -> None:
        """Create an ansible config."""
        self.ansible_config_file.parent.mkdir(exist_ok=True, parents=True)
        with open(self.ansible_config_file, "w", encoding="utf-8") as stream:
            stream.write("[defaults]\n")
            for key, value in kwargs.items():
                stream.write(f"{key} = {value}\n")
            stream.write("[colors]\n")
            stream.write("included = purple\n")
            stream.write("skip = green\n")
            stream.write("[callback]\n")
            stream.write("result_format=yaml\n")
            stream.write("pretty_results=True\n")

    def create_playbook(self, content: List[Dict[str, Any]]) -> str:
        """Dump the content of a playbook into the playbook file."""
        for nn, step in enumerate(content):
            host = step.get("hosts", "")
            if not host:
                continue
            for tt, task in enumerate(step.get("tasks", [])):
                try:
                    content[nn]["tasks"][tt]["name"] = f"{host} - {task['name']}"
                except KeyError:
                    pass
        content_str = yaml.safe_dump(content)
        self.playbook_file.write_text(content_str)
        return content_str

    @property
    def ansible_exe(self) -> str:
        """Get the path to the ansible-playbook command."""
        exe = ""
        if sys.platform.lower().startswith("win"):
            exe = ".exe"
        if is_bundeled:
            return str(Path(__file__).parent / "bin" / f"ansible-playbook{exe}")
        else:
            return "ansible-playbook"

    @property
    def inventory_file(self) -> Path:
        """Define the location of the inventory file."""
        return self.project_dir / "hosts"

    @property
    def playbook_file(self) -> Path:
        """Define the location of the playbook file."""
        return self.project_dir / "playbook.yaml"

    def write_to_tempfile(self, content: str) -> str:
        """
        Write the given content to a temporary file and return the file path.
        """
        temp_file = NamedTemporaryFile(
            dir=self.parent_dir, delete=False, mode="w", suffix=".yml"
        )
        temp_file.write(content)
        temp_file.close()
        return temp_file.name

    def convert_to_file(
        self, content: Union[Path, str, List[Any], Dict[str, Any]]
    ) -> str:
        """
        Convert inventory input to a file path. If it is already a path, return it.
        If it is a string or list of dicts, write it to a temporary file and return the path.
        """
        if isinstance(content, Path):
            return str(content)
        if isinstance(content, str):
            if os.path.isfile(content):
                return content
            else:
                return self.write_to_tempfile(content)
        elif isinstance(content, (list, dict)):
            content_str = yaml.dump(json.loads(json.dumps(content)))
            return self.write_to_tempfile(content_str)
        else:
            raise ValueError("Invalid inventory format")

    def get_remote_file_content(
        self,
        host: str,
        *file_paths: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> str:
        """Get the content of a remote file.

        Parameters
        ----------
        host: str
            Remote hostname
        file_paths: str
            The paths to the file containing the target content
        username: str, default: None
            Use this username to log on
        password: str, default: None
            Instead of logging on by ssh key, use a password based log in.

        Returns
        -------
        str: Content of the file
        """
        if not host:
            return ""
        username = username or getuser()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        file_content = ""
        try:
            logger.debug("Connecting to %s with %s", host, username)
            ssh.connect(host, username=username, password=password or None)
            for file_path in file_paths:
                _, stdout, stderr = ssh.exec_command(f"cat {file_path}")
                if stderr.channel.recv_exit_status() == 0:
                    file_content = stdout.read().decode("utf-8").strip()
                    break
        except Exception as error:
            logger.critical(
                "Couldn't establish connection to %s: %s", host, error
            )
        finally:
            ssh.close()
        return file_content

    def run_ansible_playbook(
        self,
        playbook: Optional[Union[str, Path, List[Any], Dict[str, Any]]],
        inventory: Optional[Union[str, Path, List[Any], Dict[str, Any]]],
        working_dir: Optional[Union[str, Path]] = None,
        envvars: Optional[Dict[str, str]] = None,
        extravars: Optional[Dict[str, str]] = None,
        tags: Optional[List[str]] = None,
        cmdline: Optional[str] = None,
        verbosity: int = 0,
        passwords: Optional[Dict[str, str]] = None,
        hide_output: bool = False,
        text: str = "Running playbook ...",
        output: str = "",
    ) -> str:
        """
        Run an Ansible playbook using multiprocessing.

        Parameters:
        working_dir (str): Current working directory for the playbooks.
        playbook_path (str): Path to the playbook.
        inventory_path (str): Path to the inventory file.
        envvars (Optional[Dict[str, str]]): Environment variables to set for Ansible.
        extravars (Optional[Dict[str, str]]): Extra variables to pass to Ansible.
        cmdline (Optional[str]): Extra command line arguments for Ansible.
        verbosity (int): Verbosity level for Ansible output.
        tags (Optional[List[str]]): The roles that should be involved.
        hide_output (bool): Hide stdout and stderr if True, show only on failure.

        Raises:
        DeploymentError: If the Ansible playbook execution fails.
        """
        tags = tags or []
        working_dir = Path(working_dir or "").expanduser().absolute()
        playbook_path = self.convert_to_file(playbook or "")
        inventory_path = self.convert_to_file(inventory or "")
        passwords = passwords or {}
        extravars = extravars or {}
        envvars = envvars or {}
        # Prepare the command

        command = ["ansible-playbook", playbook_path, "-i", inventory_path]
        # Set environment variables
        for tag in tags:
            command += ["-t", tag]
        for key, passwd in passwords.items():
            if passwd:
                envvars[key.upper()] = passwd
                extravars[key] = f'{{{{ lookup("env", "{key.upper()}") }}}}'
        extravars["playbook_tempdir"] = str(self.aux_file_dir)
        # Add extra variables
        for key, value in extravars.items():
            command.append(f"-e {key}='{value}'")

        # Add command line arguments
        if cmdline:
            command.extend(cmdline.split())

        # Add verbosity
        if verbosity > 0:
            command.append("-" + "v" * verbosity)
        logger.debug("Running ansible command %s", " ".join(command))
        # Run the command
        if hide_output and verbosity == 0:
            result = run_command_with_spinner(
                str(working_dir), command, envvars, text
            )
        else:
            result = run_command(
                str(working_dir), command, env=envvars, capture_output=False
            )

        # Determine if the command was successful
        success = result.returncode == 0
        # Raise an error if the playbook execution failed
        if not success:
            pprint(result.stdout)
            raise DeploymentError("Deployment failed!")
        return result.log
