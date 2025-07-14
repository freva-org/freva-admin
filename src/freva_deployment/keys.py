"""Generate keys."""

import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

_CRYPTO = True
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import (
        ec,
        ed25519,
        padding,
        rsa,
    )
    from cryptography.x509.oid import NameOID
except ImportError:
    _CRYPTO = False


class RandomKeys:
    """Generate public and private server keys.

    Parameters:
        base_name (str): The path prefix for all key files.
        common_name (str): The common name for the certificate.
    """

    def __init__(
        self, base_name: str = "freva", common_name: str = "localhost"
    ) -> None:
        self.base_name = base_name
        self.common_name = common_name
        self._private_key_pem: Optional[bytes] = None
        self._public_key_pem: Optional[bytes] = None
        self._private_key: Optional["rsa.RSAPrivateKey"] = None
        self._temp_dir = TemporaryDirectory("random_keys")

    @staticmethod
    def _check_crypto() -> None:
        if not _CRYPTO:
            raise ImportError(
                "Please install the `cryptography` python module."
                " in order to generate certificates."
            )

    def check_cert_key_pair(self, cert_path: str, key_path: str) -> bool:
        """Validate a certificate/key pair by checking:
            - The certificate is currently valid (not expired).
            - The certificate and private key match.
        Parameters
        ----------
        cert_path : str
            Path to the PEM-encoded certificate file.
        key_path : str
            Path to the PEM-encoded private key file.
        allow_self_signed : bool, optional
            Whether to consider self-signed certificates as valid, by default False.

        Returns
        -------
        bool
            True if the certificate/key pair is valid, matching, and trusted
            False otherwise.
        """
        self._check_crypto()
        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            with open(key_path, "rb") as f:
                key_data = f.read()
            private_key = serialization.load_pem_private_key(
                key_data, password=None, backend=default_backend()
            )
            public_key = cert.public_key()
        except Exception:
            return False

        now = datetime.datetime.now(datetime.timezone.utc)
        if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
            return False
        if cert.issuer == cert.subject:
            return False

        message = b"test"
        try:
            if isinstance(private_key, rsa.RSAPrivateKey) and isinstance(
                public_key, rsa.RSAPublicKey
            ):
                signature = private_key.sign(
                    message, padding.PKCS1v15(), hashes.SHA256()
                )
                public_key.verify(
                    signature, message, padding.PKCS1v15(), hashes.SHA256()
                )
                return True

            elif isinstance(
                private_key, ec.EllipticCurvePrivateKey
            ) and isinstance(public_key, ec.EllipticCurvePublicKey):
                signature = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
                public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
                return True

            elif isinstance(
                private_key, ed25519.Ed25519PrivateKey
            ) and isinstance(public_key, ed25519.Ed25519PublicKey):
                signature = private_key.sign(message)
                public_key.verify(signature, message)
                return True

            else:
                return False

        except Exception:
            return False

    @property
    def private_key(self) -> "rsa.RSAPrivateKey":
        if self._private_key is not None:
            return self._private_key
        self._private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        return self._private_key

    @property
    def private_key_pem(self) -> bytes:
        """Create a new private key pem if it doesn't exist."""
        self._check_crypto()
        if self._private_key_pem is None:
            self._private_key_pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        return self._private_key_pem

    @property
    def public_key_pem(self) -> bytes:
        """
        Generate a public key pair using RSA algorithm.

        Returns:
            bytes: The public key (PEM format).
        """
        self._check_crypto()
        if self._public_key_pem is None:
            public_key = self.private_key.public_key()
            self._public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        return self._public_key_pem

    @property
    def private_key_file(self) -> str:
        """
        Save the private key to a file.

        Returns:
            str: The filename of the private key file.
        """
        self._check_crypto()
        temp_file = (Path(self._temp_dir.name) / self.base_name).with_suffix(
            ".key"
        )
        if not temp_file.is_file():
            temp_file.write_bytes(self.private_key_pem)
        return str(temp_file)

    @property
    def public_key_file(self) -> str:
        """
        Save the public key to a file.

        Returns:
            str: The filename of the public key file.
        """
        temp_file = (Path(self._temp_dir.name) / self.base_name).with_suffix(
            ".pem"
        )
        if not temp_file.is_file():
            temp_file.write_bytes(self.public_key_pem)
        return str(temp_file)

    @property
    def public_chain_file(self) -> str:
        """
        Save the public key and certificate chain to a file.

        Returns:
            str: The filename of the certificate chain file.
        """
        temp_file = (Path(self._temp_dir.name) / self.base_name).with_suffix(
            ".crt"
        )
        if not temp_file.is_file():
            temp_file.write_bytes(self.certificate_chain)
        return str(temp_file)

    def create_self_signed_cert(self) -> "x509.Certificate":
        """
        Create a self-signed certificate using the public key.

        Returns
        -------
            x509.Certificate: The self-signed certificate.
        """
        self._check_crypto()
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name(
                    [x509.NameAttribute(NameOID.COMMON_NAME, self.common_name)]
                )
            )
            .sign(self.private_key, hashes.SHA256(), default_backend())
        )
        # Add SANs
        san = x509.SubjectAlternativeName(
            [
                x509.DNSName(f"{self.common_name}"),
                x509.DNSName(f"www.{self.common_name}"),
                x509.DNSName("web-reverse-proxy"),
                x509.DNSName("www.web-reverse-proxy"),
            ]
        )
        certificate = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(csr.subject)
            .add_extension(san, critical=False)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
            .not_valid_after(
                datetime.datetime.now(datetime.timezone.utc)
                + datetime.timedelta(days=10 * 365)
            )
            .sign(self.private_key, hashes.SHA256(), default_backend())
        )

        return certificate

    @property
    def certificate_chain(self) -> bytes:
        """The certificate chain."""
        certificate = self.create_self_signed_cert()
        certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)
        return self.public_key_pem + certificate_pem


if __name__ == "__main__":
    # Create an instance of RandomKeys
    keys = RandomKeys()

    # Output the public key
    print("Public Key:")
    print(Path(keys.private_key_file).read_text())
    # Output the certificate chain
    print("\nPublic Key:")
    print(Path(keys.public_chain_file).read_text())
