"""Command line interface for the deployment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rich_argparse import ArgumentDefaultsRichHelpFormatter

from freva_deployment import __version__

from ..deploy import DeployFactory
from ..error import DeploymentError
from ..logger import set_log_level
from ..utils import config_dir
from ..versions import VersionAction, display_versions


class BatchParser:
    """Command line interface for batchmode deployment."""

    def __init__(
        self,
        parser: Optional[argparse.ArgumentParser] = None,
        epilog: str = "",
    ) -> None:
        self.parser = parser or argparse.ArgumentParser(
            prog="deploy-freva-cmd",
            description="Deploy freva and its services on different machines.",
            formatter_class=ArgumentDefaultsRichHelpFormatter,
            epilog=epilog,
        )
        self.parser.add_argument(
            "--config",
            "-c",
            type=Path,
            help="Path to ansible inventory file.",
            default=config_dir / "config" / "inventory.toml",
        )
        self.parser.add_argument(
            "--steps",
            "-s",
            type=str,
            nargs="+",
            default=["db", "freva-rest", "web", "core"],
            choices=["web", "core", "db", "freva-rest", "auto"],
            help=(
                "The services/code stack to be deployed. Use [b]auto[/b]"
                " to only deploy outdated services"
            ),
        )
        self.parser.add_argument(
            "--ask-pass",
            help="Connect to server via ssh passwd instead of public key.",
            action="store_true",
            default=False,
        )
        self.parser.add_argument(
            "--ssh-port",
            help="Set the ssh port, in 99.9%% of the cases this should be 22",
            type=int,
            default=22,
        )
        self.parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            help="Verbosity level",
            default=0,
        )
        self.parser.add_argument(
            "-l",
            "--local",
            help="Deploy services on the local machine, debug purpose.",
            action="store_true",
            default=False,
        )
        self.parser.add_argument(
            "-g",
            "--gen-keys",
            help="Generate public and private web certs, use with caution.",
            action="store_true",
            default=False,
        )
        self.parser.add_argument(
            "--skip-version-check",
            help="Skip the version check. Use with caution.",
            action="store_true",
            default=False,
        )
        self.parser.add_argument(
            "-V",
            "--version",
            action=VersionAction,
            version="[b][red]%(prog)s[/red] {version}[/b]{services}".format(
                version=__version__, services=display_versions()
            ),
        )
        self.parser.add_argument(
            "-t",
            "--tags",
            type=str,
            nargs="+",
            default=None,
            choices=[
                "core",
                "db",
                "cache",
                "data-loader",
                "freva-rest",
                "mongodb",
                "search-server",
                "pre-web",
                "web",
            ],
            help=(
                "Fine grain deployment. Instead of using steps you can "
                "set those ansible tasks ([i]tags[/i]) to be deployed."
            ),
        )
        self.parser.add_argument(
            "--cowsay",
            action="store_true",
            help="Let the cow speak!",
            default=False,
        )
        self.parser.set_defaults(cli=self.run_cli)

    def parse_args(self, argv: Optional[List[str]]) -> argparse.Namespace:
        return self.parser.parse_args()

    @staticmethod
    def run_cli(args: argparse.Namespace) -> None:
        """Run the command line interface."""
        set_log_level(args.verbose)
        steps = [s.replace("-", "_") for s in args.steps]
        if args.tags:
            steps = []
        with DeployFactory(
            steps=steps,
            config_file=args.config,
            local_debug=args.local,
            gen_keys=args.gen_keys,
            _cowsay=args.cowsay,
        ) as DF:
            try:
                DF.play(
                    args.ask_pass,
                    args.verbose,
                    ssh_port=args.ssh_port,
                    skip_version_check=args.skip_version_check,
                    tags=args.tags or None,
                )
            except KeyboardInterrupt:
                raise SystemExit(130)
            except DeploymentError:
                raise SystemExit(1)


def cli(argv: list[str] | None = None) -> None:
    """Run the command line interface."""
    epilog = (
        "[red][b]Note:[/b] The command `deploy-freva-cmd` is a legacy command,"
        " please consdider using `deploy-freva cmd` instead.[/red]"
    )
    bp = BatchParser(epilog=epilog)
    args = bp.parse_args(argv)
    bp.run_cli(args)


if __name__ == "__main__":
    cli(sys.argv[1:])
