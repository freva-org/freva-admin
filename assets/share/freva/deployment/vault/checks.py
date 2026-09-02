"""Simple script to start and stop the storage service."""

import json
import logging
import subprocess
import time
import urllib.request

# Set up logging
logging.basicConfig(
    format="%(name)s - %(levelname)s - %(message)s",
    datefmt="[%X]",
    level=logging.INFO,
)
logger = logging.getLogger("container-check")


def start_container(container_name: str) -> subprocess.Popen[bytes]:
    """Start a vault test container with Podman.

    Parameters
    ----------
    container_name : str
        Container image to test.

    Returns
    -------
    subprocess.Popen[bytes]
        Handle for the running Podman process.
    """
    return subprocess.Popen(
        [
            "podman",
            "run",
            "--net=host",
            "-e",
            "ROOT_PW=foo",
            "-e",
            "VERSION=0.0.0",
            "-p",
            "5002:5002",
            container_name,
        ],
    )


def _check_container(process: subprocess.Popen[bytes]) -> None:
    """Check whether the vault test container is ready.

    Parameters
    ----------
    process : subprocess.Popen[bytes]
        Handle for the running Podman process.
    """
    try:
        if process.poll() is not None:
            raise RuntimeError("Container died.")
        res = urllib.request.Request(
            "http://localhost:5002/vault/status",
        )
        with urllib.request.urlopen(res) as response:
            if response.getcode() != 200:
                raise RuntimeError("Container not properly set up.")
            json_req = json.loads(response.read().decode())
    except Exception as error:
        logger.critical("The container failed: %s", error)
        raise RuntimeError(error) from None
    if json_req.get("status") != "unsealed":
        logger.critical("Vault did not unseal: %s", json_req.get("status", "500"))
        raise ValueError("Vault did not unseal")
    process.terminate()
    logger.info("Container seems to work!")


def check_container(container_name: str = "vault") -> None:
    """Check the status of a vault container image.

    Parameters
    ----------
    container_name : str, default="vault"
        Container image to test.
    """
    proc = start_container(container_name)
    time.sleep(5)
    for _ in range(10):
        try:
            _check_container(proc)
            return
        except RuntimeError:
            time.sleep(5)
    proc.terminate()
    raise ValueError("Container does not seem to work.")


if __name__ == "__main__":
    check_container()
