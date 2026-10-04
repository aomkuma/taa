"""Generate a VAPID key pair for Web Push (PLAN §A14; TAA-806).

    .venv\\Scripts\\python scripts\\generate_vapid_keys.py [--subject mailto:you@example.com]

Prints the three variables to set (on Railway as sealed service variables):

- ``VAPID_PUBLIC_KEY`` on the **web** service: the browsers' ``applicationServerKey`` (an uncompressed P-256
  point, unpadded base64url)
- ``VAPID_PRIVATE_KEY`` and ``VAPID_SUBJECT`` on the **worker**: the raw 32-byte private key (unpadded
  base64url) and the contact the push services may use

Changing the pair invalidates every existing browser subscription: the PWA has to subscribe again.
The private key is printed once and stored nowhere else; keep it in the service variables or the keyring.
"""

from __future__ import annotations

import argparse
import base64
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate() -> tuple[str, str]:
    """(public key, private key), both unpadded base64url."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64url(public), b64url(private)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a VAPID key pair for Web Push")
    parser.add_argument("--subject", default="mailto:owner@example.com", help="mailto: or https: contact")
    args = parser.parse_args(argv)
    public, private = generate()
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
    print(f"VAPID_SUBJECT={args.subject}")
    print("# web: VAPID_PUBLIC_KEY; worker: VAPID_PRIVATE_KEY and VAPID_SUBJECT", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
