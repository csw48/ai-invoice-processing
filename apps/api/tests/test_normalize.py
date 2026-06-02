from app.services.normalize import normalize_number


def test_short_number_unchanged():
    assert normalize_number("INV-2026-001") == "INV-2026-001"


def test_exactly_16_chars_unchanged():
    value = "ABCD-1234-5678-9"  # 16 chars
    assert len(value) == 16
    assert normalize_number(value) == value


def test_long_number_trimmed_from_left_with_star_prefix():
    # Brief example: 21-char number -> 16-char "*-..." keeping the right-hand part.
    assert normalize_number("218756-3701-2026-1827") == "*-3701-2026-1827"
    assert len(normalize_number("218756-3701-2026-1827")) == 16


def test_none_passthrough():
    assert normalize_number(None) is None


def test_whitespace_trimmed():
    assert normalize_number("  INV-1  ") == "INV-1"
