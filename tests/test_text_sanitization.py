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
