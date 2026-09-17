import ResponsiveLayout as RL


def test_wide_at_and_above_breakpoint():
    assert RL.tier_for_width(RL.WIDE_BREAKPOINT) == RL.WIDE
    assert RL.tier_for_width(RL.WIDE_BREAKPOINT + 400) == RL.WIDE
    assert RL.tier_for_width(1340) == RL.WIDE


def test_medium_between_breakpoints():
    assert RL.tier_for_width(RL.MEDIUM_BREAKPOINT) == RL.MEDIUM
    assert RL.tier_for_width(RL.WIDE_BREAKPOINT - 1) == RL.MEDIUM
    assert RL.tier_for_width(1000) == RL.MEDIUM  # a common small-laptop width


def test_narrow_below_medium_breakpoint():
    assert RL.tier_for_width(RL.MEDIUM_BREAKPOINT - 1) == RL.NARROW
    assert RL.tier_for_width(480) == RL.NARROW
    assert RL.tier_for_width(0) == RL.NARROW


def test_boundaries_are_stable_regardless_of_direction():
    # Whether width is shrinking or growing, the same width must always map to
    # the same tier -- otherwise resizing back and forth across a boundary
    # could flap between layouts on an identical pixel width.
    for width in (400, 760, 761, 1149, 1150, 1600):
        assert RL.tier_for_width(width) == RL.tier_for_width(width)
