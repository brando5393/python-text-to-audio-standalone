import re
import unicodedata
from collections import Counter

import ftfy

# A classic table-of-contents entry: some title text, a run of dot leaders, then a page
# number ("Chapter One .......... 14"). Matched before whitespace gets collapsed, so line
# boundaries from the original extracted text still exist.
_DOT_LEADER_LINE = re.compile(r"^.{2,80}?\.{4,}\s*\d{1,4}\s*$")
_PAGE_NUMBER_LINE = re.compile(r"^\s*(page\s+)?\d{1,4}\s*(of\s+\d{1,4})?\s*$", re.IGNORECASE)

# A running header/footer (book title, chapter name) repeats verbatim on most pages of
# an extracted PDF. Any short line appearing this often is almost certainly one, not
# something meant to be read aloud once per occurrence.
_REPEATED_LINE_MIN_COUNT = 3
_REPEATED_LINE_MAX_CHARS = 80

# Collapses OCR/extraction artifacts like "theee" to "thee" rather than "the" -- capped
# at 2 repeats instead of 1 so legitimate stretched spelling ("aaah") survives.
_REPEATED_LETTER = re.compile(r"([A-Za-z])\1{2,}")
_REPEATED_WORD = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)

# Non-printing control characters that sometimes survive PDF/DOCX extraction and produce
# odd TTS output. Tab and newline are handled separately by the caller's own whitespace
# collapsing, so they're deliberately left out here.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def sanitize(text):
    """Cleans extracted document text before it reaches a TTS engine.

    Addresses three problems seen in real extracted text: tables of contents and running
    headers/footers get read aloud verbatim word for word (a long table of contents can
    turn into many minutes of a voice reading page numbers), broken/garbled Unicode from
    PDF extraction produces strange or garbled vocal output, and duplicated characters or
    words from extraction artifacts cause mispronunciations and stutters.
    """
    lines = text.split("\n")
    text = "\n".join(_drop_boilerplate_lines(lines))

    text = ftfy.fix_text(text)  # fixes mojibake/broken encodings from bad extraction
    text = unicodedata.normalize("NFKC", text)  # ligatures (ﬁ -> fi), compatibility forms
    text = _CONTROL_CHARS.sub("", text)

    text = _REPEATED_LETTER.sub(r"\1\1", text)
    text = _REPEATED_WORD.sub(r"\1", text)

    return text


def _drop_boilerplate_lines(lines):
    repeat_counts = Counter(
        stripped for line in lines if (stripped := line.strip()) and len(stripped) <= _REPEATED_LINE_MAX_CHARS
    )
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append(line)
        elif _DOT_LEADER_LINE.match(stripped) or _PAGE_NUMBER_LINE.match(stripped):
            continue
        elif repeat_counts.get(stripped, 0) >= _REPEATED_LINE_MIN_COUNT:
            continue
        else:
            kept.append(line)
    return kept
