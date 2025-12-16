#!/usr/bin/env python3
import argparse
import asyncio
import hashlib
import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request as req
from functools import wraps
from getpass import getuser
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import (
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    ParamSpec,
    Type,
    TypeVar,
)

F = TypeVar("F", bound=Callable)
P = ParamSpec("P")

SERVICE = """[Unit]
Description=Automated freva deployments
After=network.target
Wants=network.target
After=network.target
[Service]
Type=simple
NoNewPrivileges=true
SendSIGKILL=no
KillSignal=SIGTERM
PermissionsStartOnly=true
ExecStart={prefix}/conda/bin/python {prefix}/automation-setup.py
StateDirectory=prefect
Environment="HOME=/var/lib/prefect"
Environment="PREFECT_HOME=/var/lib/prefect"
Environment="PREFECT_API_DATABASE_CONNECTION_URL=sqlite+aiosqlite:////var/lib/prefect/prefect.db?timeout=30"
Environment="PREFECT_API_URL=http://127.0.0.1:8888/api"
StandardOutput=journal
StandardError=journal
StateDirectory=prefect
Environment="PATH={prefix}/conda/bin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin"
EnvironmentFile=/etc/sysconfig/freva-automation.conf
WorkingDirectory={prefix}
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=5
# User=<set user for security>
# Group=<set group for security>

[Install]
WantedBy=multi-user.target
"""


CONFIG = """
freva = "{path}"
"""


def load_env_configs() -> List[Path]:
    env_var = "FREVA_DEPLOYMENT_CONFIG"
    return [
        Path(f.strip()) for f in os.getenv(env_var, "").split(",") if f.strip()
    ]


def mock_decorator(func: Callable[P, F]) -> Callable[P, F]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> F:
        return func(*args, **kwargs)

    return wrapper


try:
    import appdirs
    import toml
    from prefect import flow, get_run_logger, task
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import (
        DeploymentFilter,
        DeploymentFilterName,
    )
    from prefect.exceptions import FailedRun
    from prefect.filesystems import LocalFileSystem

    bootstrap = False
except ImportError as error:
    print(f"[WARNING] Module not found: {error}")
    print("[WARNING] Boot strapping")
    bootstrap = True
    task = flow = mock_decorator


class BootstrapConda:
    """Install conda into the prefix location."""

    def call_from_bootstrap(self):
        """Call the script in a bootstrap env."""
        with tempfile.NamedTemporaryFile(suffix=".py") as temp_f:
            Path(temp_f.name).write_text(sys.stdin.read())
            cmd = [self.executable, temp_f.name]
            env = os.environ.copy()
            env.pop("_CALLED_FROM_BOOTSTRAP", None)
            subprocess.check_call(cmd, env=env)

    def __init__(
        self, prefix: Path, extra_pkgs: Optional[List[str]] = None
    ) -> None:
        extra_pkgs = extra_pkgs or []
        prefix = prefix.expanduser().absolute()
        micromamba = prefix / "bin" / "micromamba"
        self.prefix = prefix
        pkgs = list(
            set(
                ["appdirs", "prefect", "caddy", "toml", "python=3.12", "git"]
                + extra_pkgs
            )
        )
        if not micromamba.is_file():
            self._setup_micromamba()
        conda_env = prefix / "conda"
        self.executable = str(prefix / "conda" / "bin" / "python")
        if not conda_env.is_dir():
            subprocess.check_call(
                [
                    f"{micromamba}",
                    "create",
                    "-y",
                    "-p",
                    f"{conda_env}",
                    "-c",
                    "conda-forge",
                    "--override-channels",
                ]
                + pkgs
            )
            subprocess.check_call([self.executable, "-m", "ensurepip"])

    def _setup_micromamba(self):
        system = platform.system().lower()
        plt = platform.machine()
        target = self.prefix / "bin" / "micromamba"
        if system != "linux":
            raise SystemExit("Only Linux based deployment is supported.")
        if plt.startswith("x86"):
            plt = "64"
        with NamedTemporaryFile(suffix=".tar") as temp_f:
            self._url_retrieve(
                f"https://micro.mamba.pm/api/micromamba/linux-{plt}/latest",
                temp_f.name,
            )
            with tarfile.open(temp_f.name, mode="r:bz2") as tar:
                member = tar.getmember("bin/micromamba")
                print("🔧 Extracting: bin/micromamba")
                tar.extract(member, path=str(self.prefix))
        target.chmod(0o755)

    def _url_retrieve(self, conda_url: str, target: str) -> None:
        print("Retrieving conda install script: {}".format(conda_url))
        req.urlretrieve(
            str(conda_url),
            filename=target,
        )


__version__ = "0.1.0"
SCRIPT_URL = "https://raw.githubusercontent.com/freva-org/freva-admin/refs/heads/main/automation/automation-setup.py"
SCRIPT_CHECKSUM = (
    "c2bcfa7702a46d753748fea4c8a21daf2c79b32ef924cef280c1c53d6f9fdf89"
)

Steps = Literal["core", "freva-rest", "db", "web"]


def project_type() -> Type:

    try:
        import toml
    except ImportError:
        return Literal["freva"]
    cfg_file = Path(__file__).parent / "freva-automation.toml"
    projects = list(toml.load(cfg_file).keys())
    if not projects:
        return Literal["freva"]
    return Literal[*projects]


def get_env_vars() -> Dict[str, str]:
    envs = dict(os.environ.copy())
    if envs.get("FREVA_AUTOMATION_ENV_FILE"):
        content = Path(envs["FREVA_AUTOMATION_ENV_FILE"]).read_text()
        for line in content.splitlines():
            key, _, value = line.partition("=")
            if key.strip() and value.strip():
                envs[key.strip()] = value.strip()
    envs["INTERACTIVE_DEPLOY"] = "0"
    envs["PATH"] = os.path.dirname(sys.executable) + os.pathsep + envs["PATH"]
    envs["MASTER_PASSWD"] = envs["FREVA_AUTOMATION_PASSWORD"]
    return envs


@task
def update_deployment_software():
    return
    subprocess.check_output(
        [sys.executable, "-m", "pip", "install", "-U", "freva-deployment"]
    )


@task
def run_scripts(script_path: Path, prefix: str = "*"):

    logger = get_run_logger()
    for path in script_path.glob(f"{prefix}.sh"):
        try:
            PrefectServer.execute(["sh", str(path.absolute())])
        except subprocess.CalledProcessError as error:
            logger.error("Could not execute script: %s", path)


@task
def run_deployment(
    config_file: Path,
    steps: List[Steps],
    gen_certs: bool = False,
    use_ssh_pass: bool = False,
    verbosity: int = 0,
    skip_version_check: bool = False,
    extra: Optional[List[str]] = None,
):
    extra = extra or []
    steps = steps or ["auto"]
    cmd = ["deploy-freva", "cmd", "-c", f"{config_file}"]
    if verbosity:
        cmd.append("-" + "v" * verbosity)
    if use_ssh_pass:
        cmd.append("--ask-pass")
    if gen_certs:
        cmd.append("-g")
    if skip_version_check:
        cmd.append("--skip-version-check")
    cmd += ["-s"] + steps
    for ex in extra:
        key, _, value = ex.partition("=")
        if key and value:
            cmd += ["-e", key.strip(), value.strip()]

    PrefectServer.execute(cmd)


@flow
def freva_deployment_flow(
    project: project_type(),
    steps: Optional[List[Steps]] = None,
    gen_certs: bool = False,
    verbosity: int = 0,
    use_ssh_pass: bool = False,
    skip_version_check: bool = False,
    extra: Optional[List[str]] = None,
):
    """
    Apply the freva deployment for a Project.

    Args:
        project: The freva project that should be deployed.
        steps: The steps that should be run.
        gen_certs: Auto generate self signed keys.
        verbosity: Set the verbosity level.
        skip_version_check: Skip checking the micro server versions.
        use_ssh_pass: Instead of trying to connect via ssh keys, use a ssh password
        extra: Any config items that should be overridden.
    """
    update_deployment_software()
    if os.getenv("SCRIPT_PATH"):
        run_scripts(Path(os.getenv("SCRIPT_PATH")))
    steps = steps or ["auto"]
    config = toml.loads(
        (Path(__file__).parent / "freva-automation.toml").read_text()
    )
    run_deployment(
        config[project],
        steps,
        gen_certs,
        use_ssh_pass,
        verbosity,
        skip_version_check=skip_version_check,
        extra=extra,
    )


def get_user_config_dir(appname: str) -> Path:
    if sys.platform.startswith("win"):
        base = os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    cfg_dir = Path(base) / appname
    cfg_dir.mkdir(exist_ok=True, parents=True)
    return cfg_dir


class PrefectServer:
    """Start the prefect server."""

    @staticmethod
    def execute(cmd):
        """Execute a command and log the stdout to the prefect logger."""

        logger = get_run_logger()
        logger.info("Running : %s", " ".join(cmd))
        env = get_env_vars()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=env,
        )
        assert proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            s_line = (line or "").rstrip().strip()
            if s_line:
                logger.info(s_line)
        if proc.returncode != 0:
            stderr_output = proc.stderr.read()
            logger.error(
                "Process %s exited with code : %i", " ".join(cmd), proc.returncode
            )
            logger.error("Captured stderr:\n%s", stderr_output.strip())
            raise FailedRun(f"{' '.join(cmd)} exited: {proc.returncode}")

    def __init__(
        self,
        log_dir: Path,
        api_port: int,
        web_port: Optional[int] = None,
        endpoint: Optional[str] = None,
    ) -> None:

        self.caddy_bin = shutil.which(
            "caddy", path=str(Path(sys.executable).parent)
        )
        self.username = os.getenv("FREVA_AUTOMATION_USERNAME")
        self.password = os.getenv("FREVA_AUTOMATION_PASSWORD")
        if not self.username or not self.password:
            raise SystemExit(
                "FREVA_AUTOMATION_USERNAME and FREVA_AUTOMATION_PASSWORD must be set"
            )

        if not self.caddy_bin:
            raise SystemExit("Caddy bin not found.")
        if web_port is None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                self.port = s.getsockname()[1]
        else:
            self.port = web_port
        self.api_port = api_port
        log_dir.mkdir(exist_ok=True, parents=True)

        self.caddy_dir = Path(tempfile.mkdtemp(prefix="caddy-config-"))
        self.log_dir = log_dir
        self.server_log = (log_dir / "prefect-server.log").open("w")
        self.agent_log = (log_dir / "prefect-agent.log").open("w")
        self.caddy_log = (log_dir / "caddy.log").open("w")
        self.env = os.environ.copy()
        self.caddy_host = f"{socket.gethostname()}:{self.api_port}"
        self.prefect_api_url = f"http://127.0.0.1:{self.port}/api"
        self.env["PREFECT_API_URL"] = self.prefect_api_url
        if endpoint:
            self.env["PREFECT_UI_API_URL"] = (
                f"https://{self.caddy_host}/{endpoint}/api"
            )
        else:
            self.env["PREFECT_UI_API_URL"] = f"https://{self.caddy_host}/api"

    def linger(self) -> None:
        """Wait until the server gets terminated."""
        try:
            while True:
                server_status = self.server.poll()
                agent_status = self.agent.poll()
                if server_status is not None or agent_status is not None:
                    break
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            pass
        self.server.terminate()
        self.agent.terminate()
        self.server_log.close()
        self.agent_log.close()

    def prep_server(
        self, script_path: Path, user_var: Optional[str] = None
    ) -> None:
        """Prepare the server startup."""
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "freva-deployment"]
        )
        from freva_deployment.utils import config_file

        if user_var:
            config_dir = Path(appdirs.user_config_dir("freva")) / "deployment"
            config_dir.mkdir(exist_ok=True, parents=True)
            config = {"general": {}, "variables": {"USER": user_var}}
            config_file.write_text(toml.dumps(config))

        if not script_path.is_dir():
            print("[WARNING] Script path is not a directory.")
            return
        for path in script_path.glob("*.sh"):
            try:
                subprocess.run(
                    ["sh", str(path.absolute())],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    env=get_env_vars(),
                )
            except subprocess.CalledProcessError as error:
                print(f"[WARNING] Failed to execute {path}: {error.stderr}")

    def start_caddy(
        self,
        cert_file: Optional[Path] = None,
        key_file: Optional[Path] = None,
    ) -> None:
        """Create and launch Caddy reverse proxy with basic auth."""
        if cert_file is None or key_file is None:
            from freva_deployment.keys import RandomKeys

            keys = RandomKeys("freva-automation", socket.gethostname())
            key_file = Path("freva-automation.key").absolute()
            cert_file = Path("freva-automation.crt").absolute()
            key_file.write_text(Path(keys.private_key_file).read_text())
            cert_file.write_text(Path(keys.public_chain_file).read_text())

        # Generate bcrypt hash
        hashed_password = subprocess.check_output(
            [self.caddy_bin, "hash-password", "--plaintext", self.password],
            text=True,
        ).strip()
        # Create temp dir for Caddy config
        caddyfile = self.caddy_dir / "Caddyfile"
        caddyfile.write_text(
            f"""{{
    auto_https disable_redirects

}}

{self.caddy_host} {{
    reverse_proxy 127.0.0.1:{self.port}
    tls {cert_file} {key_file}
    basicauth / {{
        {self.username} {hashed_password}
    }}
}}

:8080 {{
    redir https://{self.caddy_host}{{uri}} permanent
}}"""
        )
        subprocess.check_call(
            [self.caddy_bin, "fmt", "--overwrite", "--config", str(caddyfile)],
            env=self.env,
        )
        self.caddy = subprocess.Popen(
            [
                self.caddy_bin,
                "run",
                "--config",
                str(caddyfile),
                "--adapter",
                "caddyfile",
            ],
            stdout=self.caddy_log,
            stderr=self.caddy_log,
            env=self.env,
        )
        print("[INFO] Reverse proxy started visit: " f"https://{self.caddy_host}")

    def stop_server(self) -> None:
        """Stop all services."""
        for attr in ("server", "agent", "caddy"):
            proc = getattr(self, attr, None)
            if proc:
                proc.terminate()
            log = getattr(self, f"{attr}_log", None)
            if log:
                log.close()

    def start_prefect(self) -> None:
        """Start the prefect server."""
        subprocess.check_call(
            [sys.executable, "-m", "prefect", "server", "stop"], env=self.env
        )
        print("[INFO] Starting Prefect server...")
        self.server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "prefect",
                "server",
                "start",
                "--port",
                f"{self.port}",
                "--host",
                "127.0.0.1",
            ],
            stdout=self.server_log,
            stderr=self.server_log,
            env=self.env,
        )
        time.sleep(10)
        print("[INFO] Starting Prefect agent...")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "prefect",
                "work-pool",
                "create",
                "--overwrite",
                "--type",
                "process",
                "default-agent-pool",
            ],
            env=self.env,
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "prefect",
                "block",
                "register",
                "-m",
                "prefect.filesystems",
            ],
            env=self.env,
        )
        self.agent = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "prefect",
                "worker",
                "start",
                "--pool",
                "default-agent-pool",
            ],
            env=self.env,
            stdout=self.agent_log,
            stderr=self.agent_log,
        )
        time.sleep(5)
        print(f"[INFO] Prefect web app started at: http://localhost:{self.port}")


def write_config(config: dict, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as stream:
        toml.dump(config, stream)


async def delete_existing_deployment(name: str):
    """Delete existing deployments."""
    async with get_client() as client:
        deployments = await client.read_deployments(
            deployment_filter=DeploymentFilter(
                name=DeploymentFilterName(any_=[name])
            )
        )
        for dep in deployments:
            await client.delete_deployment(dep.id)
            print(f"[INFO] Deleted existing deployment: {dep.id}")


def register_prefect_deployment(
    name: str = "Freva Deployments",
) -> None:
    basepath = Path(__file__).parent.absolute()

    LocalFileSystem(
        basepath=str(basepath),
    ).save(name="freva-local", overwrite=True)
    LocalFileSystem.load("freva-local")

    this_file = Path(__file__).name
    asyncio.run(delete_existing_deployment(name))
    freva_deployment_flow.from_source(
        source=Path(__file__).parent,
        entrypoint=f"{this_file}:freva_deployment_flow",
    ).deploy(
        name=name,
        tags=["Deployment"],
        work_pool_name="default-agent-pool",
    )


# --- Self-update & checksum logic ---
def self_update(script_url: str, destination: Path):

    print(f"[INFO] Downloading latest script from: {script_url}")
    with req.urlopen(script_url) as response:
        content = response.read()
        destination.write_bytes(content)
    print(f"[INFO] Script updated at: {destination}")
    os.chmod(destination, 0o755)


def calculate_checksum(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# --- CLI
def main():
    parser = argparse.ArgumentParser(
        description="Prepare Freva config and register Prefect.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--prefix",
        "-p",
        help="The path where the automation should be deployed to.",
        type=Path,
        default=Path(
            os.getenv("FREVA_AUTOMATION_PREFIX_DIR") or Path(__file__).parent
        ),
    )
    parser.add_argument(
        "--config",
        "-c",
        nargs="*",
        help="Path(s) to the deployment files.",
        default=load_env_configs(),
    )
    parser.add_argument(
        "--version", action="store_true", help="Show script version and exit"
    )
    parser.add_argument(
        "--self-update",
        action="store_true",
        help="Fetch and replace script with latest version",
    )
    parser.add_argument(
        "--verify-checksum",
        action="store_true",
        help="Verify SHA256 checksum of script",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=os.getenv("FREVA_AUTOMATION_SERVER_PORT", "4200"),
        help="Set the port to run the server.",
    )
    parser.add_argument(
        "--extra-pkg",
        type=str,
        default=os.getenv("FREVA_AUTOMATION_EXTRA_PGKS") or None,
        help="Extra conda-forge packages that need to be installed. "
        "',' separated.",
    )
    parser.add_argument(
        "--script-directory",
        type=Path,
        default=os.getenv("FREVA_AUTOMATION_SCRIPT_DIR", "."),
        help="The directory that contains any pre-processing scripts "
        "that should be executed before launching the automation "
        "server.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=os.getenv("ANSIBLE_USER") or getuser(),
        help="If the deployment config file defines the `USER` variable. "
        "you can set the value of this variable here.",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("FREVA_AUTOMATION_SERVER_ENDPOINT") or None,
        help="Set the reverse proxy endpoint that serves the web app.",
    )
    parser.add_argument(
        "--cert-file",
        type=Path,
        default=os.getenv("FREVA_AUTOMATION_CERT_FILE") or None,
        help="Path to the web server certificate file.",
    )
    parser.add_argument(
        "--key-file",
        type=Path,
        default=os.getenv("FREVA_AUTOMATION_KEY_FILE") or None,
        help="Path to the web server private key file.",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=os.getenv("FREVA_AUTOMATION_WEB_PORT") or None,
        help="Port the web app should be running on. This is useful if you "
        "don't want to spawn a revers porxy but use an existing one.",
    )
    parser.add_argument(
        "--no-reverse-proxy",
        action="store_true",
        help="Do not start a caddy reverse proxy.",
    )
    args = parser.parse_args()
    port = int(args.port)
    script_path = Path(__file__).resolve()
    extra_pkgs = [
        pkg.strip() for pkg in (args.extra_pkg or "").split(",") if pkg.strip()
    ]
    prefix = args.prefix.absolute().expanduser()
    if bootstrap or not (prefix / "conda" / "bin" / "prefect").is_file():
        service = prefix / "freva-automation.service"
        config = prefix / "freva-automation.toml"
        args.prefix.mkdir(exist_ok=True, parents=True)
        script_path = prefix / "automation-setup.py"
        if not script_path.is_file() or not Path(sys.argv[0]).is_file():
            script_path.write_text(sys.stdin.read())
        if not service.is_file():
            service.write_text(SERVICE.format(prefix=prefix))
        if not config.is_file():
            config.write_text(
                CONFIG.format(
                    path=os.getenv(
                        "FREVA_CONFIG_PATH", "/path/to/freva-config.toml"
                    )
                )
            )
        BootstrapConda(args.prefix, extra_pkgs)
        print(
            "Boot strapping success.\n"
            f"Check systemd {service} and {config} config file."
        )
        return

    if args.version:
        print(f"freva_setup.py version {__version__}")
        return

    if args.verify_checksum:
        actual = calculate_checksum(script_path)
        expected = SCRIPT_CHECKSUM.lower()
        print(f"[INFO] SHA256: {actual}")
        if actual == expected:
            print("[INFO] Checksum verified.")
            return
        else:
            raise SystemExit("[ERROR] Checksum mismatch!")

    if args.self_update:
        self_update(SCRIPT_URL, script_path)
        sys.exit(0)

    # Main execution
    log_dir = prefix / "log"
    log_dir.mkdir(exist_ok=True, parents=True)
    env = os.environ.copy()
    try:
        os.environ["SCRIPT_PATH"] = str(args.script_directory or "")
        with tempfile.NamedTemporaryFile(suffix=".conf") as temp_f:
            os.environ["FREVA_AUTOMATION_ENV_FILE"] = temp_f.name
            Path(temp_f.name).write_text(
                "\n".join(f"{e}={v}" for e, v in os.environ.items())
            )
            ps = PrefectServer(
                log_dir, port, web_port=args.web_port, endpoint=args.endpoint
            )
            ps.prep_server(args.script_directory.expanduser(), args.user)
            ps.start_prefect()
            register_prefect_deployment()
            if args.no_reverse_proxy is False:
                ps.start_caddy(args.cert_file, args.key_file)
            ps.linger()
    finally:
        os.environ = env
        try:
            ps.stop_server()
        except UnboundLocalError:
            pass


if __name__ == "__main__":
    main()
