from datetime import datetime, timedelta, timezone

import pytest

from solution_optimizer.license.gate import (
    CI_INTEGRATION,
    ENV_VAR_NAME,
    FREE_TIER,
    ORG_DASHBOARD,
    TREND_REPORTS,
    LicenseGate,
    LicenseRequiredError,
)
from solution_optimizer.license.keys import generate_keypair, sign_license


@pytest.fixture()
def test_keypair():
    return generate_keypair()


def _valid_token(private_key, tier="enterprise", features=None, days=365):
    payload = {
        "tier": tier,
        "features": features or [],
        "expires": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
    }
    return sign_license(payload, private_key)


def test_no_env_var_is_free_tier(monkeypatch, test_keypair):
    _private_key, public_key = test_keypair
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)
    gate = LicenseGate(public_key=public_key)
    assert gate.tier == FREE_TIER
    assert gate.is_licensed is False
    assert gate.has_feature(ORG_DASHBOARD) is False
    assert gate.has_feature(CI_INTEGRATION) is False
    assert gate.has_feature(TREND_REPORTS) is False


def test_valid_token_grants_only_listed_features(test_keypair):
    private_key, public_key = test_keypair
    token = _valid_token(private_key, tier="enterprise", features=[ORG_DASHBOARD, CI_INTEGRATION])
    gate = LicenseGate(token=token, public_key=public_key)

    assert gate.is_licensed is True
    assert gate.tier == "enterprise"
    assert gate.has_feature(ORG_DASHBOARD) is True
    assert gate.has_feature(CI_INTEGRATION) is True
    assert gate.has_feature(TREND_REPORTS) is False


def test_env_var_token_used_when_no_explicit_token(monkeypatch, test_keypair):
    private_key, public_key = test_keypair
    token = _valid_token(private_key, tier="pro", features=[TREND_REPORTS])
    monkeypatch.setenv(ENV_VAR_NAME, token)
    gate = LicenseGate(public_key=public_key)
    assert gate.tier == "pro"
    assert gate.has_feature(TREND_REPORTS) is True


def test_invalid_token_falls_back_to_free(test_keypair):
    _private_key, public_key = test_keypair
    gate = LicenseGate(token="totally-bogus-token", public_key=public_key)
    assert gate.tier == FREE_TIER
    assert gate.is_licensed is False
    assert gate.has_feature(ORG_DASHBOARD) is False
    assert gate.verification_error is not None


def test_expired_token_falls_back_to_free(test_keypair):
    private_key, public_key = test_keypair
    token = _valid_token(private_key, tier="enterprise", features=[ORG_DASHBOARD], days=-10)
    gate = LicenseGate(token=token, public_key=public_key)
    assert gate.tier == FREE_TIER
    assert gate.is_licensed is False
    assert gate.has_feature(ORG_DASHBOARD) is False


def test_token_signed_by_wrong_key_falls_back_to_free(test_keypair):
    private_key, _public_key = test_keypair
    _other_private, other_public = generate_keypair()
    token = _valid_token(private_key, tier="enterprise", features=[ORG_DASHBOARD])
    # Verify against a different public key than the one that would match.
    gate = LicenseGate(token=token, public_key=other_public)
    assert gate.tier == FREE_TIER
    assert gate.has_feature(ORG_DASHBOARD) is False


def test_require_feature_raises_when_ungated(test_keypair):
    _private_key, public_key = test_keypair
    monkeypatch_none = None  # no token at all
    gate = LicenseGate(token=monkeypatch_none, public_key=public_key)
    with pytest.raises(LicenseRequiredError) as excinfo:
        gate.require_feature(ORG_DASHBOARD)
    message = str(excinfo.value)
    assert "org_dashboard" in message
    assert "license" in message.lower()
    assert "upgrade" in message.lower()


def test_require_feature_passes_when_granted(test_keypair):
    private_key, public_key = test_keypair
    token = _valid_token(private_key, tier="enterprise", features=[CI_INTEGRATION])
    gate = LicenseGate(token=token, public_key=public_key)
    gate.require_feature(CI_INTEGRATION)  # should not raise


def test_require_feature_raises_for_ungranted_feature_even_with_valid_license(test_keypair):
    private_key, public_key = test_keypair
    token = _valid_token(private_key, tier="enterprise", features=[ORG_DASHBOARD])
    gate = LicenseGate(token=token, public_key=public_key)
    with pytest.raises(LicenseRequiredError):
        gate.require_feature(TREND_REPORTS)


def test_default_gate_uses_repo_embedded_public_key(monkeypatch):
    """Sanity check: constructing LicenseGate with no explicit public_key
    falls back to the repo's embedded key without raising, and behaves as
    free tier when there's no env var set."""
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)
    gate = LicenseGate()
    assert gate.tier == FREE_TIER
