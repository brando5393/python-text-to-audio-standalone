# Releasing Talebrew

This document describes how a new version of Talebrew is packaged and published.

## Toolchain

- **Freezing**: [cx_Freeze](https://cx-freeze.readthedocs.io/) (`setup.py`), already a dev
  dependency. It bundles the app, its CPython interpreter, and `assets/` into a
  self-contained `build/exe.<platform>/` directory -- no separate Python install needed
  on the target machine.
- **Installer**: cx_Freeze's own `bdist_msi` command, which produces a real Windows
  Installer (`.msi`) package -- the same underlying format WiX produces, just without a
  second toolchain to maintain. It registers Talebrew in "Apps & features" (so Windows'
  own uninstaller works with no extra scripting), carries version info, and adds both a
  Desktop and a Start Menu shortcut (see `setup.py`'s `bdist_msi_options["data"]`).

### Why not PyInstaller + Inno Setup

Those are reasonable defaults for a from-scratch Tkinter app, and were seriously
considered (PyInstaller has the broadest hook coverage for GUI toolkits; Inno Setup is
the lightest-weight scripted installer). They weren't adopted here because Talebrew
already had a **working, tested** cx_Freeze/MSI pipeline before this round of work
(`setup.py`, verified end-to-end below) and a **live integration that specifically
depends on `.msi`**: `AppUpdater.py` looks for a `.msi` asset on each GitHub Release,
verifies it against the SHA-256 digest GitHub computes for that asset, and launches it
with `msiexec /passive`. Switching to a PyInstaller `.exe` behind an Inno Setup wrapper
would mean rewriting and re-testing that updater (and its existing unit tests in
`tests/test_app_updater.py`) for no real gain -- cx_Freeze's `bdist_msi` already produces
a native MSI with an uninstaller, Start Menu entry, and upgrade codes, which is the same
end result WiX would give, with one less tool in the chain.

If a future need arises that cx_Freeze can't meet (e.g. needing a single-file `.exe`,
or needing Nuitka's compiled-code IP protection), that's a deliberate follow-up, not a
default to reach for without a concrete reason.

### What's NOT bundled

The Piper TTS engine and voice models are downloaded on demand from Settings (see
`PiperEngine.py`), not bundled into the installer -- that keeps the `.msi` small.
`pyttsx3`/SAPI (the system voice) works immediately with no extra download.

## Releasing a new version

1. **Bump the version.** Edit `version.py`'s `__version__` and `pyproject.toml`'s
   `[tool.poetry].version` to match (both need updating; nothing currently automates
   keeping them in sync -- consider that a good follow-up).
2. **Run the test suite locally**: `poetry run pytest tests/ -q`. All tests must pass
   before tagging.
3. **Build and smoke-test the installer locally** (see below) before pushing the tag --
   CI will build it again, but catching a packaging problem before it's public is
   cheaper than catching it after.
4. **Commit** the version bump.
5. **Tag and push**: `git tag vX.Y.Z && git push origin vX.Y.Z`. The tag must start with
   `v` and match `__version__` exactly (e.g. `v0.2.0` for `__version__ = "0.2.0"`) --
   `.github/workflows/release.yml` checks this and fails the build if they disagree.
6. **CI takes over** (`.github/workflows/release.yml`, triggered by the tag push): it
   installs dependencies, re-runs the full test suite, builds the `.msi` via
   `poetry run python setup.py bdist_msi`, and attaches it to a new GitHub Release
   (auto-generated release notes from commits since the last tag).
7. **Existing installs update themselves**: `AppUpdater.py` polls this repo's latest
   release on startup; anyone running an older version sees an in-app banner offering to
   download and install the new one.

Nothing here is silently automatic beyond that: no telemetry, and the updater only ever
downloads a file after the user clicks "Update Now" in the banner -- see `AppUpdater.py`
and the "Auto-updates" section of `README.md` for exactly what that does and doesn't do.

## Building and testing the installer locally

```
poetry install
poetry run python setup.py bdist_msi
```

The `.msi` lands in `dist\Talebrew-<version>-win-arm64.msi` (or `-win-amd64` on an
Intel/AMD machine -- cx_Freeze builds for whatever architecture it runs on, it does not
cross-compile). To verify it before tagging:

1. **Smoke-test the frozen exe directly**, without installing anything:
   `build\exe.<platform>\Talebrew.exe` should launch and show the normal window --
   this is the fastest way to catch a packaging problem (a missing data file, a bad
   icon path) without going through a full install/uninstall cycle.
2. **Run the actual installer**: double-click the `.msi` in `dist\`. Confirm it adds
   both a Desktop and a Start Menu shortcut, and that the app launches correctly from
   each.
3. **Uninstall** via "Apps & features" (search the Start Menu for "Talebrew" or open
   `appwiz.cpl`) and confirm it's removed cleanly.

CI runs on `windows-latest` (x64), so it produces an x64 `.msi`; a maintainer building
and testing locally on Windows-on-ARM64 (as this project has been developed on) will get
an arm64 `.msi` instead -- both are valid release assets for their respective machines,
but only whichever architecture the CI runner is on gets attached to the GitHub Release
automatically. If both architectures need distributing, run the build locally on the
other and upload it to the release by hand (`gh release upload vX.Y.Z path\to\file.msi`).

## What CI does *not* do

- It does not sign the installer -- Talebrew ships unsigned. `AppUpdater.py`'s
  SHA-256 check against GitHub's own asset digest guards against a corrupted or
  tampered-with *download*, not against a compromised release process; it is not a
  substitute for code signing.
- It does not publish to any store (Microsoft Store, winget, Chocolatey, etc.) --
  a GitHub Release is the only distribution channel today.
- It never executes anything it downloads. `AppUpdater.py` only ever checks a version
  number and a download URL automatically; the actual download and install only happen
  after the user clicks "Update Now" in the in-app banner.
