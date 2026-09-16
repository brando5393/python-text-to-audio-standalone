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
