import tkinter as tk

from MiniPlayer import MiniPlayer


class FakePlayer:
    def __init__(self):
        self.playing = False
        self.paused_calls = 0
        self.resumed_calls = 0
        self.stopped_calls = 0

    def is_playing(self):
        return self.playing

    def pause(self):
        self.paused_calls += 1
        self.playing = False

    def resume(self):
        self.resumed_calls += 1
        self.playing = True

    def stop(self):
        self.stopped_calls += 1
        self.playing = False


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


def test_closing_window_calls_on_expand(tk_root):
    expand_calls = []
    mini = MiniPlayer(tk_root, FakePlayer(), tk.StringVar(), on_expand=lambda: expand_calls.append(1))
    mini.protocol("WM_DELETE_WINDOW")  # querying the handler shouldn't itself invoke it
    # Simulate the OS close button by invoking the bound handler directly.
    handler_name = mini.protocol("WM_DELETE_WINDOW")
    mini.tk.call(handler_name)
    assert expand_calls == [1]
    mini.destroy()
