import os

import docx
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
