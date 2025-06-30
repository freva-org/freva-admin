"""Command line interface for the configuration."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Optional

import tomlkit
from rich.console import Console
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from freva_deployment import __version__

from ..utils import config_dir, load_config


def _get_config(parser: argparse.Namespace) -> None:
    """Display config."""
    error_console = Console(markup=True, force_terminal=True, stderr=True)
    std_console = Console(markup=True, force_terminal=True)
    try:
        cfg = load_config(parser.config_file)
    except Exception as error:
        if parser.verbose > 0:
            raise
        error_console.print(f"[b]:warning:  {error}[/b]")
        raise SystemExit(1)
    if not parser.keys:
        if parser.raw:
            print(parser.config_file.read_text())
        else:
            std_console.print(parser.config_file.read_text())
        return
    for key in parser.keys:
        section, _, value = key.partition(".")
        try:
            sec = cfg[section]
            if value:
                disp = sec[value]
            else:
                disp = sec
        except Exception as error:
            error_console.print(f"[b red]:warning:  {error}[/b red]")
            continue
    try:
        disp_dump = tomlkit.dumps(disp)
    except Exception:
        disp_dump = disp
    if parser.raw:
        print(disp_dump)
    else:
        std_console.print(disp_dump)


def _set_config(parser: argparse.Namespace) -> None:
    """Set config."""
    default_config_file = config_dir / "config" / "inventory.toml"

    error_console = Console(markup=True, force_terminal=True, stderr=True)
    if parser.config_file == default_config_file:
        error_console.print(
            "[b]:warning:  Using system default config, which will overridden "
            "on update.[/b]"
        )
    try:
        cfg = load_config(parser.config_file)
    except Exception as error:
        if parser.verbose > 0:
            raise
        error_console.print(f"[b]:warning:  {error}[/b]")
        raise SystemExit(1)
    default_config = tomlkit.loads(default_config_file.read_text())
    for keys, value in parser.values:
        section, _, key = keys.partition(".")
        if key:
            default = default_config.get(section, {}).get(key)
        else:
            default = default_config.get(section)
        try:
            cfg_value: Any = ""
            if isinstance(default, bool):
                if value.lower() == "false":
                    cfg_value = False
                else:
                    cfg_value = True
            elif isinstance(default, int) and value.isdigit():
                cfg_value = int(value)
            elif isinstance(default, float) and value.isdigit():
                cfg_value = float(value)
            elif isinstance(default, str):
                cfg_value = value
            else:
                cfg_value = tomlkit.loads(f"foo={value}")["foo"]
            if key:
                cfg[section][key] = cfg_value
            else:
                cfg[section] = cfg_value
        except Exception as error:
            if parser.verbose > 0:
                raise
            error_console.print(f"[b red]:warning:  {error}[/b red]")
            raise SystemExit(1)
    parser.config_file.write_text(tomlkit.dumps(cfg))


def config_parser(
    epilog: str = "", parser: Optional[argparse.ArgumentParser] = None
) -> argparse.ArgumentParser:
    """Construct command line argument parser."""
    parser = parser or argparse.ArgumentParser(
        prog="deploy-freva-config",
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
    subparsers = parser.add_subparsers(required=False)
    get_parser = subparsers.add_parser(
        "get",
        description="Inspect configuration values.",
        help=(
            "Use this command to query either the whole or parts of the "
            "deployment config."
        ),
        epilog=epilog,
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    get_parser.add_argument(
        "keys",
        nargs="*",
        help=(
            "Query keys. Can be the from of <section>.<key>, <key>, <section> "
            "if no keys are given the whole configuration is printed to stdout."
            " this can be useful for creating new config files"
        ),
    )
    get_parser.add_argument(
        "-c",
        "--config-file",
        type=Path,
        help="Path to ansible inventory file.",
        default=config_dir / "config" / "inventory.toml",
    )
    get_parser.add_argument(
        "-r", "--raw", help="Raw output", action="store_true", default=False
    )
    get_parser.add_argument(
        "-v", "--verbose", action="count", help="Verbosity level", default=0
    )

    set_parser = subparsers.add_parser(
        "set",
        description="Inspect configuration values.",
        help=(
            "Use this command to set/override values " "of the deployment config."
        ),
        epilog=epilog,
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    set_parser.add_argument(
        "-c",
        "--config-file",
        type=Path,
        help="Path to ansible inventory file.",
        default=config_dir / "config" / "inventory.toml",
    )
    set_parser.add_argument(
        "values",
        nargs=2,
        action="append",
        help=(
            "Key value pairs of the config. Can be in from of"
            "<section>.<key> value, <key> = value. Note: value needs "
            "to follow toml syntax"
        ),
    )
    set_parser.add_argument(
        "-v", "--verbose", action="count", help="Verbosity level", default=0
    )
    set_parser.set_defaults(cli=_set_config)
    get_parser.set_defaults(cli=_get_config)
    return parser
