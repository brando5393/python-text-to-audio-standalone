import MediaKeys as mk


def test_resolve_command_maps_known_hotkey_ids():
    assert mk.resolve_command(1) == "play_pause"
    assert mk.resolve_command(2) == "stop"
    assert mk.resolve_command(3) == "next"
    assert mk.resolve_command(4) == "previous"


def test_resolve_command_returns_none_for_unknown_id():
    assert mk.resolve_command(999) is None


def test_dispatch_calls_the_matching_action():
    calls = []
    actions = {"play_pause": lambda: calls.append("play_pause")}
    result = mk.dispatch("play_pause", actions)
    assert result is True
    assert calls == ["play_pause"]


def test_dispatch_returns_false_for_unmapped_command():
    calls = []
    actions = {"play_pause": lambda: calls.append("play_pause")}
    result = mk.dispatch("next", actions)
    assert result is False
    assert calls == []


def test_dispatch_returns_false_for_unknown_command_name():
    result = mk.dispatch("not_a_real_command", {})
    assert result is False


def test_dispatch_does_not_call_unrelated_actions():
    calls = []
    actions = {
        "play_pause": lambda: calls.append("play_pause"),
        "stop": lambda: calls.append("stop"),
        "next": lambda: calls.append("next"),
        "previous": lambda: calls.append("previous"),
    }
    mk.dispatch("stop", actions)
    assert calls == ["stop"]


def test_full_hotkey_id_to_action_pipeline():
    """End-to-end of the two pure pieces together (resolve_command then dispatch),
    which is exactly what MediaKeyHook's WM_HOTKEY handler does -- this is the part of
    the media-key feature that can be verified without a real OS hook."""
    calls = []
    actions = {"next": lambda: calls.append("next")}
    command = mk.resolve_command(3)
    assert mk.dispatch(command, actions) is True
    assert calls == ["next"]
