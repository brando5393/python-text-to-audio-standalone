import tkinter as tk

from MiniPlayer import MiniPlayer, format_time


class FakePlayer:
    def __init__(self, position=0, length=0, path=None):
        self.playing = False
        self.paused_calls = 0
        self.resumed_calls = 0
        self.stopped_calls = 0
        self.seek_calls = []
        self._position = position
        self._length = length
        self._path = path

    def is_playing(self):
        return self.playing

    def current_path(self):
        return self._path

    def pause(self):
        self.paused_calls += 1
        self.playing = False

    def resume(self):
        self.resumed_calls += 1
        self.playing = True

    def stop(self):
        self.stopped_calls += 1
        self.playing = False

    def position_ms(self):
        return self._position

    def length_ms(self):
        return self._length

    def seek_ms(self, position_ms):
        self.seek_calls.append(position_ms)
        self._position = position_ms


def test_mini_player_constructs_and_shows_now_playing(tk_root):
    now_playing_var = tk.StringVar(value="Now playing: test.wav")
    expand_calls = []
    mini = MiniPlayer(tk_root, FakePlayer(), now_playing_var, on_expand=lambda: expand_calls.append(1))
    assert mini.winfo_exists()
    mini.destroy()


def test_toggle_pause_pauses_when_playing(tk_root):
    player = FakePlayer()
    player.playing = True
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._toggle_pause()
    assert player.paused_calls == 1
    assert player.resumed_calls == 0
    mini.destroy()


def test_toggle_pause_resumes_when_not_playing(tk_root):
    player = FakePlayer()
    player.playing = False
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._toggle_pause()
    assert player.resumed_calls == 1
    assert player.paused_calls == 0
    mini.destroy()


def test_stop_calls_player_stop(tk_root):
    player = FakePlayer()
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._stop()
    assert player.stopped_calls == 1
    mini.destroy()


def test_stop_resets_progress_display(tk_root):
    player = FakePlayer(position=30000, length=120000)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._stop()
    assert mini.progress_var.get() == 0
    assert mini.time_var.get() == "0:00 / 0:00"
    mini.destroy()


def test_update_progress_reflects_player_position(tk_root):
    player = FakePlayer(position=30000, length=120000)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._update_progress()
    assert mini.progress_var.get() == 25.0
    assert mini.time_var.get() == "0:30 / 2:00"
    mini.destroy()


def test_update_progress_handles_nothing_loaded(tk_root):
    player = FakePlayer(position=0, length=0)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._update_progress()
    assert mini.progress_var.get() == 0
    assert mini.time_var.get() == "0:00 / 0:00"
    mini.destroy()


def test_update_progress_does_not_move_slider_while_dragging(tk_root):
    player = FakePlayer(position=30000, length=120000)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._dragging = True
    mini.progress_var.set(75)
    mini._update_progress()
    assert mini.progress_var.get() == 75  # untouched while the user is actively dragging
    mini.destroy()


def test_ending_drag_seeks_to_slider_position(tk_root):
    player = FakePlayer(position=0, length=100000)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini.progress_var.set(50)
    mini._end_drag(None)
    assert player.seek_calls == [50000.0]
    assert mini._dragging is False
    mini.destroy()


def test_ending_drag_does_nothing_when_nothing_loaded(tk_root):
    player = FakePlayer(position=0, length=0)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini.progress_var.set(50)
    mini._end_drag(None)
    assert player.seek_calls == []
    mini.destroy()


def test_restart_seeks_to_zero_when_something_loaded(tk_root):
    player = FakePlayer(position=45000, length=100000, path=r"C:\Books\a.wav")
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._restart()
    assert player.seek_calls == [0]
    mini.destroy()


def test_restart_does_nothing_when_nothing_loaded(tk_root):
    player = FakePlayer(position=0, length=0, path=None)
    mini = MiniPlayer(tk_root, player, tk.StringVar(), on_expand=lambda: None)
    mini._restart()
    assert player.seek_calls == []
    mini.destroy()


def test_format_time():
    assert format_time(0) == "0:00"
    assert format_time(30000) == "0:30"
    assert format_time(90000) == "1:30"
    assert format_time(3_661_000) == "61:01"


def test_closing_window_calls_on_expand(tk_root):
    expand_calls = []
    mini = MiniPlayer(tk_root, FakePlayer(), tk.StringVar(), on_expand=lambda: expand_calls.append(1))
    mini.protocol("WM_DELETE_WINDOW")  # querying the handler shouldn't itself invoke it
    # Simulate the OS close button by invoking the bound handler directly.
    handler_name = mini.protocol("WM_DELETE_WINDOW")
    mini.tk.call(handler_name)
    assert expand_calls == [1]
    mini.destroy()
