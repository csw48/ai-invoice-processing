"""Pure normalization helpers (brief Step 2 — extraction normalization rules).

Kept separate from the extractors so the rules can be unit-tested in isolation
and applied by any extractor (deterministic regex or LLM).
"""
from __future__ import annotations

# Brief §"number length": a document/invoice number may be at most 16 characters.
MAX_NUMBER_LEN = 16


def normalize_number(value: str | None) -> str | None:
    """Cap a document/invoice number at MAX_NUMBER_LEN characters.

    If it is longer, trim from the LEFT and prepend ``*`` so the most specific
    (right-hand) part is preserved. Brief example:
        ``218756-3701-2026-1827`` (21 chars) -> ``*-3701-2026-1827`` (16 chars).

    Returns the input unchanged when it is None or already within the limit.
    """
    if value is None:
        return None
    s = str(value).strip()
    if len(s) <= MAX_NUMBER_LEN:
        return s
    # Keep the rightmost (MAX_NUMBER_LEN - 1) characters; the '*' marks truncation.
    return "*" + s[-(MAX_NUMBER_LEN - 1):]
