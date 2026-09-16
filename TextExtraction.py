import os
import shutil

import PyPDF2
from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

SUPPORTED_EXTENSIONS = (".txt", ".pdf", ".epub", ".mobi", ".azw3")


def extract_text(file_path):
    """Extracts plain text from a supported document. Raises ValueError for unsupported types."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        return _extract_txt(file_path)
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".epub":
        return _extract_epub(file_path)
    if ext in (".mobi", ".azw3"):
        return _extract_mobi(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


def _extract_txt(path):
    with open(path, "r", encoding="utf-8") as txt_file:
        return txt_file.read()


def _extract_pdf(path):
    text = ""
    with open(path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def _extract_epub(path):
    book = epub.read_epub(path)
    parts = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        parts.append(soup.get_text(separator=" "))
    return " ".join(parts)


def _extract_mobi(path):
    """Unpacks a non-DRM MOBI/AZW3 file via KindleUnpack and extracts its text.

    DRM-protected Kindle store books cannot be decrypted here or anywhere without
    the owner's Kindle device key; those will fail extraction, which is expected.
    """
    import mobi

    tempdir, extracted_path = mobi.extract(path)
    try:
        ext = os.path.splitext(extracted_path)[1].lower()
        if ext == ".epub":
            return _extract_epub(extracted_path)
        if ext == ".pdf":
            return _extract_pdf(extracted_path)
        with open(extracted_path, "r", encoding="utf-8", errors="ignore") as html_file:
            soup = BeautifulSoup(html_file.read(), "html.parser")
            return soup.get_text(separator=" ")
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
