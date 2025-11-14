#!/usr/bin/env python3
"""Simple script to download data via python build in modules."""

import argparse
import logging
import urllib.request
from pathlib import Path
from typing import Tuple

logging.basicConfig(
    format="%(name)s: %(message)s",
    level=logging.INFO,
)


logger = logging.getLogger("downloader")


def reporthook(count: float, block_size: float, total_size: float) -> None:
    """Print the download status."""
    if count == 0:
        return
    frac = count * block_size / total_size
    percent = int(100 * frac)
    bar = "#" * int(frac * 40)
    msg = "Downloading: [{0:<{1}}] | {2}% Completed".format(
        bar, 40, round(percent, 2)
    )
    print(msg, end="\r", flush=True)
    if frac >= 1:
        print()


def cli() -> Tuple[str, str]:
    """Parse the command line arguments."""

    app = argparse.ArgumentParser(
        description="Download files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    app.add_argument(
        "url",
        help="The url of the file that needs to be downloaded.",
        type=str,
    )
    app.add_argument(
        "-o",
        "--output",
        help="The output file name.",
        type=str,
    )
    app.add_argument(
        "-v",
        "--verbose",
        help="Add debug output",
        action="store_true",
        default=False,
    )
    args = app.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    return args.url, args.output or "output"


def download(url: str, output: str) -> None:
    """Download a file."""
    out = Path(output).expanduser()
    out.parent.mkdir(exist_ok=True, parents=True)
    logger.debug("Downloading %s to %s", url, out)
    urllib.request.urlretrieve(
        url,
        filename=str(out),
        reporthook=reporthook,
    )
    out.chmod(0o755)


if __name__ == "__main__":
    download(*cli())
