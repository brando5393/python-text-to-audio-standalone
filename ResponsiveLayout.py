"""Pure breakpoint logic for the main window's responsive layout.

Tk's `grid` geometry manager has no notion of "reflow" the way CSS flexbox/grid
does -- it only ever proportionally resizes a fixed arrangement of rows/columns.
To get bootstrap/React-style responsiveness (stacking columns below a width
threshold instead of just squeezing them), main.py binds to the root window's
`<Configure>` event and re-grids its section frames between a small number of
named layout "tiers" based on the current width. This module holds the pure,
easily-testable "which tier applies to this width" decision so that logic isn't
buried inside Tk event-handling code -- following the same split used elsewhere
in this codebase (see SleepTimer.py, PlaybackQueue.py).

Three tiers:
  - WIDE:   the original 3-column side-by-side arrangement (Files | Library |
            Actions+Playback), with the Settings drawer docked as a 4th column.
            Used once there's comfortably enough width for all three primary
            columns plus their minimum comfortable content width.
  - MEDIUM: two columns -- Files and Library share a row, Actions+Playback
            stacks full-width below them. A reasonable middle ground for
            common laptop widths (e.g. 1366px minus window chrome/taskbar)
            that are wide enough for two comfortable columns but not three.
  - NARROW: a single stacked column -- Files, then Library, then Actions, then
            Playback, each full width. Used for small/portrait-ish windows,
            where the content is reachable via vertical scrolling rather than
            being clipped or force-squeezed below a usable size.
"""

WIDE = "wide"
MEDIUM = "medium"
NARROW = "narrow"

# Each primary column reads comfortably starting around 300-340px (see the
# original files_frame column minsize of 340 and library/actions columns in
# main.py). Three side-by-side plus the settings-drawer's 260px want ~1150px;
# two side-by-side want ~700px. These thresholds are picked with headroom
# below those figures -- once a real window drops under them, forcing the old
# fixed 3/2-column arrangement started clipping or crushing content in real
# testing, so reflow kicks in first.
WIDE_BREAKPOINT = 1150
MEDIUM_BREAKPOINT = 760


def tier_for_width(width):
    """Returns which layout tier (WIDE, MEDIUM, or NARROW) applies at `width` pixels."""
    if width >= WIDE_BREAKPOINT:
        return WIDE
    if width >= MEDIUM_BREAKPOINT:
        return MEDIUM
    return NARROW
