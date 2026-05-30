# Invoice Processing Pipeline — Implementation Brief

Brief for Claude Code. Goal: an AP (accounts payable) invoice processing app.
OCR/extraction already exists — we're adding classification, structured extraction, validation and routing.

Inspired by the E.ON × Hypatos architecture, but deliberately **heavily simplified**. The original
handles 14+ document types, SAP/VIM mapping and a team of agents for German VAT coding — none of that
belongs here. We stick to three steps.

---

## Architectural decision (read first)

**3 steps, not 1 big agent, not 7 small ones.**

```
OCR (exists) → Classification → [if invoice/credit_note] → Extraction → Validation
                              → [if junk/other]          → stop / redirect
```

Principles to respect:

1. **Classification is separate from extraction.** Reason: if a document is junk, we don't run
   expensive extraction. Conditional execution saves cost.
2. **Validation is NOT an LLM.** It's deterministic code. The LLM must not compute
   `net + tax = gross` because it rounds unreliably. The validator takes the finished JSON and
   returns a list of error codes.
3. **Each step has one input and one output**, so it can be tested in isolation.

What NOT to do (over-engineering we don't need):
- no team of sub-agents for tax coding
- no dozens of document types — four is enough
- no SAP/VIM/ERP integration
- no dual PO indexes and master-data matching unless the business actually requires it

---

## Step 1 — Document classification

LLM step. Input: OCR text. Output: document type + sender/recipient.

### Document types (simplified set)
- `invoice`
- `credit_note`
- `other`
- `junk`

(Expand only if the business genuinely needs it. E.ON has 14+ because of SAP, we don't.)

### Core classification logic
- **Classify by context, NOT by the document title.** A title like "Invoice" does not mean
  the document is an invoice.
- First try to assign "non-invoice" types (junk, other, credit_note). Treat `invoice` as the
  last resort — only if nothing else fits.
- **Two-stage invoice validation**: a document is an `invoice` only if it has (a) a net amount,
  (b) a clear sender AND recipient. Otherwise → `other`.
- **Override rules at the end**: e.g. an invoice with a negative payable amount → `credit_note`.

### Sender / recipient identification (this prevents a lot of errors)
- Take the **sender** from the **footer** of the document — that's where the full legal name +
  bank details (IBAN, SWIFT) usually live.
- The entity with the **payment details** is **always the sender**, never the recipient.
- Take the **recipient** only from a place where the **name + full postal address appear together**.
  NEVER from running text, a note, or the footer.
- Sender and recipient must be **different** entities.

### Step 1 output (example)
```json
{
  "documentType": "invoice",
  "typeReasoning": "short reasoning for debugging",
  "sender": { "companyName": "...", "address": "...", "vatId": "..." },
  "recipient": { "companyName": "...", "address": "...", "vatId": "..." }
}
```

---

## Step 2 — Extraction to JSON

LLM step. Runs **only if** the type is `invoice` or `credit_note`.

### Fixed output schema
```json
{
  "type": "<string>",
  "number": "<string>",
  "issuedAt": "<DD.MM.YYYY>",
  "deliveredAt": "<DD.MM.YYYY>",
  "currency": "<ISO 4217>",
  "sender": {
    "companyName": "", "address": "", "postcode": "", "city": "",
    "country": "<ISO ALPHA-2>", "vatId": "", "taxNumber": "",
    "contactName": "", "contactMail": ""
  },
  "recipient": {
    "companyName": "", "address": "", "postcode": "", "city": "",
    "country": "<ISO ALPHA-2>", "vatId": "",
    "contactName": "", "contactPhone": "", "emailRecipient": ""
  },
  "totals": {
    "net": 0, "gross": 0, "due": 0,
    "tax": [ { "rate": 0, "amount": 0, "net": 0 } ]
  }
}
```

### Normalization rules
- **`deliveredAt`**: use the service/delivery date (Leistungsdatum/Lieferdatum). If missing,
  fall back to `issuedAt`.
- **`number`** (if there are multiple candidates, priority order): case number → proceedings number →
  invoice number → reference number. Return the single most relevant one.
- **`number` length**: max 16 characters. If it exceeds that, trim from the left and prepend `*`.
  Example: `218756-3701-2026-1827` → `*-3701-2026-1827`.
- **Transcribe numbers exactly** as on the document — do not round, do not reformat.
- **Currencies and units** kept as on the document (€, $, £).
- `country` as ISO ALPHA-2 (DE, SK, AT…).
- `currency` as ISO 4217 (EUR, USD…).

---

## Step 3 — Validation (deterministic code, NOT an LLM)

Pure function: `validate(invoiceJson) -> string[]` (list of error codes + descriptions).

### Error codes
| Code | Condition |
|------|-----------|
| E02 | missing `totals.net` OR `totals.gross` OR `totals.tax[0].amount` |
| E03 | `net + tax != gross` (first verify all exist, then round to 2 decimals) |
| E04 | incomplete supplier (sender) data — a required field is missing |
| E05 | incomplete recipient data — a required field is missing |

### E03 logic (mind the order)
1. first verify that `net`, `gross`, `tax[0].amount` exist and are numbers
2. only then compute: `round(net + tax_amount, 2) != round(gross, 2)` → E03

### Optional extensions (if needed)
- **Duplicate detection**: match on `number` + `issuedAt` + `net` + sender → possible duplicate
  (similarity threshold ~0.9).
- **VAT ID mismatch**: if the VAT ID on the invoice differs from the one in master data.
- **Low-confidence flag**: if extraction returns low confidence on a key field.

The validator returns a list of codes and modifies nothing. Easy to cover with unit tests.

---

## Step 4 — Routing / orchestration

Simple state flow (a function/switch is enough, no heavy workflow engine needed):

```
result = classify(ocr_text)

if result.documentType in ["invoice", "credit_note"]:
    data   = extract(ocr_text)
    errors = validate(data)
    return { data, errors }
else:
    return { documentType: result.documentType, action: "redirect/manual" }
```

- `junk` → discard / archive
- `other` → manual handling or forward

---

## Implementation order (recommended)

1. **Validator** (Step 3) — pure code, no LLM, fastest win, immediately testable.
2. **Fixed JSON schema + extraction prompt** (Step 2) — you already have OCR, wire up extraction.
3. **Classification** (Step 1) — separate step before extraction.
4. **Orchestration** (Step 4) — wire it together and add conditional execution.

## Testing strategy
- Validator: unit tests with hand-crafted JSON (valid, E02, E03, E04, E05).
- Classification + extraction: a few real invoices of each type, compare output, iterate on the prompt.
