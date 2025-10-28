"""

This resAPI let's you savely store and retrieve secrets. Such secrets include
the login credentials of the freva database or user name and password for
the django enmail interface.

Overview
--------

"""

import argparse
import base64
import json
import logging
import os
import pathlib
import random
import sys
import time
from subprocess import Popen
from typing import Annotated, Dict, List, Optional, TypedDict, cast

import hvac
import requests
from fastapi import Body, FastAPI, Header, HTTPException, Path, status
from fastapi.responses import JSONResponse

KeyType = TypedDict("KeyType", {"keys": List[str], "token": str})
if os.getenv("KEY_FILE"):
    KEY_FILE = pathlib.Path(os.getenv("KEY_FILE"))
elif os.getenv("CONDA_PREFIX"):
    KEY_FILE = (
        pathlib.Path(os.getenv("CONDA_PREFIX"))
        / "share"
        / "freva-rest-server"
        / "vault"
        / "keys"
    )
else:
    KEY_FILE = pathlib.Path("/vault/file/keys")
VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
POLICY = """
    path "secret" {
        capabilities = ["create", "read", "update", "delete", "list"]
    }
"""

PHRASES = [
    "There seems to be a noose around this request.",
    "Our guns jammed! Something went wrong.",
    "When you have to shoot, shoot, don't talk.",
    "The bullets didn't fire.",
    "I've never seen so many men wasted so badly.",
    "You're not digging.",
    "We're in the desert without a horse.",
    "We faced a showdown, and it didn't end well."
    "Blondie! You know what you are? Just a dirty son of a...",
]

metadata_tags = [
    {
        "name": "Secrets",
        "description": "Read and Store secret key=value pairs.",
    }
]

VERSION = "2505.0.3"

app = FastAPI(
    title="freva-vault",
    debug=False,
    summary="The freva secret restAPI 🔒",
    description=__doc__,
    openapi_url="/vault/docs/openapi.json",
    docs_url="/vault/docs",
    version=VERSION,
    redoc_url=None,
    contact={"name": "DKRZ, Clint", "email": "freva@dkrz.de"},
    license_info={
        "name": "BSD 2-Clause License",
        "url": "https://opensource.org/license/bsd-2-clause",
    },
)
logging.basicConfig(
    format="%(asctime)s - %(name)s - [%(levelname)s] - %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("secret-reader")


def cli() -> str:
    """Set up the command line interface."""
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description="Start the vault server.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        type=pathlib.Path,
        help="Vault config path.",
        default="/opt/vault/vault-server-tls.hcl",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", help="Verbosity level", default=0
    )
    args = parser.parse_args()
    logger.setLevel(max(logging.INFO - 10 * args.verbose, logging.DEBUG))
    return str(args.config.expanduser().absolute())


class VaultClient:
    """Interact with the client."""

    secret_threshold: int = 5
    """The number of shares required to reconstruct the master key."""
    secret_shares: int = 5
    """The number of shares to split the master key into."""
    client = hvac.Client(
        url=VAULT_ADDR,
    )
    keys: KeyType = {"token": "", "keys": []}

    def __init__(self) -> None:
        prefix = "VAULT_ADD_VAR_"
        self.add_keys = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                k = key.removeprefix(prefix).lower().replace("_", ".")
                self.add_keys[k] = value

    def _auth_vault(self) -> None:
        if not self.client.is_authenticated():
            keys = self.unseal()
            self.client.token = keys.get("token")

    def update_secret(self, path: str, **secret: str) -> None:
        """Update or create a secret."""
        self._auth_vault()
        old_secret = self.get_secret(path) or {}
        old_secret.update(secret)
        self.client.secrets.kv.v1.create_or_update_secret(
            path=path, secret=old_secret
        )

    def get_secret(self, path: str) -> Optional[Dict[str, str]]:
        """Get the secretes of a path."""
        self._auth_vault()
        try:
            return cast(
                Optional[Dict[str, str]],
                self.client.secrets.kv.v1.read_secret(path).get("data"),
            )
        except hvac.exceptions.VaultError:
            logger.warning("Could not find secret path: %s", path)
            return None

    @property
    def token(self) -> str:
        """Get the root token."""
        self._auth_vault()
        return self.client.token or ""

    @classmethod
    def init_vault(cls) -> KeyType:
        """Setup a fresh vault."""
        if cls.client.sys.is_initialized() is False:
            keys = cls.client.sys.initialize(
                cls.secret_shares, cls.secret_threshold
            )
            keys.pop("keys_base64", "")
            keys["token"] = keys.pop("root_token")
            KEY_FILE.parent.mkdir(exist_ok=True, parents=True)
            KEY_FILE.write_bytes(
                base64.b64encode(json.dumps(keys).encode("utf-8"))
            )
        elif not KEY_FILE.is_file():
            logger.critical(
                "Vault is initialized but the key file does not exist"
            )
            return {"token": "", "keys": []}
        return cast(
            KeyType,
            json.loads(base64.b64decode(KEY_FILE.read_bytes())),
        )

    @property
    def vault_state(self) -> str:
        """Get a human readable state of the vault."""
        try:
            is_sealed = Vault.client.sys.is_sealed()
        except requests.exceptions.ConnectionError:
            is_sealed = None
        return {True: "sealed", False: "unsealed", None: "down"}[is_sealed]

    @classmethod
    def configure(cls, token: str) -> None:
        """Configure the vault if not already done."""
        cls.client.token = token
        if "secret/" not in cls.client.sys.list_mounted_secrets_engines():
            cls.client.sys.enable_secrets_engine("kv", "secret")
            cls.client.sys.create_or_update_policy("secret", POLICY)

    @classmethod
    def unseal(cls) -> KeyType:
        """Unseal the vault."""

        logger.info("Unsealing vault")
        for _ in range(5):
            try:
                keys = cls.init_vault()
                if cls.client.sys.is_sealed() is True:
                    cls.client.sys.submit_unseal_keys(keys.get("keys", []))
                if cls.client.sys.is_sealed() is False:
                    logger.info("Vault has been unsealed.")
                    cls.configure(keys["token"])
                    return keys
            except requests.exceptions.ConnectionError:
                logger.warning("Vault not ready yet.")
                time.sleep(1)
            except Exception as error:
                logger.error("Failed to unseal vault: %s", error)
                return {"token": "", "keys": []}
        logger.error("Vault doesn't seem to be up.")
        return {"token": "", "keys": []}


Vault = VaultClient()


@app.get("/vault/status", tags=["Secrets"])
async def get_vault_status() -> JSONResponse:
    """Get the status of the vault."""
    return JSONResponse(
        content={"status": Vault.vault_state, "version": VERSION}, status_code=200
    )


@app.post("/vault/{path}", tags=["Secrets"])
async def update_secret(
    path: Annotated[str, Path(description="Secret location.", examples=["test"])],
    secrets: Annotated[
        Optional[Dict[str, str]],
        Body(
            description=(
                "The secret that should be stored, "
                "this is a string represenatation of the"
                " the secrets. Secrets are encoded via "
                "key=value. Multiple secrets are ',' "
                "comma separated."
            ),
            examples=[{"foo": "bar", "hoo": "roo"}],
        ),
    ] = None,
    admin_pw: Annotated[
        Optional[str],
        Header(
            alias="password",
            description="Give the pre defined admin password.",
            examples="password",
            tile="Password",
        ),
    ] = None,
) -> JSONResponse:
    """Update or create a secret."""
    if path == "test":
        return JSONResponse(
            {"message": "success"}, status_code=status.HTTP_201_CREATED
        )
    if admin_pw != os.environ.get("ROOT_PW", ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Permission denied",
        ) from None
    if not secrets:
        JSONResponse(
            content={"message": random.choice(PHRASES)},
            status_code=status.HTTP_204_NO_CONTENT,
        )
    try:
        Vault.update_secret(path, **secrets)
    except hvac.exceptions.VaultError:
        logger.warning("Could not add secrets %s to %s", path, secrets)
        raise HTTPException(
            detail=random.choice(PHRASES),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from None
    return JSONResponse(
        content={"message": "success"}, status_code=status.HTTP_201_CREATED
    )


@app.get("/vault/{path}/{public_key}", tags=["Secrets"])
async def read_secret(
    path: Annotated[
        str,
        Path(
            description="The name of the k/v secrets path",
            examples="data",
        ),
    ],
    public_key: Annotated[
        str,
        Path(
            description="hexdigest representation of the sha512 freva public key.",
            examples="foo",
        ),
    ],
) -> JSONResponse:
    """Read evaulation system secrets from the vault."""
    status_code = 400
    if len(public_key) != 128:  # This is not a checksum of a cert.
        text = f"But the vault is {Vault.vault_state}"
        raise HTTPException(
            detail=f"{random.choice(PHRASES)} {text}", status_code=status_code
        ) from None
    # Get the information from the vault
    data = Vault.get_secret(path)
    if data is not None:
        status_code = 200
    return JSONResponse(content=data or {}, status_code=status_code)


if __name__ == "__main__":

    Popen(["vault", "server", "-config", cli()])
    key = Vault.unseal()
    if key.get("token") and Vault.add_keys:
        print(Vault.add_keys)
        Vault.update_secret("data", **Vault.add_keys)
