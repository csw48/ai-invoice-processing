import pymupdf

from app.services.pdf import extract_pdf_text, extract_pdf_text_with_positions


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


def test_extract_pdf_text_with_positions_uses_ocr_for_image_only_pdf():
    image_doc = pymupdf.open()
    image_page = image_doc.new_page(width=600, height=200)
    image_page.insert_text((30, 80), "OCR Firma s.r.o.", fontsize=28)
    image_page.insert_text((30, 125), "Total: 149.44 EUR", fontsize=28)
    pixmap = image_page.get_pixmap(dpi=180)

    pdf_doc = pymupdf.open()
    pdf_page = pdf_doc.new_page(width=600, height=200)
    pdf_page.insert_image(pdf_page.rect, stream=pixmap.tobytes("png"))
    pdf_bytes = pdf_doc.tobytes()

    raw_text, word_positions = extract_pdf_text_with_positions(pdf_bytes)

    assert "OCR Firma" in raw_text
    assert "149.44" in raw_text
    assert word_positions
