from io import BytesIO


def extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF.

    Returns the concatenated text of all pages, or an empty string for empty PDFs.
    """
    import pymupdf

    with pymupdf.open(stream=BytesIO(content), filetype="pdf") as doc:
        return "\n".join(page.get_text("text") for page in doc).strip()
