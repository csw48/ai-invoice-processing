import pymupdf

from app.services.pdf import extract_pdf_text


def _build_pdf_bytes(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    return doc.tobytes()


def test_extract_pdf_text_returns_visible_text():
    pdf_bytes = _build_pdf_bytes("Firma Test s.r.o.\nVAT: SK1234567890")

    raw_text = extract_pdf_text(pdf_bytes)

    assert "Firma Test s.r.o." in raw_text
    assert "SK1234567890" in raw_text
