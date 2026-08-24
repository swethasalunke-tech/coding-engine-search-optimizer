"""Ed25519 keypair generation and license token sign/verify.

License tokens are plain, offline, asymmetrically-signed bundles: a JSON
payload (tier, features, expiry, customer info — whatever the issuer wants
to embed) plus an Ed25519 signature over that payload's canonical JSON
encoding. There is no phone-home step and no server component — this is
the same basic approach used by tools like Keygen for offline license
verification (see DESIGN.md).

This module has ZERO dependency on any payment processor. It only knows
how to sign and verify tokens; deciding *when* to call sign_license is a
human (or later, a webhook handler — see BUILD-SCHEDULE.md, not built
today) decision made outside this module.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class LicenseError(Exception):
    """Base class for license-related errors."""


class InvalidLicenseError(LicenseError):
    """Raised when a token's signature doesn't verify, or the token is
    malformed (not valid base64/JSON, missing required fields)."""


class ExpiredLicenseError(LicenseError):
    """Raised when a token's signature is valid but payload['expires'] is
    in the past."""


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a new Ed25519 keypair. Returns (private_key, public_key)."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def _canonical_json_bytes(payload: dict) -> bytes:
    """Serialize a payload dict to canonical JSON bytes: sorted keys, no
    extraneous whitespace, so signing and verification always hash the
    exact same byte sequence for a semantically-equal payload."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_license(payload: dict, private_key: Ed25519PrivateKey) -> str:
    """Sign a license payload and return an opaque base64 token string.

    The token embeds both the original payload (as JSON) and the base64
    signature, so verify_license can recover the payload without needing
    a separate lookup.

    `payload` should be a JSON-serializable dict. If it should expire,
    include an "expires" key as an ISO-8601 UTC timestamp string, e.g.
    "2027-01-01T00:00:00+00:00" (see verify_license for the check).
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")

    payload_bytes = _canonical_json_bytes(payload)
    signature = private_key.sign(payload_bytes)

    envelope = {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    envelope_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    token = base64.urlsafe_b64encode(envelope_json.encode("utf-8")).decode("ascii")
    return token


def verify_license(token: str, public_key: Ed25519PublicKey) -> dict:
    """Verify a license token's signature and expiry, returning the
    payload dict if valid.

    Raises:
        InvalidLicenseError: token is malformed (not valid base64/JSON,
            missing required "payload"/"signature" fields) or the
            signature does not verify against `public_key`.
        ExpiredLicenseError: signature is valid but payload["expires"]
            (if present) is a timestamp in the past relative to
            datetime.now(timezone.utc).
    """
    if not isinstance(token, str) or not token:
        raise InvalidLicenseError("token must be a non-empty string")

    try:
        envelope_json = base64.urlsafe_b64decode(token.encode("ascii"))
        envelope = json.loads(envelope_json)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any malformed input -> InvalidLicenseError
        raise InvalidLicenseError(f"malformed license token: {exc}") from exc

    if not isinstance(envelope, dict) or "payload" not in envelope or "signature" not in envelope:
        raise InvalidLicenseError("malformed license token: missing payload/signature")

    payload = envelope["payload"]
    signature_b64 = envelope["signature"]

    if not isinstance(payload, dict) or not isinstance(signature_b64, str):
        raise InvalidLicenseError("malformed license token: bad payload/signature types")

    try:
        signature = base64.b64decode(signature_b64)
    except Exception as exc:  # noqa: BLE001
        raise InvalidLicenseError(f"malformed license token signature: {exc}") from exc

    payload_bytes = _canonical_json_bytes(payload)
    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature as exc:
        raise InvalidLicenseError("license signature verification failed") from exc

    expires = payload.get("expires")
    if expires:
        try:
            expires_dt = datetime.fromisoformat(expires)
        except ValueError as exc:
            raise InvalidLicenseError(f"malformed 'expires' timestamp: {expires!r}") from exc
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        if expires_dt < datetime.now(timezone.utc):
            raise ExpiredLicenseError(f"license expired at {expires}")

    return payload
