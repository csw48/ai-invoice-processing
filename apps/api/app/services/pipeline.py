from typing import Callable

from app.country_profiles import detect_country
from app.models import ClientConfig, EnrichedInvoice, ExtractedInvoice, ProcessedInvoice
from app.services.extract import extract_invoice_fields
from app.services.formatters import format_invoice
from app.services.validate import validate_invoice


Extractor = Callable[[str], ExtractedInvoice]


def process_invoice(
    raw_text: str,
    config: ClientConfig,
    extractor: Extractor | None = None,
) -> ProcessedInvoice:
    extract = extractor or extract_invoice_fields
    extracted = extract(raw_text)
    validation = validate_invoice(extracted, config)
    enriched = EnrichedInvoice(extracted=extracted)
    formatted = format_invoice(enriched, config.output_connector)

    profile = detect_country(
        explicit_code=config.country_code,
        vendor_vat=extracted.vendor_vat.value if extracted.vendor_vat else None,
        currency=extracted.currency.value if extracted.currency else None,
    )

    return ProcessedInvoice(
        extracted=extracted,
        validation=validation,
        enriched=enriched,
        formatted=formatted,
        country_code=profile.code,
    )
