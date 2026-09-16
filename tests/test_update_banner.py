import time
import tkinter as tk

from packaging.version import Version

import AppUpdater
from UpdateBanner import UpdateBanner


def _fake_update(version="9.9.9"):
    return AppUpdater.AvailableUpdate(
        version=Version(version),
        msi_download_url="https://example.com/fake.msi",
        release_page_url="https://example.com",
        expected_sha256=None,
    )


def _wait_until(predicate, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_banner_is_hidden_until_an_update_is_found(tk_root):
    # tk_root is withdrawn (see conftest.py), so winfo_ismapped() would be False regardless
    # of placement -- Tk's mapping state requires the ancestor window to be viewable too.
    # winfo_manager() reflects geometry-manager registration instead, independent of that.
    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    banner = UpdateBanner(tk_root, LogManager(log_list), on_before_install_quit=lambda: None)
    assert banner.winfo_manager() == ""
    banner.destroy()


def test_banner_shows_when_update_found(tk_root):
    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    banner = UpdateBanner(tk_root, LogManager(log_list), on_before_install_quit=lambda: None)

    banner._events.put(("found", _fake_update()))
    assert _wait_until(lambda: (tk_root.update(), banner.winfo_manager() == "place")[1])

    assert banner.winfo_manager() == "place"
    assert "9.9.9" in banner.message_var.get()
    banner.destroy()


def test_hide_unmaps_the_banner(tk_root):
    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    banner = UpdateBanner(tk_root, LogManager(log_list), on_before_install_quit=lambda: None)
    banner.show()
    tk_root.update()
    assert banner.winfo_manager() == "place"
    banner.hide()
    tk_root.update()
    assert banner.winfo_manager() == ""
    banner.destroy()


def test_update_now_downloads_launches_and_quits(tk_root, monkeypatch):
    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    quit_calls = []
    banner = UpdateBanner(tk_root, LogManager(log_list), on_before_install_quit=lambda: quit_calls.append(1))

    launched = []
    monkeypatch.setattr(AppUpdater, "download_installer", lambda update: "/fake/path/to.msi")
    monkeypatch.setattr(AppUpdater, "launch_installer", lambda path: launched.append(path))

    banner.update = _fake_update()
    banner._start_update()

    deadline = time.time() + 5
    while time.time() < deadline and not quit_calls:
        tk_root.update()
        time.sleep(0.02)

    assert launched == ["/fake/path/to.msi"]
    assert quit_calls == [1]
    banner.destroy()


def test_update_now_handles_download_failure_gracefully(tk_root, monkeypatch):
    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    banner = UpdateBanner(tk_root, LogManager(log_list), on_before_install_quit=lambda: None)

    def fail(update):
        raise RuntimeError("network is down")

    monkeypatch.setattr(AppUpdater, "download_installer", fail)
    banner.update = _fake_update()
    banner._start_update()

    # cget("state") returns a _tkinter.Tcl_Obj, not a plain str -- it reprs as e.g.
    # "disabled" but doesn't `==` the Python string directly, so the loop condition
    # below (and the final assertion) both go through str() explicitly.
    deadline = time.time() + 5
    while time.time() < deadline and str(banner.update_btn.cget("state")) == "disabled":
        tk_root.update()
        time.sleep(0.02)

    assert str(banner.update_btn.cget("state")) == "normal"  # re-enabled after the failure
    banner.destroy()
