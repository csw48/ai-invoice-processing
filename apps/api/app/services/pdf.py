from io import BytesIO

_MIN_PAGE_TEXT_CHARS = 20


def extract_pdf_text(content: bytes) -> str:
    raw_text, _ = extract_pdf_text_with_positions(content)
    return raw_text


def extract_pdf_text_with_positions(
    content: bytes,
    force_ocr: bool = False,
) -> tuple[str, list[dict]]:
    """Extract text AND word-level bounding boxes (normalised 0–1) from a PDF.

    Returns (raw_text, word_positions) where each word position is:
      {page, text, x0, y0, x1, y1}   — coordinates are fractions of page size.
    """
    import pymupdf
    words: list[dict] = []
    pages_text: list[str] = []

    with pymupdf.open(stream=BytesIO(content), filetype="pdf") as doc:
        for page_num, page in enumerate(doc):
            rect = page.rect
            w, h = rect.width, rect.height
            text_page = None
            page_text = page.get_text("text")
            if force_ocr or len(page_text.strip()) < _MIN_PAGE_TEXT_CHARS:
                try:
                    text_page = page.get_textpage_ocr(full=True)
                    page_text = page.get_text("text", textpage=text_page)
                except Exception:
                    text_page = None

            word_tuples = page.get_text("words", textpage=text_page) if text_page else page.get_text("words")
            for word_tuple in word_tuples:
                x0, y0, x1, y1, word_text = word_tuple[:5]
                if word_text.strip():
                    words.append({
                        "page": page_num,
                        "text": word_text,
                        "x0": round(x0 / w, 4),
                        "y0": round(y0 / h, 4),
                        "x1": round(x1 / w, 4),
                        "y1": round(y1 / h, 4),
                    })
            pages_text.append(page_text)

    return "\n".join(pages_text).strip(), words
