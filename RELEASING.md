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

### Installer: optional MCP Server feature

The `.msi` also carries a second, optional Executable, `TalebrewMCP.exe` (built from
`mcp_server.py` -- see `MCP_SETUP.md`), behind an "Install MCP Server support" checkbox
in the wizard, **unchecked by default**: most people installing Talebrew just want the
desktop app, and the checkbox is the one signal that a user actually wants the AI-agent
integration bundled in.

cx_Freeze's `bdist_msi` has no single high-level option for "make this one Executable an
optional, checkbox-selectable install component" -- `bdist_msi.add_files()` always puts
every file into one Feature ("default", installed for everyone). `setup.py` supplies a
custom `bdist_msi` subclass (`msi_mcp_feature.py`, wired in via `cmdclass=`) that, after
cx_Freeze's own `add_files()` runs, does direct `msilib` table work: moves
`TalebrewMCP.exe`'s Component (and its generated Claude-config JSON's) out of "default"
and into a new "MCPServer" Feature, gives that Feature a `Level` above the installer's
default `INSTALLLEVEL` (excluded unless selected), adds a `Condition` table row that
drops the Level back down when a property is set, and adds one small custom dialog into
the wizard (`InstallUISequence`, between cx_Freeze's own `SelectDirectoryDlg` and
`LicenseAgreementDlg`) with a checkbox bound to that property. See
`msi_mcp_feature.py`'s own docstring for the full mechanics and why each piece is needed.
This follows the same "extend cx_Freeze via `bdist_msi_options`/direct table rows, don't
fork it" convention the Start Menu `Shortcut` row (`setup.py`'s `bdist_msi_options["data"]`)
already established -- nothing here patches a disabled internal the way the abandoned
installer-bitmap idea below would have.

**A real, honest limitation this hit**: cx_Freeze's `build_exe_options["packages"]` is a
single build-wide (`Freezer`-level) option, not a per-`Executable` one -- confirmed by
reading `cx_Freeze/executable.py` (`Executable.__init__` takes no packages/includes of
its own) and `cx_Freeze/freezer.py` (`Freezer.packages` is one set shared by the whole
build). So `Talebrew.exe` and `TalebrewMCP.exe` necessarily share one forced-include
package list and one output `lib` folder when built in a single `bdist_msi` invocation --
there's no cx_Freeze knob to force `sounddevice`/`numpy`/`soundfile` into just
`Talebrew.exe`'s dependency closure and leave them out of `TalebrewMCP.exe`'s physical
footprint. What's still true, and was verified directly rather than assumed: `mcp_server.py`
and everything it imports (`Config`/`ConversionsLibrary`/`Converter`/`FileManager`/
`TextExtraction`/`JobStore`) never references `sounddevice`/`numpy`/`soundfile`/
`AudioPlayer`, so `TalebrewMCP.exe` never loads or calls into them at runtime, even though
they're physically present in the shared install directory. A genuinely separate,
smaller-on-disk `TalebrewMCP`-only tree would need two independent `build_exe`/`bdist_msi`
invocations merged together afterward -- a bigger restructuring not undertaken here,
consistent with this project's habit of documenting a real limitation instead of forcing
a fragile workaround.

**Cryptography note**: the `mcp` dependency group's `cryptography` pin is
platform-conditional (see `pyproject.toml`) -- an old, vulnerable-but-only-one-with-wheels
version on ARM64, the current patched one everywhere else. A `.msi` built locally on this
project's ARM64 dev machine therefore bundles the older `cryptography` inside
`TalebrewMCP.exe`'s dependency closure; CI (`windows-latest`, x64) picks up the current
patched version automatically, since it resolves against whatever's installed in *its*
environment. Don't treat a local ARM64 build's bundled `cryptography` version as
representative of what a release actually ships -- check the CI-built artifact if that
ever matters.

This is why GitHub's Dependabot tab on this repo shows open alerts against `cryptography`
(as of 2026-09-18: 7 open, GHSA-jwv3-5hgf-82ww, GHSA-m2h6-j472-rp4c, GHSA-g6cj-pr64-35w5,
GHSA-537c-gmf6-5ccf, GHSA-p423-j2cm-9vmq, GHSA-m959-cc7f-wv43, GHSA-r6ph-v2qm-q3c2) even
though no shipped release is affected -- they're all against the ARM64-only `46.0.3` pin,
not the `>=50.0.1` resolved for x64 in `poetry.lock`, which already carries the fixes for
all of them. Accepted risk, scoped to building/running the optional MCP server locally on
ARM64; re-evaluate if `cryptography` ever ships a newer win_arm64 wheel.

The generated `talebrew_mcp_claude_config.json` (written into the build tree by
`setup.py`'s `_write_generated_mcp_config()`, not committed to source control) bakes in
`C:\Program Files\Talebrew\TalebrewMCP.exe` -- the default `initial_target_dir` -- because
cx_Freeze's minimal installer UI has no custom-action hook to learn the user's *actually
chosen* `TARGETDIR` and write it into a file at install time without a lot more machinery
(a real custom-action script/DLL). A user who installs somewhere else needs to hand-edit
that one path; `MCP_SETUP.md` says so.

### Installer branding

`bdist_msi_options["install_icon"]` (in `setup.py`) puts Talebrew's icon on the
"Apps & features" / "Programs and Features" entry, on top of the icon the Executable
already gets on its Desktop/Start Menu shortcuts -- verified by building the `.msi` and
querying its `Icon`/`Property` tables directly.

Beyond that, the installer's own wizard pages (License, Select Directory, Progress, ...)
stay Windows Installer's plain default look, on purpose: cx_Freeze's minimal MSI UI here
has no image support at all -- its one bitmap hook (`PyDialog.bitmap(...)`) is dead code,
commented out in the library itself. Wiring it up would mean monkey-patching a disabled
internal of a third-party package (fragile across a `cx_Freeze` version bump) for a small
~152px sidebar image. `assets/installer_banner.bmp` and `assets/installer_dialog.bmp`
(generated by `scripts/generate_installer_art.py` from the app's own logo and theme
colors) are kept in the repo as ready-made brand assets, unused by the current installer
-- useful if this ever moves to a toolchain built for this (Inno Setup, WiX) that supports
it without a hack.

## Releasing a new version

1. **Bump the version**: `poetry run python scripts/bump_version.py X.Y.Z` updates both
   `version.py`'s `__version__` and `pyproject.toml`'s `[tool.poetry].version` together,
   so they can't drift apart from a hand-edit only touching one of them.
   `tests/test_version_sync.py` also asserts the two agree, on every push/PR (not just at
   tag time), so a stale value in either file fails the test suite immediately.
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
   installs dependencies (`poetry install --with mcp`, the same `mcp` extras group the
   local build needs -- see "Building and testing the installer locally" below), re-runs
   the full test suite, builds the `.msi` via `poetry run python setup.py bdist_msi`, and
   attaches it to a new GitHub Release (auto-generated release notes from commits since
   the last tag).
7. **Existing installs update themselves**: `AppUpdater.py` polls this repo's latest
   release on startup; anyone running an older version sees an in-app banner offering to
   download and install the new one.

Nothing here is silently automatic beyond that: no telemetry, and the updater only ever
downloads a file after the user clicks "Update Now" in the banner -- see `AppUpdater.py`
and the "Auto-updates" section of `README.md` for exactly what that does and doesn't do.

## Building and testing the installer locally

```
poetry install --with mcp
poetry run python setup.py bdist_msi
```

Building now needs the `mcp` dependency group -- not just `poetry install` -- because
`setup.py` also freezes `TalebrewMCP.exe` from `mcp_server.py` (see "Installer: optional
MCP Server feature" above), and imports `mcp` directly to fail fast with a clear message
if that group isn't installed, rather than a confusing cx_Freeze error partway through
the build.

The `.msi` lands in `dist\Talebrew-<version>-win-arm64.msi` (or `-win-amd64` on an
Intel/AMD machine -- cx_Freeze builds for whatever architecture it runs on, it does not
cross-compile). To verify it before tagging:

1. **Smoke-test both frozen exes directly**, without installing anything:
   `build\exe.<platform>\Talebrew.exe` should launch and show the normal window, and
   `build\exe.<platform>\TalebrewMCP.exe` should start and sit waiting for stdio input
   with no window (an MCP client, not a human, talks to it -- see MCP_SETUP.md's
   troubleshooting section for what "working" looks like from a terminal). This is the
   fastest way to catch a packaging problem (a missing data file, a bad icon path)
   without going through a full install/uninstall cycle.
2. **Run the actual installer**: double-click the `.msi` in `dist\`. Confirm it adds
   both a Desktop and a Start Menu shortcut, and that the app launches correctly from
   each. Leave "Install MCP Server support" unchecked once and confirm `TalebrewMCP.exe`
   is *not* present afterward; run it again with the box checked and confirm it *is*
   present, alongside a `talebrew_mcp_claude_config.json` with the real install path
   filled in.
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
