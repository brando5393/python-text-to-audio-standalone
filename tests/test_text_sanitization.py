import TextSanitization


def test_strips_dot_leader_toc_entries():
    text = "Chapter One .......... 14\nChapter Two .......... 42\nActual story text begins here."
    result = TextSanitization.sanitize(text)
    assert "Chapter One" not in result
    assert "Chapter Two" not in result
    assert "Actual story text begins here." in result


def test_strips_page_number_only_lines():
    text = "Some real content.\nPage 12\n42\nMore real content."
    result = TextSanitization.sanitize(text)
    assert "Page 12" not in result
    assert "Some real content." in result
    assert "More real content." in result


def test_strips_repeated_running_headers():
    lines = ["The Great Novel"] + [f"Paragraph number {i} of the story." for i in range(3)]
    # Simulate the header repeating on every "page" of the extracted document.
    text = "\n".join(["The Great Novel", lines[1], "The Great Novel", lines[2], "The Great Novel", lines[3]])
    result = TextSanitization.sanitize(text)
    assert "The Great Novel" not in result
    assert "Paragraph number 1" in result


def test_keeps_short_lines_that_do_not_repeat():
    text = "A short line.\nAnother short line.\nA third short one."
    result = TextSanitization.sanitize(text)
    assert "A short line." in result
    assert "Another short line." in result


def test_fixes_broken_unicode_mojibake():
    result = TextSanitization.sanitize("café")
    assert "caf" in result  # ftfy repairs mojibake; exact byte round-trip isn't the point here


def test_expands_ligatures_via_nfkc():
    result = TextSanitization.sanitize("ﬁle ﬂow")
    assert "file" in result
    assert "flow" in result


def test_collapses_repeated_letters():
    result = TextSanitization.sanitize("I really neeeeeed this.")
    assert "neeeeeed" not in result
    assert "need" in result


def test_collapses_repeated_words():
    result = TextSanitization.sanitize("This is the the correct answer.")
    assert "the the" not in result.lower()
    assert "the correct answer" in result


def test_removes_control_characters():
    result = TextSanitization.sanitize("Hello\x00World\x07!")
    assert "\x00" not in result
    assert "\x07" not in result
    assert "Hello" in result and "World" in result


def test_preserves_ordinary_prose_unchanged():
    text = "It was the best of times, it was the worst of times."
    assert TextSanitization.sanitize(text) == text


def test_strips_chapter_listing_run_with_no_newlines():
    """Regression test: some PDFs extract a table of contents as one continuous run of
    text with no newlines at all, which defeats every line-based check above."""
    toc = "Contents Chapter 1 Chapter 2 Chapter 3 Chapter 4 Chapter 5 Chapter 6 "
    text = toc + "It is a truth universally acknowledged, that a single man in want of a wife."
    result = TextSanitization.sanitize(text)
    assert "Chapter 1 Chapter 2" not in result
    assert "It is a truth universally acknowledged" in result


def test_keeps_single_genuine_chapter_heading():
    text = "Chapter 12 It was a dark and stormy night."
    result = TextSanitization.sanitize(text)
    assert "Chapter 12" in result


def test_strips_inline_page_fraction_glued_to_next_word():
    """Regression test: a page-number stamp like "1 / 301" is sometimes glued directly
    onto the next word with no separating space at all."""
    text = "the end of the chapter. 1 / 301Full speed ahead into the next one."
    result = TextSanitization.sanitize(text)
    assert "1 / 301" not in result


def test_strips_watermark_phrase_repeated_after_page_stamps_but_keeps_the_real_next_word():
    """Regression test based on a real failure: 'Full Text Archive' (a site watermark)
    was glued directly onto a page stamp 301 times throughout a real book, immediately
    followed by whatever word started the next page -- often a real word that also
    happens to be capitalized (a name, or the start of a new sentence). The watermark
    must be removed without eating that following word, and a one-off phrase that only
    glues on once (not a real repeating watermark) must be left alone entirely.
    """
    chunks = []
    people = ["Elizabeth", "Darcy", "Bingley", "Jane", "Wickham"]
    for i, person in enumerate(people):
        chunks.append(f"some page content ending here. {i + 1} / 301Full Text Archive {person} said something.")
    text = " ".join(chunks)

    result = TextSanitization.sanitize(text)

    assert "Full Text Archive" not in result
    for person in people:
        assert f"{person} said something." in result


def test_one_off_glued_word_is_not_mistaken_for_a_watermark():
    text = "the chapter ends. 1 / 50Suddenly, everything changed for the better."
    result = TextSanitization.sanitize(text)
    assert "Suddenly, everything changed for the better." in result


def test_rejoins_word_broken_across_a_pdf_line_wrap():
    """Regression scenario: many PDFs wrap justified text mid-word at the right margin,
    extracting a trailing hyphen immediately before the line's newline ("exam-\\nple").
    Read verbatim, this becomes two nonsense fragments instead of one word."""
    text = "This is a good exam-\nple of the problem, and another exam-\n   ple right after."
    result = TextSanitization.sanitize(text)
    assert "example of the problem" in result
    assert "example right after" in result
    assert "exam-" not in result


def test_keeps_a_real_hyphenated_name_split_across_a_line_wrap():
    """A genuine hyphenated proper noun that happens to fall at a line break ("Anne-\\nMarie")
    must not be silently fused into "AnneMarie" -- the capital letter after the break is
    what distinguishes it from an ordinary broken word, which always continues lowercase."""
    text = "Her full name was Anne-\nMarie, and everyone called her that."
    result = TextSanitization.sanitize(text)
    assert "Anne-\nMarie" in result or "Anne-Marie" in result
    assert "AnneMarie" not in result


def test_keeps_mid_sentence_hyphenated_compound_words_untouched():
    """Ordinary compound words that are NOT split across a line wrap (no newline glued to
    the hyphen) must never be touched by the line-wrap fix, which only ever fires on a
    hyphen immediately followed by a newline."""
    text = "It was a well-known fact that she was a strong-willed, self-aware woman."
    assert TextSanitization.sanitize(text) == text


def test_strips_bracketed_numeric_citation_markers():
    """Regression scenario: academic PDFs and articles often render footnote/citation
    references as bracketed numbers inline ("the theory[12] is well established."), which
    sound like stray digits when read aloud and carry no meaning in an audio narration."""
    text = "The theory[12] is well established, though later work[3, 4] complicates it."
    result = TextSanitization.sanitize(text)
    assert "[12]" not in result
    assert "[3, 4]" not in result
    assert "The theory is well established" in result
    assert "though later work complicates it" in result


def test_keeps_non_numeric_bracketed_stage_directions():
    """A bracketed annotation that contains letters, not digits, is real content meant to
    be read (or at least isn't a citation marker) -- e.g. transcript stage directions like
    "[Laughter]" or an editorial "[sic]" -- and must be left alone."""
    text = "That was hilarious [Laughter]. The article said the the [sic] answer was wrong."
    result = TextSanitization.sanitize(text)
    assert "[Laughter]" in result
    assert "[sic]" in result


def test_strips_superscript_footnote_markers():
    """A footnote marker is sometimes extracted as literal superscript Unicode digits
    glued directly onto a word ("the effect¹² was profound"), which is an
    unambiguous non-prose signal since ordinary sentences never contain superscript
    digits."""
    text = "The effect¹² was profound, though critics³ disagreed."
    result = TextSanitization.sanitize(text)
    assert "¹" not in result and "²" not in result and "³" not in result
    assert "The effect was profound" in result
    assert "though critics disagreed" in result


def test_strips_footnote_number_glued_between_sentences():
    """Regression scenario: a footnote number sometimes extracts as a plain digit glued
    directly onto the end of one sentence and the start of the next with no separating
    space at all ("...well established.12The next paragraph begins here.")."""
    text = "The theory is well established.12The next paragraph begins here."
    result = TextSanitization.sanitize(text)
    assert "established.12The" not in result
    assert "The theory is well established." in result
    assert "The next paragraph begins here." in result


def test_keeps_decimal_numbers_that_precede_a_capitalized_word():
    """A decimal number must never be mistaken for a glued footnote marker -- the digit
    before the decimal point (not a lowercase letter) is what rules this out, since real
    footnote markers only ever follow the end of a word, not another digit."""
    text = "The kit weighs 3.14Kilograms when fully assembled."
    result = TextSanitization.sanitize(text)
    assert "3.14Kilograms" in result


def test_strips_bullet_point_glyphs_but_keeps_the_list_text():
    """Bullet glyphs extracted from a PDF/EPUB list ("• First item") are either
    skipped silently or mispronounced by a TTS engine; the glyph should be dropped while
    the real list content after it is kept and still read aloud."""
    text = "Shopping list:\n• Milk\n• Eggs\n◦ Bread"
    result = TextSanitization.sanitize(text)
    assert "•" not in result and "◦" not in result
    assert "Milk" in result and "Eggs" in result and "Bread" in result


def test_decodes_leftover_html_entities():
    """Regression scenario: text pulled from web-sourced content (an HTML/EPUB file, or a
    document originally copy-pasted from a web page) sometimes carries literal HTML
    entities that were never decoded, which a TTS engine would otherwise read as gibberish
    ("ampersand a m p semicolon") instead of the character they represent."""
    text = "Rock &amp; Roll wasn&#39;t always called that &mdash; ask anyone."
    result = TextSanitization.sanitize(text)
    assert "&amp;" not in result and "&#39;" not in result and "&mdash;" not in result
    assert "Rock & Roll wasn't always called that" in result


def test_strips_zero_width_and_invisible_formatting_characters():
    """Regression scenario: copy-pasted or web-derived text sometimes carries truly
    invisible Unicode characters (zero-width space, zero-width joiner, a stray byte-order
    mark) that a human proofreading the source text would never see, since they render as
    nothing, but which can make a TTS engine stumble or insert an odd pause."""
    text = "This is a normal​ sentence﻿ with hidden‍ characters‌ inside."
    result = TextSanitization.sanitize(text)
    assert "​" not in result and "﻿" not in result
    assert "‍" not in result and "‌" not in result
    assert "This is a normal sentence with hidden characters inside." in result


def test_strips_soft_hyphens_without_touching_real_hyphens():
    """A soft hyphen (a discretionary line-break point) is invisible in normal rendering
    but sometimes leaks into extracted text as a literal character embedded mid-word
    ("respon­sibility"), regardless of whether the word ever actually wrapped there.
    A real hyphen in a compound word must be left completely untouched."""
    text = "It was her respon­sibility to finish the well-known task on time."
    result = TextSanitization.sanitize(text)
    assert "­" not in result
    assert "responsibility" in result
    assert "well-known" in result


def test_strips_symbol_divider_lines_but_keeps_real_content():
    """Regression scenario: both scanned and born-digital books commonly mark a
    scene/section break with a line of repeated symbol glyphs ("* * *", "-----",
    "======") instead of real words. Read verbatim, a TTS engine either spells out the
    glyph name or reads a long run of "asterisk" or "dash", which is never useful."""
    text = "The chapter ends here.\n* * *\nA new scene begins.\n------\nAnd another one starts."
    result = TextSanitization.sanitize(text)
    assert "* * *" not in result
    assert "------" not in result
    assert "The chapter ends here." in result
    assert "A new scene begins." in result
    assert "And another one starts." in result


def test_keeps_ordinary_sentences_with_punctuation_that_are_not_pure_dividers():
    """A line-start em dash (dialogue) or a sentence that merely contains punctuation must
    never be mistaken for a symbol-divider line -- only a line made ENTIRELY of one
    repeated symbol (optionally space-separated), 3+ times, qualifies."""
    text = "Wait... what did you just say?\nShe said, \"No -- not that one.\"\nMaybe... just maybe."
    assert TextSanitization.sanitize(text) == text


def test_keeps_dialogue_dashes_at_line_start():
    """French/European-style dialogue sometimes marks a new speaker with a leading dash
    or em dash at the start of a line, which is real, meaningful content and must never
    be stripped the way an actual bullet glyph is."""
    text = "— Are you coming? she asked.\n— Not yet, he replied."
    result = TextSanitization.sanitize(text)
    assert "— Are you coming?" in result
    assert "— Not yet, he replied." in result
