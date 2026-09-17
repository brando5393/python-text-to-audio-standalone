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

# Some PDFs don't encode real line breaks around structural content at all -- a table of
# contents can extract as one continuous run of text with no newlines to split on, which
# defeats every line-based check above. A run of 4+ consecutive "Chapter <number>" tokens
# is still a reliable, low-risk signal of a ToC listing even with no line boundaries: real
# prose essentially never says "Chapter 1 Chapter 2 Chapter 3 Chapter 4" back to back, and
# a single genuine chapter heading (a real, wanted structural cue) never hits this count.
_CHAPTER_LISTING_RUN = re.compile(r"(?:\bChapter\s+\d+\b[.,:]?\s*){4,}", re.IGNORECASE)

# An inline "page N / total" marker (e.g. "1 / 301") glued into the surrounding text with
# no delimiter of its own -- common in PDFs exported with a running page-number stamp. No
# trailing \b: the digits are often glued directly onto the next word with no separator
# at all ("1 / 301Full Text Archive..."), and a digit followed by a letter is not a word
# boundary, so requiring one there would silently never match the exact case this exists for.
_INLINE_PAGE_FRACTION = re.compile(r"(?<!\w)\d{1,4}\s*/\s*\d{1,4}")

# A site-attribution/watermark phrase is often glued directly onto a page-number stamp
# with no separating space at all (see above) -- but a plain "starts with a capital
# letter" check can't tell that apart from the next real sentence simply starting there
# too ("...1 / 301Full Text Archive It is a truth..." -- "It" looks identical to "Archive"
# by case alone). Repetition is the tiebreaker: the exact same glued phrase appearing this
# way 3+ times across the document is a watermark; a one-off is almost certainly just a
# sentence that happened to start right where a stray page stamp landed.
_GLUED_TITLE_RUN = re.compile(r"[A-Z][A-Za-z]*(?:\s[A-Z][A-Za-z]*){0,5}")

# A word broken across a PDF line wrap ("exam-\nple") extracts as a trailing hyphen
# immediately before the newline. Requiring a lowercase letter on both sides is what
# keeps this from mangling a real hyphenated compound word or name that happens to fall
# at a line break ("Anne-\nMarie", "Well-\nKnown"): those almost always continue with a
# capital letter, which this pattern deliberately excludes. A genuine mid-word wrap
# almost always continues in lowercase, which is what makes the two distinguishable at
# all without a dictionary.
_LINE_WRAP_HYPHEN = re.compile(r"([a-z])-\s*\n\s*([a-z])")

# A citation/footnote marker rendered as "[12]" or "[12, 34]" in extracted text. Square
# brackets containing only digits (and separators between multiple numbers) are
# essentially never meant to be read aloud as prose -- unlike "[Laughter]" or "[sic]",
# which contain letters and are deliberately left untouched by requiring digits here.
_BRACKETED_CITATION = re.compile(r"\s?\[\d{1,3}(?:\s*[,;–-]\s*\d{1,3})*\]")

# Superscript-digit footnote markers ("the effect¹² was profound") are an
# unambiguous non-prose signal on their own -- real sentences don't contain superscript
# digits -- so these are stripped before NFKC normalization converts them into ordinary
# glued digits (see below), at which point they'd be indistinguishable from real numbers.
_SUPERSCRIPT_DIGITS = re.compile(r"[⁰¹²³⁴-⁹]+")

# A footnote number glued directly onto the end of one sentence and the start of the
# next with no separating space at all ("...well established.12The next paragraph...").
# Requiring a lowercase letter immediately before the period rules out decimal numbers
# ("3.14Something" never matches, since the character before "." is a digit, not a
# letter), and requiring no space before the following capital keeps this narrow to the
# exact glued pattern real footnote extraction produces, mirroring the page-stamp case above.
_GLUED_FOOTNOTE_NUMBER = re.compile(r"(?<=[a-z])\.(\d{1,3})(?=[A-Z])")

# A bullet-point glyph at the start of a line (only genuine bullet characters, never a
# plain hyphen or em dash, since those are also used for dialogue attribution in novels
# and would be wrong to strip). TTS engines either skip these silently or mispronounce
# them, so the glyph itself is dropped while the real list-item text after it is kept.
_BULLET_MARKER = re.compile(r"^[•‣◦▪▸●○]\s*")


def sanitize(text):
    """Cleans extracted document text before it reaches a TTS engine.

    Addresses problems seen in real extracted text: tables of contents and running
    headers/footers get read aloud verbatim word for word (a long table of contents can
    turn into many minutes of a voice reading page numbers), broken/garbled Unicode from
    PDF extraction produces strange or garbled vocal output, duplicated characters or
    words from extraction artifacts cause mispronunciations and stutters, words broken
    across a PDF line wrap get read as two nonsense fragments, footnote/citation markers
    (bracketed, superscript, or glued onto sentence-ending punctuation) get read aloud as
    stray numbers, and bullet-point glyphs get skipped or mispronounced instead of just
    being dropped.

    Generic number/date/currency expansion (e.g. "$5.99" -> "five dollars and ninety nine
    cents") is deliberately not attempted here: both TTS engines this app supports
    (espeak-ng behind Piper, and Windows SAPI behind pyttsx3) already do reasonable,
    locale-aware number normalization of their own, and a second, cruder pass here would
    only add a new way to get it wrong for uncertain benefit.
    """
    text = _LINE_WRAP_HYPHEN.sub(r"\1\2", text)

    lines = text.split("\n")
    lines = [_BULLET_MARKER.sub("", line) for line in lines]
    text = "\n".join(_drop_boilerplate_lines(lines))

    text = _CHAPTER_LISTING_RUN.sub(" ", text)
    text = _strip_glued_page_stamps(text)
    text = _BRACKETED_CITATION.sub("", text)
    text = _SUPERSCRIPT_DIGITS.sub("", text)
    text = _GLUED_FOOTNOTE_NUMBER.sub(". ", text)

    text = ftfy.fix_text(text)  # fixes mojibake/broken encodings from bad extraction
    text = unicodedata.normalize("NFKC", text)  # ligatures (ﬁ -> fi), compatibility forms
    text = _CONTROL_CHARS.sub("", text)

    text = _REPEATED_LETTER.sub(r"\1\1", text)
    text = _REPEATED_WORD.sub(r"\1", text)

    return text


def _strip_glued_page_stamps(text):
    """Removes inline page-number stamps, plus a fixed watermark phrase glued directly
    onto them with no separating space, if the document has one.

    The tricky part is telling the watermark's own words apart from the next real
    sentence's words, which can be glued on exactly the same way and look identical by
    case alone ("...1 / 301Full Text Archive It is a truth..." -- "It" is capitalized for
    the same reason "Archive" is). A per-occurrence word count can't tell them apart, so
    this instead finds the single N-word prefix shared by a strong majority of every
    glued occurrence in the whole document, growing N only while that majority holds --
    real trailing words vary occurrence to occurrence and so never form a majority,
    which is what makes the boundary between "the watermark" and "the next sentence"
    detectable at all. A document with no repeating watermark still gets its bare page
    stamps removed either way; a page number is never worth reading aloud regardless.
    """
    matches = list(_INLINE_PAGE_FRACTION.finditer(text))
    if not matches:
        return text

    glued_words_at = {}
    for m in matches:
        glued_match = _GLUED_TITLE_RUN.match(text, m.end())
        glued_words_at[m.start()] = glued_match.group(0).split() if glued_match else []

    total_glued = sum(1 for words in glued_words_at.values() if words)
    watermark_words = []
    if total_glued:
        for n in range(1, 7):
            prefix_counts = Counter(
                tuple(words[:n]) for words in glued_words_at.values() if len(words) >= n
            )
            if not prefix_counts:
                break
            top_prefix, top_count = prefix_counts.most_common(1)[0]
            if top_count < _REPEATED_LINE_MIN_COUNT or top_count < 0.5 * total_glued:
                break
            watermark_words = list(top_prefix)

    parts = []
    last_end = 0
    for m in matches:
        parts.append(text[last_end:m.start()])
        parts.append(" ")
        words = glued_words_at[m.start()]
        if watermark_words and words[: len(watermark_words)] == watermark_words:
            last_end = m.end() + len(" ".join(words[: len(watermark_words)]))
        else:
            last_end = m.end()
    parts.append(text[last_end:])
    return "".join(parts)


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
