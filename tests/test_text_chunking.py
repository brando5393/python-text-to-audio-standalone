import TextChunking as tc


def test_short_text_is_a_single_chunk():
    chunks = tc.split_into_chunks("Just one short sentence.", max_chars=1000)
    assert chunks == ["Just one short sentence."]


def test_long_text_splits_on_sentence_boundaries():
    text = "This is a sentence. " * 200  # ~4000 chars
    chunks = tc.split_into_chunks(text, max_chars=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    # No chunk should end mid-sentence (mid-word): each should end with the
    # sentence-final period, since splitting only happens between sentences.
    for chunk in chunks:
        assert chunk.rstrip().endswith(".")


def test_single_sentence_longer_than_limit_is_hard_split():
    long_sentence = "word " * 500  # 2500 chars, no punctuation
    chunks = tc.split_into_chunks(long_sentence, max_chars=1000)
    assert len(chunks) == 3
    assert all(len(c) <= 1000 for c in chunks)


def test_empty_text_yields_no_chunks():
    assert tc.split_into_chunks("") == []


def test_whitespace_only_text_yields_no_chunks():
    assert tc.split_into_chunks("   \n\n  ") == []


def test_chunks_preserve_all_words():
    text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota."
    chunks = tc.split_into_chunks(text, max_chars=25)
    rejoined = " ".join(chunks)
    for word in ["Alpha", "beta", "gamma", "Delta", "epsilon", "zeta", "Eta", "theta", "iota"]:
        assert word in rejoined
