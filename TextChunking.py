import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# A book-length text synthesized in one Piper/SAPI call can run for a very long time with
# zero feedback and no way to tell "still working" from "stuck". Chunking keeps each call
# short, lets progress be reported, and means one bad chunk doesn't lose the whole book.
MAX_CHUNK_CHARS = 3000


def split_into_chunks(text, max_chars=MAX_CHUNK_CHARS):
    """Splits `text` into chunks of roughly `max_chars`, breaking on sentence boundaries
    where possible so playback doesn't cut off mid-sentence between audio segments."""
    sentences = _SENTENCE_END.split(text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > max_chars:
            chunks.append(current)
            current = sentence
        elif len(sentence) > max_chars:
            # A single sentence longer than the limit: hard-split it so no chunk is ever
            # too large for the engine, even if it means a mid-sentence audio boundary.
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(sentence), max_chars):
                chunks.append(sentence[i:i + max_chars])
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks
