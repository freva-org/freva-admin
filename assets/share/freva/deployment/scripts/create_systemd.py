#!/usr/bin/env python3
import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SYSTEMD_TMPL = dict(
    Unit=dict(
        Description="Start/Stop freva services containers",
        After="network-online.target",
    ),
    Service=dict(
        TimeoutStartSec="35s",
        TimeoutStopSec="35s",
        ExecStartPre='/bin/sh -c "{delete_command}"',
        ExecStart='/bin/sh -c "{container_cmd} {container_args}"',
        ExecStop='/bin/sh -c "{delete_command}"',
        Restart="on-failure",
        RestartSec=5,
        StartLimitBurst=5,
    ),
    Install=dict(WantedBy="default.target"),
)


def parse_args() -> Tuple[str, str, List[str], bool]:
    """Parse the commandline arguments."""

    app = argparse.ArgumentParser(
        prog=sys.argv[0], description="Create a new systemd unit."
    )
    app.add_argument("name", type=str, help="Set the container name")
    app.add_argument(
        "--enable",
        action="store_true",
        default=False,
        help="Enable this unit.",
    )
    app.add_argument("--requires", type=str, nargs="+", default=[])
    app.add_argument(
        "--gracious",
        action="store_true",
        default=False,
        help="Do not restart but only start the unit",
    )
    app.add_argument(
        "--print-unit-only",
        action="store_true",
        default=False,
        help="Only print the unit that would be created and started.",
    )
    args, other = app.parse_known_args()
    enable = args.enable
    if os.environ.get("DEBUG", "false").lower() == "true":
        enable = False
    return (
        " ".join(other),
        args.name,
        args.requires,
        enable,
        args.gracious,
        args.print_unit_only,
    )


def _parse_dict(tmp_dict: Dict[str, Dict[str, str]]) -> str:
    systemd_unit = ""
    for section, keys in tmp_dict.items():
        systemd_unit += "[{}]\n".format(section)
        for key, values in keys.items():
            systemd_unit += "{}={}\n".format(key, values)
    return systemd_unit


def load_unit(
    unit: str,
    content: str,
    enable: bool = True,
    gracious: bool = False,
    print_unit_only: bool = False,
) -> None:
    """Load a given systemd unit."""
    files = (
        "/etc/systemd/system/{}.service".format(unit),
        "~/.local/share/systemd/user/{}.service".format(unit),
    )
    if print_unit_only:
        print(content)
        return
    flags = ("", "--user")
    for file, flag in zip(files, flags):
        out_file = Path(file).expanduser()
        try:
            out_file.parent.mkdir(exist_ok=True, parents=True)
            with out_file.open(mode="w", encoding="utf-8") as f_obj:
                f_obj.write(content)
        except PermissionError:
            continue
        cmd = ["systemctl"]
        if flag:
            cmd += [flag]

        subprocess.run(cmd + ["daemon-reload"], check=True)
        if enable:
            subprocess.run(cmd + ["enable", unit], check=True)
        if gracious:
            subprocess.run(cmd + ["start", unit], check=True)
        else:
            subprocess.run(cmd + ["restart", unit], check=True)
        return


def get_container_cmd(args: str) -> Tuple[str, str]:
    """Get the correct container command for the system."""

    def _get_container_cmd(path: str) -> str:
        prefer = os.getenv("PREFER") or "podman"
        for cmd in (prefer,) + ("podman", "docker"):
            container_cmd = shutil.which(cmd, path=path)
            if container_cmd:
                return cmd
        raise ValueError("Docker or Podman must be installed")

    home_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
    path = (
        os.environ.get("PATH", "")
        + os.pathsep
        + "/usr/local/bin"
        + os.pathsep
        + home_bin
    )
    container_cmd = _get_container_cmd(path)
    args_list = shlex.split(args)
    if "compose" in args_list:
        proc = subprocess.run(
            [container_cmd, "compose"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if "podman" in container_cmd:
            container_cmd = "podman-compose"
            args_list = [a for a in args_list if a != "compose"]
        if proc.returncode != 0:
            _ = args_list.pop(args_list.index("compose"))
            compose_cmd = f"{container_cmd}-compose"
            command = shutil.which(compose_cmd)
            if not command:
                for cmd in ("ensurepip", f"pip install {compose_cmd}"):
                    try:
                        subprocess.check_call(
                            shlex.split("python3 -m " + cmd),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        txt = (
                            f"{container_cmd} is available but not {compose_cmd}"
                            " which should be installed on the system."
                        )
                        print(txt, file=sys.stderr)
                        raise ValueError(txt)
            container_cmd = compose_cmd
    container_path = shutil.which(container_cmd) or container_cmd
    return container_path, " ".join(args_list)


def create_unit(
    args: str,
    unit: str,
    requires: List[str],
    enable: bool,
    gracious: bool,
    print_unit_only: bool = False,
) -> None:
    """Create the systemd unit."""
    container_cmd, container_args = get_container_cmd(args)
    cmd = shlex.split(args)
    if "compose" in cmd and "up" in cmd:
        new_cmd = []
        for word in cmd:
            if word == "up":
                new_cmd.append("down")
            elif word not in ("-d", "--detach"):
                new_cmd.append(word)
        _, delete_command = get_container_cmd(" ".join(new_cmd))
    else:
        _, delete_command = get_container_cmd("rm -f {}".format(unit))
    if delete_command:
        delete_command = "{} {}".format(container_cmd, delete_command)
    else:
        delete_command = ""
    if "docker" in container_cmd:
        SYSTEMD_TMPL["Unit"]["Requires"] = "docker.service"
        SYSTEMD_TMPL["Unit"]["After"] += " docker.service"
    # else:
    #    SYSTEMD_TMPL["Service"]["Environment"] = "PODMAN_USERNS=keep-id"
    for key in ("ExecStart",):
        SYSTEMD_TMPL["Service"][key] = SYSTEMD_TMPL["Service"][key].format(
            container_cmd=container_cmd,
            container_args=container_args,
            unit=unit,
        )
    for key in ("ExecStartPre", "ExecStop"):
        SYSTEMD_TMPL["Service"][key] = SYSTEMD_TMPL["Service"][key].format(
            delete_command=delete_command
        )
    for service in requires:
        for key in ("After", "Requires"):
            try:
                SYSTEMD_TMPL["Unit"][key] += " {}.service".format(service)
            except KeyError:
                SYSTEMD_TMPL["Unit"][key] = " {}.service".format(service)
    load_unit(
        unit,
        _parse_dict(SYSTEMD_TMPL),
        enable,
        gracious=gracious,
        print_unit_only=print_unit_only,
    )


if __name__ == "__main__":
    create_unit(*parse_args())
