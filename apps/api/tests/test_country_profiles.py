import pytest

from app.country_profiles import GENERIC_PROFILE, PROFILES, detect_country


def test_detect_country_uses_explicit_code_first():
    profile = detect_country(explicit_code="DE", vendor_vat="SK1234567890", currency="USD")
    assert profile.code == "DE"


def test_detect_country_falls_back_to_vat_prefix():
    profile = detect_country(explicit_code=None, vendor_vat="DE123456789", currency=None)
    assert profile.code == "DE"


def test_detect_country_falls_back_to_currency():
    profile = detect_country(explicit_code=None, vendor_vat=None, currency="USD")
    assert profile.code == "US"

    profile = detect_country(explicit_code=None, vendor_vat=None, currency="GBP")
    assert profile.code == "GB"


def test_detect_country_returns_generic_when_unknown():
    profile = detect_country(explicit_code="XX", vendor_vat=None, currency="JPY")
    assert profile is GENERIC_PROFILE


@pytest.mark.parametrize("code", ["SK", "CZ", "DE", "AT", "FR", "IT", "ES", "NL", "PL", "GB", "US"])
def test_all_profiles_define_required_fields(code):
    p = PROFILES[code]
    assert p.code == code
    assert p.default_currency
    assert p.allowed_currencies
    assert p.date_formats
