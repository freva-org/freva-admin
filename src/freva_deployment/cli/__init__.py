"""Command line interfaces."""

import argparse
import importlib
import os
import shutil
from typing import List, Optional

os.environ["ANSIBLE_COW_PATH"] = os.getenv(
    "ANSIBLE_COW_PATH", shutil.which("cowsay") or ""
)

from rich_argparse import ArgumentDefaultsRichHelpFormatter

from freva_deployment import __version__
from freva_deployment.ui.deployment_tui import tui
from freva_deployment.versions import VersionAction, display_versions

from ._compose import compose_parser
from ._config import config_parser
from ._deploy import BatchParser
from ._deploy import cli as deploy
from ._migrate import cli as migrate
from ._migrate import create_parser as migrate_parser

__all__ = ["deploy", "migrate"]


def __getattr__(name):
    return getattr(importlib.import_module(f"._{name}", __name__), "cli")


def main_cli(argv: Optional[List[str]] = None) -> None:
    """Construct command line argument parser."""
    app = argparse.ArgumentParser(
        prog="deploy-freva",
        description="Run the freva deployment",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    app.set_defaults(cli=tui)
    app.add_argument(
        "-v", "--verbose", action="count", help="Verbosity level", default=0
    )
    app.add_argument(
        "-V",
        "--version",
        action=VersionAction,
        version="[b][red]%(prog)s[/red] {version}[/b]{services}".format(
            version=__version__, services=display_versions()
        ),
    )
    app.add_argument(
        "--cowsay",
        action="store_true",
        help="Let the cow speak!",
        default=False,
    )

    subparser = app.add_subparsers(
        required=False,
    )
    _ = BatchParser(
        subparser.add_parser(
            name="cmd",
            help="Run deployment in batch mode.",
            description="Run deployment in batch mode.",
            formatter_class=ArgumentDefaultsRichHelpFormatter,
        )
    )

    config_parser(
        parser=subparser.add_parser(
            name="config",
            help="Create and inspect freva configuration.",
            formatter_class=ArgumentDefaultsRichHelpFormatter,
        )
    )
    compose_parser(
        parser=subparser.add_parser(
            name="compose",
            help="Create a compose file.",
            formatter_class=ArgumentDefaultsRichHelpFormatter,
        )
    )

    migrate_parser(
        parser=subparser.add_parser(
            name="migrate",
            help="Utilities to handle migrations from old freva systems.",
            formatter_class=ArgumentDefaultsRichHelpFormatter,
        )
    )

    args = app.parse_args(argv)
    args.cli(args)
