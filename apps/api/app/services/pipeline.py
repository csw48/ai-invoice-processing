from app.models import ClientConfig, EnrichedInvoice, ProcessedInvoice
from app.services.extract import extract_invoice_fields
from app.services.formatters import format_invoice
from app.services.validate import validate_invoice


def process_invoice(raw_text: str, config: ClientConfig) -> ProcessedInvoice:
    extracted = extract_invoice_fields(raw_text)
    validation = validate_invoice(extracted, config)
    enriched = EnrichedInvoice(extracted=extracted)
    formatted = format_invoice(enriched, config.output_connector)
    return ProcessedInvoice(extracted=extracted, validation=validation, enriched=enriched, formatted=formatted)
