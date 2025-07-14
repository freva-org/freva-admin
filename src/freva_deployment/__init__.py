import argparse
from urllib.request import urlretrieve

__version__ = "2507.3.0"

FREVA_PYTHON_VERSION = "3.13"
AVAILABLE_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13"]
AVAILABLE_CONDA_ARCHS = [
    "linux-64",
    "linux-aarch64",
    "linux-ppc64le",
    "linux-s390x",
    "osx-64",
    "osx-arm64",
]

AUX_URL = (
    "https://raw.githubusercontent.com/freva-org/freva-legacy/main/assets/"
    "evaluation_system.conf"
)


def download_auxiliry_data():
    """Download any data that needs to be downloaded."""

    def reporthook(count, block_size, total_size):
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

    urls = {
        AUX_URL: (
            "assets/share/freva/deployment/config/evaluation_system.conf.tmpl"
        )
    }

    for source, target in urls.items():
        urlretrieve(source, filename=target, reporthook=reporthook)


if __name__ == "__main__":
    app = argparse.ArgumentParser()
    app.add_argument("-v", "--version", action="store_true", default=False)
    args = app.parse_args()
    if args.version:
        print(__version__)
    else:
        download_auxiliry_data()
