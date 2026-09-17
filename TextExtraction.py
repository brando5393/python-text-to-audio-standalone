import os
import re
import shutil

import docx
import pypdf
from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub
from striprtf.striprtf import rtf_to_text

SUPPORTED_EXTENSIONS = (
    ".txt", ".md", ".pdf", ".epub", ".mobi", ".azw3", ".docx", ".rtf", ".html", ".htm",
)

_MARKDOWN_SYNTAX = re.compile(r"(^#{1,6}\s+|\*+|_+|`{1,3}|^>\s?|^-{3,}$)", re.MULTILINE)
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def extract_text(file_path):
    """Extracts plain text from a supported document. Raises ValueError for unsupported types."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        return _extract_txt(file_path)
    if ext == ".md":
        return _extract_markdown(file_path)
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".epub":
        return _extract_epub(file_path)
    if ext in (".mobi", ".azw3"):
        return _extract_mobi(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    if ext == ".rtf":
        return _extract_rtf(file_path)
    if ext in (".html", ".htm"):
        return _extract_html(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


def extract_structure_counts(file_path):
    """Returns (pages, chapters) for a document -- whichever concept applies to its
    format, None for the other. Cheap: reads structural metadata, not the full text.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _count_pdf_pages(file_path), None
    if ext == ".epub":
        return None, _count_epub_chapters(file_path)
    if ext in (".mobi", ".azw3"):
        return _count_mobi_structure(file_path)
    if ext == ".docx":
        return None, _count_docx_chapters(file_path)
    return None, None


def extract_chapters(file_path):
    """Returns a list of per-chapter plain text, in reading order, for a format where
    "chapter" is a real structural concept -- or None if the format has no such concept,
    or nothing that looks like a chapter boundary was actually found in this particular
    document. Used to offer splitting a converted audiobook into one file per chapter
    instead of a single long file, mirroring what dedicated audiobook tools do. Unlike
    extract_text(), this never raises for an unsupported format -- splitting is an
    opt-in convenience, so callers are expected to fall back to a single whole-file
    conversion when this returns None rather than treating it as an error.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".epub":
        return _extract_epub_chapters(file_path)
    if ext == ".docx":
        return _extract_docx_chapters(file_path)
    if ext in (".mobi", ".azw3"):
        return _extract_mobi_chapters(file_path)
    return None


def _extract_epub_chapters(path):
    book = epub.read_epub(path)
    chapters = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        if not item.is_chapter():
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator=" ").strip()
        if text:
            chapters.append(text)
    return chapters or None


def _extract_docx_chapters(path):
    # Same "Heading 1" heuristic as _count_docx_chapters: everything from one Heading 1
    # paragraph up to (not including) the next becomes one chapter's text, including the
    # heading itself so the chapter title is still read aloud, the same as it always was
    # in the un-split whole-document text. Anything before the first Heading 1 (a title
    # page, foreword, etc.) becomes its own leading chapter rather than being dropped.
    document = docx.Document(path)
    chapters = []
    current = []
    for p in document.paragraphs:
        if p.style and p.style.name == "Heading 1":
            if current:
                chapters.append("\n".join(current))
            current = [p.text]
        else:
            current.append(p.text)
    if current:
        chapters.append("\n".join(current))
    # Fewer than two chapters means no real Heading 1 boundary was found -- the whole
    # document just landed in one bucket, which isn't a split worth offering.
    if len(chapters) < 2:
        return None
    return chapters


def _extract_mobi_chapters(path):
    import mobi

    tempdir, extracted_path = mobi.extract(path)
    try:
        ext = os.path.splitext(extracted_path)[1].lower()
        if ext == ".epub":
            return _extract_epub_chapters(extracted_path)
        return None  # a PDF-based Kindle extraction has pages, not chapters
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def _count_pdf_pages(path):
    with open(path, "rb") as pdf_file:
        return len(pypdf.PdfReader(pdf_file).pages)


def _count_epub_chapters(path):
    # get_items_of_type(ITEM_DOCUMENT) also includes the navigation document itself
    # (a table of contents page, not a chapter) -- is_chapter() is False only for that.
    book = epub.read_epub(path)
    return sum(1 for item in book.get_items_of_type(ITEM_DOCUMENT) if item.is_chapter())


def _count_docx_chapters(path):
    # A rough but cheap heuristic: "Heading 1" is the conventional Word style for chapter
    # titles. None (not 0) when nothing matches -- an undetected chapter count is more
    # honestly "unknown" than "zero".
    document = docx.Document(path)
    count = sum(1 for p in document.paragraphs if p.style and p.style.name == "Heading 1")
    return count or None


def _count_mobi_structure(path):
    import mobi

    tempdir, extracted_path = mobi.extract(path)
    try:
        ext = os.path.splitext(extracted_path)[1].lower()
        if ext == ".epub":
            return None, _count_epub_chapters(extracted_path)
        if ext == ".pdf":
            return _count_pdf_pages(extracted_path), None
        return None, None
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


def _extract_txt(path):
    with open(path, "r", encoding="utf-8") as txt_file:
        return txt_file.read()


def _extract_markdown(path):
    with open(path, "r", encoding="utf-8") as md_file:
        raw = md_file.read()
    # A light strip of common syntax so headings/emphasis/links aren't read aloud
    # literally (e.g. "pound pound Chapter One" or "asterisk asterisk important").
    text = _MARKDOWN_LINK.sub(r"\1", raw)
    return _MARKDOWN_SYNTAX.sub("", text)


def _extract_pdf(path):
    text = ""
    with open(path, "rb") as pdf_file:
        reader = pypdf.PdfReader(pdf_file)
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


def _extract_docx(path):
    document = docx.Document(path)
    paragraphs = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            paragraphs.extend(cell.text for cell in row.cells)
    return "\n".join(paragraphs)


def _extract_rtf(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as rtf_file:
        return rtf_to_text(rtf_file.read())


def _extract_html(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as html_file:
        soup = BeautifulSoup(html_file.read(), "html.parser")
        return soup.get_text(separator=" ")
