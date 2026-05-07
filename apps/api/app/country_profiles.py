"""Country-specific invoice rules.

Each profile defines: VAT/Tax-ID format, accepted date formats, default
currencies, VAT rate set, and VAT-id prefix used for auto-detection.

Picking the profile (in order):
  1. Explicit `country_code` on `ClientConfig`.
  2. First two letters of `vendor_vat` if it matches a known EU prefix.
  3. Currency hint (USD -> US, GBP -> GB).
  4. Default fallback profile (generic).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CountryProfile:
    code: str
    name: str
    vat_format: str | None  # regex; None means no VAT id (e.g. US uses EIN)
    tax_id_format: str | None  # alternate id (e.g. EIN), or None
    date_formats: tuple[str, ...]
    default_currency: str
    allowed_currencies: tuple[str, ...]
    vat_rates: tuple[float, ...]  # standard rates (decimal: 0.20 = 20%)
    vat_id_prefix: str | None  # used for vendor_vat-based auto-detection


# Notes:
# - VAT formats follow the official EU VIES patterns; we use raw EU codes.
# - "default_currency" is what you'd expect a domestic invoice to be denominated in.
# - "allowed_currencies" is intentionally wide so foreign-currency invoices don't
#   trip validation. Tighten per-client via overrides if you want strict rules.
# - vat_rates is informational; we do not block invoices with non-standard rates,
#   we only warn on math errors.

PROFILES: dict[str, CountryProfile] = {
    "SK": CountryProfile(
        code="SK", name="Slovakia",
        vat_format=r"SK\d{10}", tax_id_format=None,
        date_formats=("DD.MM.YYYY", "D.M.YYYY"),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.10, 0.20, 0.23),
        vat_id_prefix="SK",
    ),
    "CZ": CountryProfile(
        code="CZ", name="Czech Republic",
        vat_format=r"CZ\d{8,10}", tax_id_format=None,
        date_formats=("DD.MM.YYYY", "D.M.YYYY"),
        default_currency="CZK", allowed_currencies=("CZK", "EUR"),
        vat_rates=(0.0, 0.12, 0.21),
        vat_id_prefix="CZ",
    ),
    "DE": CountryProfile(
        code="DE", name="Germany",
        vat_format=r"DE\d{9}", tax_id_format=None,
        date_formats=("DD.MM.YYYY", "D.M.YYYY"),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.07, 0.19),
        vat_id_prefix="DE",
    ),
    "AT": CountryProfile(
        code="AT", name="Austria",
        vat_format=r"ATU\d{8}", tax_id_format=None,
        date_formats=("DD.MM.YYYY", "D.M.YYYY"),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.10, 0.13, 0.20),
        vat_id_prefix="AT",
    ),
    "FR": CountryProfile(
        code="FR", name="France",
        vat_format=r"FR[A-HJ-NP-Z0-9]{2}\d{9}", tax_id_format=None,
        date_formats=("DD/MM/YYYY", "DD.MM.YYYY"),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.055, 0.10, 0.20),
        vat_id_prefix="FR",
    ),
    "IT": CountryProfile(
        code="IT", name="Italy",
        vat_format=r"IT\d{11}", tax_id_format=None,
        date_formats=("DD/MM/YYYY",),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.04, 0.10, 0.22),
        vat_id_prefix="IT",
    ),
    "ES": CountryProfile(
        code="ES", name="Spain",
        vat_format=r"ES[A-Z0-9]\d{7}[A-Z0-9]", tax_id_format=None,
        date_formats=("DD/MM/YYYY",),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.04, 0.10, 0.21),
        vat_id_prefix="ES",
    ),
    "NL": CountryProfile(
        code="NL", name="Netherlands",
        vat_format=r"NL\d{9}B\d{2}", tax_id_format=None,
        date_formats=("DD-MM-YYYY", "DD/MM/YYYY"),
        default_currency="EUR", allowed_currencies=("EUR",),
        vat_rates=(0.0, 0.09, 0.21),
        vat_id_prefix="NL",
    ),
    "PL": CountryProfile(
        code="PL", name="Poland",
        vat_format=r"PL\d{10}", tax_id_format=None,
        date_formats=("DD.MM.YYYY", "YYYY-MM-DD"),
        default_currency="PLN", allowed_currencies=("PLN", "EUR"),
        vat_rates=(0.0, 0.05, 0.08, 0.23),
        vat_id_prefix="PL",
    ),
    "GB": CountryProfile(
        code="GB", name="United Kingdom",
        vat_format=r"GB\d{9}|GB\d{12}", tax_id_format=None,
        date_formats=("DD/MM/YYYY", "DD.MM.YYYY"),
        default_currency="GBP", allowed_currencies=("GBP", "EUR"),
        vat_rates=(0.0, 0.05, 0.20),
        vat_id_prefix="GB",
    ),
    "US": CountryProfile(
        code="US", name="United States",
        vat_format=None, tax_id_format=r"\d{2}-\d{7}",  # EIN
        date_formats=("MM/DD/YYYY", "M/D/YYYY"),
        default_currency="USD", allowed_currencies=("USD",),
        vat_rates=tuple(),  # sales tax handled separately, no fixed national rates
        vat_id_prefix=None,
    ),
}


GENERIC_PROFILE = CountryProfile(
    code="XX", name="Generic",
    vat_format=None, tax_id_format=None,
    date_formats=("YYYY-MM-DD", "DD.MM.YYYY", "DD/MM/YYYY", "MM/DD/YYYY"),
    default_currency="EUR",
    allowed_currencies=("EUR", "USD", "GBP", "CHF", "PLN", "CZK", "HUF", "SEK", "NOK", "DKK"),
    vat_rates=tuple(),
    vat_id_prefix=None,
)


# Map currency hints to default country profile (used when no VAT prefix found).
CURRENCY_TO_COUNTRY = {
    "USD": "US",
    "GBP": "GB",
    "PLN": "PL",
    "CZK": "CZ",
}


def detect_country(
    explicit_code: str | None,
    vendor_vat: str | None,
    currency: str | None,
) -> CountryProfile:
    """Pick a country profile from explicit code, VAT prefix, or currency hint."""
    if explicit_code and explicit_code.upper() in PROFILES:
        return PROFILES[explicit_code.upper()]

    if vendor_vat:
        prefix = vendor_vat.strip().upper()[:2]
        if prefix in PROFILES:
            return PROFILES[prefix]

    if currency:
        country = CURRENCY_TO_COUNTRY.get(currency.upper())
        if country and country in PROFILES:
            return PROFILES[country]

    return GENERIC_PROFILE
