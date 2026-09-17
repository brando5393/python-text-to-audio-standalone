"""Pure "what's the next/previous file" logic for queue/playlist playback, kept
separate from Tkinter and `ConversionsLibrary` so it's directly unit-testable.

Deliberately does not wrap around from the last file back to the first: reaching the
end of the Conversions Library's current order stops playback (returns None) rather
than looping, which matches how the existing "finished naturally" behavior worked
before auto-play existed -- looping silently forever felt more surprising than useful
for a library that isn't a curated playlist.
"""


def next_file(current_path, ordered_paths):
    """Returns the file after `current_path` in `ordered_paths`, or None if there is
    none (empty list, `current_path` is the last entry, or nothing is playing yet --
    in which case the first file is used as a reasonable starting point)."""
    if not ordered_paths:
        return None
    if current_path not in ordered_paths:
        return ordered_paths[0]
    index = ordered_paths.index(current_path)
    if index + 1 >= len(ordered_paths):
        return None
    return ordered_paths[index + 1]


def previous_file(current_path, ordered_paths):
    """Returns the file before `current_path` in `ordered_paths`, or None if there is
    none (empty list, `current_path` is the first entry, or nothing is playing yet --
    in which case the last file is used as a reasonable starting point)."""
    if not ordered_paths:
        return None
    if current_path not in ordered_paths:
        return ordered_paths[-1]
    index = ordered_paths.index(current_path)
    if index - 1 < 0:
        return None
    return ordered_paths[index - 1]
