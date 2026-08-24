"""Sign/verify round trip tests using a throwaway test keypair generated
fresh in this test module -- NOT the repo's real embedded key from
solution_optimizer/license/gate.py."""

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from solution_optimizer.license.keys import (
    ExpiredLicenseError,
    InvalidLicenseError,
    generate_keypair,
    sign_license,
    verify_license,
)


@pytest.fixture()
def keypair():
    return generate_keypair()


def _future_iso(days=365):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past_iso(days=1):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_sign_and_verify_round_trip(keypair):
    private_key, public_key = keypair
    payload = {"tier": "enterprise", "features": ["org_dashboard"], "customer": "acme"}
    token = sign_license(payload, private_key)
    assert isinstance(token, str) and token

    recovered = verify_license(token, public_key)
    assert recovered == payload


def test_verify_with_future_expiry_succeeds(keypair):
    private_key, public_key = keypair
    payload = {"tier": "pro", "features": [], "expires": _future_iso()}
    token = sign_license(payload, private_key)
    recovered = verify_license(token, public_key)
    assert recovered["tier"] == "pro"


def test_verify_expired_license_raises(keypair):
    private_key, public_key = keypair
    payload = {"tier": "pro", "features": [], "expires": _past_iso()}
    token = sign_license(payload, private_key)
    with pytest.raises(ExpiredLicenseError):
        verify_license(token, public_key)


def test_verify_with_wrong_key_raises(keypair):
    private_key, _public_key = keypair
    _other_private, other_public = generate_keypair()
    payload = {"tier": "pro", "features": []}
    token = sign_license(payload, private_key)
    with pytest.raises(InvalidLicenseError):
        verify_license(token, other_public)


def test_tampered_payload_rejected(keypair):
    private_key, public_key = keypair
    payload = {"tier": "free", "features": []}
    token = sign_license(payload, private_key)

    envelope = json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
    envelope["payload"]["tier"] = "enterprise"
    tampered_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    tampered_token = base64.urlsafe_b64encode(tampered_json.encode("utf-8")).decode("ascii")

    with pytest.raises(InvalidLicenseError):
        verify_license(tampered_token, public_key)


def test_tampered_signature_rejected(keypair):
    private_key, public_key = keypair
    payload = {"tier": "free", "features": []}
    token = sign_license(payload, private_key)

    envelope = json.loads(base64.urlsafe_b64decode(token.encode("ascii")))
    # Flip the signature to a different, still-valid-base64 value.
    real_sig = base64.b64decode(envelope["signature"])
    flipped = bytes([real_sig[0] ^ 0xFF]) + real_sig[1:]
    envelope["signature"] = base64.b64encode(flipped).decode("ascii")
    tampered_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
    tampered_token = base64.urlsafe_b64encode(tampered_json.encode("utf-8")).decode("ascii")

    with pytest.raises(InvalidLicenseError):
        verify_license(tampered_token, public_key)


@pytest.mark.parametrize(
    "bad_token",
    [
        "",
        "not-valid-base64!!!",
        base64.urlsafe_b64encode(b"not json at all").decode("ascii"),
        base64.urlsafe_b64encode(b'{"payload": {}}').decode("ascii"),  # missing signature
        base64.urlsafe_b64encode(b'{"signature": "abc"}').decode("ascii"),  # missing payload
    ],
)
def test_malformed_tokens_rejected(keypair, bad_token):
    _private_key, public_key = keypair
    with pytest.raises(InvalidLicenseError):
        verify_license(bad_token, public_key)


def test_malformed_expires_field_rejected(keypair):
    private_key, public_key = keypair
    payload = {"tier": "pro", "features": [], "expires": "not-a-date"}
    token = sign_license(payload, private_key)
    with pytest.raises(InvalidLicenseError):
        verify_license(token, public_key)


def test_sign_license_rejects_non_dict_payload(keypair):
    private_key, _public_key = keypair
    with pytest.raises(TypeError):
        sign_license(["not", "a", "dict"], private_key)
