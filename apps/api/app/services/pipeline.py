from typing import Callable
from uuid import UUID

from app.country_profiles import detect_country
from app.models import (
    Classification,
    ClientConfig,
    DocumentType,
    EnrichedInvoice,
    ExtractedInvoice,
    InvoiceStatus,
    ProcessedInvoice,
    ValidationReport,
)
from app.services.classify import classify_document
from app.services.enrich import enrich_invoice
from app.services.extract import extract_invoice_fields, fill_delivered_at, fill_missing_line_items
from app.services.formatters import format_invoice
from app.services.log import LogFn, timed_step
from app.services.validate import validate_invoice


Extractor = Callable[[str], ExtractedInvoice]
Classifier = Callable[[str], Classification]

_NON_INVOICE_STATUS = {
    DocumentType.other: InvoiceStatus.redirect,
    DocumentType.junk: InvoiceStatus.discarded,
}


def process_invoice(
    raw_text: str,
    config: ClientConfig,
    client_id: str,
    extractor: Extractor | None = None,
    classifier: Classifier | None = None,
    vendor_repository=None,
    invoice_repository=None,
    log_fn: LogFn | None = None,
    invoice_id: UUID | None = None,
) -> ProcessedInvoice:
    extract = extractor or extract_invoice_fields
    classify = classifier or classify_document

    with timed_step(log_fn, "classify", {"text_chars": len(raw_text)}, invoice_id) as out:
        fallback_reason = None
        try:
            classification = classify(raw_text)
        except Exception as exc:
            fallback_reason = str(exc)
            classification = classify_document(raw_text)
        output = {"document_type": classification.document_type.value}
        if fallback_reason:
            output["fallback"] = "deterministic"
            output["fallback_reason"] = fallback_reason
        out.append(output)

    # Conditional execution: only invoices/credit notes go through extraction.
    if not classification.needs_extraction:
        return _short_circuit(classification, invoice_id)

    with timed_step(log_fn, "extract", {"text_chars": len(raw_text)}, invoice_id) as out:
        fallback_reason = None
        try:
            extracted = extract(raw_text)
        except Exception as exc:
            fallback_reason = str(exc)
            extracted = extract_invoice_fields(raw_text)
        extracted = fill_missing_line_items(extracted, raw_text)
        extracted = fill_delivered_at(extracted)
        output = {"fields_extracted": len(type(extracted).model_fields)}
        if fallback_reason:
            output["fallback"] = "deterministic"
            output["fallback_reason"] = fallback_reason
        out.append(output)

    with timed_step(log_fn, "validate", {"required": config.fields_required}, invoice_id) as out:
        validation = validate_invoice(extracted, config)
        out.append({"valid": validation.valid, "issues": len(validation.issues)})

    with timed_step(log_fn, "enrich", {"vendor_vat": extracted.vendor_vat.value if extracted.vendor_vat else None}, invoice_id) as out:
        enriched = enrich_invoice(extracted, vendor_repository, invoice_repository, client_id)
        out.append({"duplicate": enriched.duplicate, "vendor_matched": bool(enriched.vendor_metadata)})

    with timed_step(log_fn, "format", {"connector": config.output_connector}, invoice_id) as out:
        formatted = format_invoice(enriched, config.output_connector, classification.document_type.value)
        out.append({"type": formatted.get("type")})

    profile = detect_country(
        explicit_code=config.country_code,
        vendor_vat=extracted.vendor_vat.value if extracted.vendor_vat else None,
        currency=extracted.currency.value if extracted.currency else None,
    )

    kwargs = dict(
        classification=classification,
        extracted=extracted,
        validation=validation,
        enriched=enriched,
        formatted=formatted,
        country_code=profile.code,
    )
    if invoice_id is not None:
        kwargs["invoice_id"] = invoice_id
    return ProcessedInvoice(**kwargs)


def _short_circuit(classification: Classification, invoice_id: UUID | None) -> ProcessedInvoice:
    """Build a minimal result for non-invoice documents (junk / other).

    Extraction, validation, enrichment and formatting are skipped.
    """
    empty = ExtractedInvoice()
    kwargs = dict(
        status=_NON_INVOICE_STATUS[classification.document_type],
        classification=classification,
        extracted=empty,
        validation=ValidationReport(valid=True, issues=[]),
        enriched=EnrichedInvoice(extracted=empty),
        formatted={"type": "skipped", "reason": classification.document_type.value},
    )
    if invoice_id is not None:
        kwargs["invoice_id"] = invoice_id
    return ProcessedInvoice(**kwargs)
