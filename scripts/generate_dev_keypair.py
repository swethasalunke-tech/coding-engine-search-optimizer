#!/usr/bin/env python3
"""Generate this repo's real Ed25519 keypair for license signing.

Run once (already run for this repo's committed public key in
solution_optimizer/license/gate.py). Writes the private key to
dev_keys/private_key.pem (git-ignored, never committed) and prints the
public key as hex to stdout so it can be pasted into gate.py's
_PUBLIC_KEY_HEX constant.

Usage:
    python3 scripts/generate_dev_keypair.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from solution_optimizer.license.keys import generate_keypair


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dev_keys_dir = repo_root / "dev_keys"
    dev_keys_dir.mkdir(exist_ok=True)
    private_key_path = dev_keys_dir / "private_key.pem"

    if private_key_path.exists():
        print(
            f"error: {private_key_path} already exists. Refusing to overwrite an "
            "existing dev keypair. Delete it manually first if you really want a "
            "new one.",
            file=sys.stderr,
        )
        return 1

    private_key, public_key = generate_keypair()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key_path.write_bytes(private_pem)
    private_key_path.chmod(0o600)

    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_hex = public_raw.hex()

    print(f"Private key written to: {private_key_path}")
    print("This file is git-ignored and must never be committed or pushed.")
    print()
    print("Public key (hex) -- paste into solution_optimizer/license/gate.py "
          "as _PUBLIC_KEY_HEX:")
    print(public_hex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
