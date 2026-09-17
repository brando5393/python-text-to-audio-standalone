import os

import docx
import pypdf
import pytest
from ebooklib import epub

import TextExtraction as te


def test_extract_txt(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("Plain text content.", encoding="utf-8")
    assert te.extract_text(str(path)) == "Plain text content."


def test_extract_markdown_strips_common_syntax(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("# Heading\n\nSome **bold** and _italic_ text.\n", encoding="utf-8")
    result = te.extract_text(str(path))
    assert "#" not in result
    assert "*" not in result
    assert "Heading" in result
    assert "bold" in result


def test_extract_markdown_converts_links_to_plain_text(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("See [the docs](https://example.com) for more.", encoding="utf-8")
    result = te.extract_text(str(path))
    assert "https://example.com" not in result
    assert "the docs" in result


def test_extract_docx(tmp_path):
    doc = docx.Document()
    doc.add_paragraph("First paragraph.")
    doc.add_paragraph("Second paragraph.")
    path = tmp_path / "doc.docx"
    doc.save(str(path))
    result = te.extract_text(str(path))
    assert "First paragraph." in result
    assert "Second paragraph." in result


def test_extract_rtf(tmp_path):
    path = tmp_path / "note.rtf"
    path.write_text(r"{\rtf1\ansi Hello from RTF.\par}", encoding="utf-8")
    result = te.extract_text(str(path))
    assert "Hello from RTF." in result


def test_extract_html(tmp_path):
    path = tmp_path / "page.html"
    path.write_text("<html><body><h1>Title</h1><p>Body text.</p></body></html>", encoding="utf-8")
    result = te.extract_text(str(path))
    assert "Title" in result
    assert "Body text." in result


def test_extract_epub(tmp_path):
    book = epub.EpubBook()
    book.set_identifier("id1")
    book.set_title("Test Book")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml", lang="en")
    chapter.content = "<h1>Chapter One</h1><p>Some epub content.</p>"
    book.add_item(chapter)
    book.toc = (chapter,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    path = tmp_path / "book.epub"
    epub.write_epub(str(path), book)
    result = te.extract_text(str(path))
    assert "Some epub content." in result


def test_unsupported_extension_raises_value_error(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError):
        te.extract_text(str(path))


def test_supported_extensions_are_all_lowercase_with_dot():
    for ext in te.SUPPORTED_EXTENSIONS:
        assert ext.startswith(".")
        assert ext == ext.lower()


def _make_pdf(path, num_pages):
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)


def _make_epub(path, num_chapters):
    book = epub.EpubBook()
    book.set_identifier("id1")
    book.set_title("Test Book")
    book.set_language("en")
    chapters = []
    for i in range(num_chapters):
        chapter = epub.EpubHtml(title=f"Chapter {i + 1}", file_name=f"chap{i + 1}.xhtml", lang="en")
        chapter.content = f"<h1>Chapter {i + 1}</h1><p>Content for chapter {i + 1}.</p>"
        book.add_item(chapter)
        chapters.append(chapter)
    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters
    epub.write_epub(str(path), book)


def test_extract_structure_counts_pdf_returns_page_count(tmp_path):
    path = tmp_path / "doc.pdf"
    _make_pdf(path, 5)
    assert te.extract_structure_counts(str(path)) == (5, None)


def test_extract_structure_counts_epub_returns_chapter_count(tmp_path):
    path = tmp_path / "book.epub"
    _make_epub(path, 4)
    assert te.extract_structure_counts(str(path)) == (None, 4)


def test_extract_structure_counts_docx_counts_heading_1_paragraphs(tmp_path):
    doc = docx.Document()
    doc.add_paragraph("Chapter One", style="Heading 1")
    doc.add_paragraph("Some prose here.")
    doc.add_paragraph("Chapter Two", style="Heading 1")
    doc.add_paragraph("More prose here.")
    path = tmp_path / "doc.docx"
    doc.save(str(path))
    assert te.extract_structure_counts(str(path)) == (None, 2)


def test_extract_structure_counts_docx_returns_none_without_headings(tmp_path):
    doc = docx.Document()
    doc.add_paragraph("Just a plain paragraph with no heading style.")
    path = tmp_path / "doc.docx"
    doc.save(str(path))
    assert te.extract_structure_counts(str(path)) == (None, None)


def test_extract_structure_counts_txt_returns_none_none(tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("Plain text content.", encoding="utf-8")
    assert te.extract_structure_counts(str(path)) == (None, None)
