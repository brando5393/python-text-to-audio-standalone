"""Makes TalebrewMCP.exe an optional, checkbox-selectable MSI Feature ("Install MCP
Server support"), unchecked by default -- see RELEASING.md's "Installer: optional MCP
Server feature" section for why this needs low-level msilib table authoring instead of
a single high-level cx_Freeze/bdist_msi option (there isn't one).

cx_Freeze's own `bdist_msi.add_files()` (see cx_Freeze/command/bdist_msi.py) already
creates exactly one Feature ("default", Level=1 -- installed by everyone) and puts every
Component -- including one per Executable with no shortcut, via its own
`separate_components` mechanism -- into that single Feature. There is no
`bdist_msi_options` knob to give one Executable its own optional Feature; the components
have to be moved after the fact, and a UI needs adding so a user can actually pick it.

The approach here, in order:

1. Let cx_Freeze's own `add_files()` run exactly as it always does (it's what puts every
   file, including TalebrewMCP.exe and its generated Claude-config JSON, into the
   database as MSI Components in the first place).
2. Re-point just those two Components' `FeatureComponents` rows from "default" to a new
   "MCPServer" Feature, added directly via `msilib.Feature`/`msilib.add_data` -- the same
   pattern `setup.py`'s existing `bdist_msi_options["data"]["Shortcut"]` entry already
   uses for the Start Menu shortcut, just for more tables.
3. Give that Feature a `Level` (1000) above the installer's default `INSTALLLEVEL` (1),
   so it's excluded from a default install, then add a `Condition` table row that drops
   the Level back to 1 -- making it install after all -- only when a property
   (`INSTALLMCP`) is `"1"`.
4. Add one small custom dialog into the install wizard's `InstallUISequence`, between
   cx_Freeze's existing `SelectDirectoryDlg` and `LicenseAgreementDlg`, with a single
   checkbox bound to that `INSTALLMCP` property. This reuses the exact
   `msilib.Dialog`/`Control`/`ControlEvent` machinery cx_Freeze's own `CancelDlg` and
   `WaitForCostingDlg` already use in the same file -- nothing here reaches into a
   disabled/private internal the way the abandoned installer-bitmap idea would have (see
   RELEASING.md's "Installer branding" section for that precedent). Checkbox controls
   default to unchecked (property unset) unless a row pre-sets the property to "1" --
   confirmed directly against cx_Freeze's own "LaunchOnFinish" checkbox in
   `add_exit_dialog()`, which does exactly that to make *its* checkbox checked by
   default. We deliberately don't, so ours starts unchecked.

Real Windows Installer UI-sequence mechanics, not a workaround: an InstallUISequence
Action whose name matches a Dialog table row is a documented built-in "show this dialog"
action, and a dialog's "EndDialog"/"Return" control event is what advances the engine to
the sequence's next action -- exactly how cx_Freeze's own SelectDirectoryDlg -> (next
entry) already works. See MCP_SETUP.md for what installing this feature actually gets a
user, and setup.py for where the two file paths below (`MCP_EXE_BASENAME`,
`MCP_CONFIG_BASENAME`) need to land inside the frozen build tree for this to find them.
"""

from __future__ import annotations

import warnings

with warnings.catch_warnings():
    # msilib is deprecated (slated for removal) upstream, same as cx_Freeze's own
    # bdist_msi.py silences -- this module is only ever imported on Windows, doing the
    # same kind of table authoring cx_Freeze itself does with it.
    warnings.filterwarnings("ignore", "'msilib' is deprecated")
    import msilib

from cx_Freeze.command.bdist_msi import bdist_msi as _CxFreezeBdistMsi

MCP_EXE_BASENAME = "TalebrewMCP.exe"
MCP_CONFIG_BASENAME = "talebrew_mcp_claude_config.json"
MCP_FEATURE_ID = "MCPServer"
# MSI property name conventionally upper-case; this is what the wizard checkbox toggles,
# and what the Condition table row (see _make_mcp_feature_optional) checks for.
MCP_FEATURE_PROPERTY = "INSTALLMCP"
# Above the installer's default INSTALLLEVEL (1) -- excludes the feature from a default
# install unless the Condition table row overrides it back down to 1.
MCP_FEATURE_EXCLUDED_LEVEL = 1000


class BdistMsiWithOptionalMcpFeature(_CxFreezeBdistMsi):
    """cx_Freeze's bdist_msi, plus an optional "MCP Server Support" Feature."""

    def finalize_options(self) -> None:
        super().finalize_options()
        # Give the generated Claude-config JSON (see setup.py) its own Component too, the
        # same way cx_Freeze already does for every Executable -- so it can be moved into
        # the MCP feature alongside TalebrewMCP.exe in _make_mcp_feature_optional below,
        # rather than staying part of the single shared "default" Feature everyone gets.
        self.separate_components[MCP_CONFIG_BASENAME] = msilib.make_id(
            f"_mcp_config_{MCP_CONFIG_BASENAME}"
        )

    def add_files(self) -> None:
        super().add_files()
        self._make_mcp_feature_optional()

    def _make_mcp_feature_optional(self) -> None:
        db = self.db
        mcp_component = self.separate_components.get(MCP_EXE_BASENAME)
        if mcp_component is None:
            # Fail loudly rather than silently ship an installer that dropped the
            # feature this whole module exists to add -- e.g. if TalebrewMCP.exe's
            # Executable() entry ever gets renamed/removed from setup.py without
            # updating MCP_EXE_BASENAME here.
            msg = (
                f"{MCP_EXE_BASENAME} not found among this build's executables -- "
                "can't set up its optional MSI feature."
            )
            raise RuntimeError(msg)
        config_component = self.separate_components.get(MCP_CONFIG_BASENAME)
        components_to_move = [c for c in (mcp_component, config_component) if c]

        # Undo cx_Freeze's own add_files(), which already put both of these Components
        # into its single "default" Feature -- a raw parameterized DELETE via OpenView
        # since msilib has no higher-level "remove this FeatureComponents row" helper.
        view = db.OpenView(
            "DELETE FROM FeatureComponents WHERE Feature_='default' AND Component_=?"
        )
        for component in components_to_move:
            record = msilib.CreateRecord(1)
            record.SetString(1, component)
            view.Execute(record)
        view.Close()

        msilib.Feature(
            db,
            MCP_FEATURE_ID,
            "MCP Server Support",
            "Installs TalebrewMCP.exe, a headless server an AI agent (Claude Desktop, "
            "Claude Code) can use to hand Talebrew files to convert without a human "
            "clicking through the GUI -- see MCP_SETUP.md. Unchecked by default: most "
            "people installing Talebrew just want the desktop app.",
            2,
            level=MCP_FEATURE_EXCLUDED_LEVEL,
            directory="TARGETDIR",
        )
        msilib.add_data(
            db,
            "FeatureComponents",
            [(MCP_FEATURE_ID, component) for component in components_to_move],
        )
        # Drops the Feature's Level back to 1 (<= the default INSTALLLEVEL) -- i.e.
        # actually installs it -- once the wizard checkbox below sets INSTALLMCP="1".
        msilib.add_data(
            db,
            "Condition",
            [(MCP_FEATURE_ID, 1, f'{MCP_FEATURE_PROPERTY}="1"')],
        )

    def add_ui(self) -> None:
        super().add_ui()
        self._add_mcp_feature_dialog()

    def _add_mcp_feature_dialog(self) -> None:
        db = self.db
        dialog = msilib.Dialog(
            db,
            "MCPFeatureDlg",
            self.x,
            self.y,
            self.width,
            self.height,
            self.modal,
            self.title,
            "Next",
            "Next",
            "Cancel",
        )
        dialog.text(
            "Title",
            20,
            15,
            300,
            15,
            0x30003,
            r"{\DlgFontBold8}AI agent integration (optional)",
        )
        dialog.text(
            "Description",
            20,
            35,
            320,
            40,
            3,
            "Talebrew can run a small headless server that lets an AI agent (Claude "
            "Desktop, Claude Code) convert files with Talebrew directly. Most people "
            "installing Talebrew don't need this -- see MCP_SETUP.md for details.",
        )
        dialog.checkbox(
            "InstallMcp",
            20,
            85,
            320,
            18,
            3,
            MCP_FEATURE_PROPERTY,
            "Install MCP Server support (TalebrewMCP.exe)",
            "Next",
        )
        button = dialog.pushbutton("Next", self.width - 145, self.height - 35, 56, 17, 3, "Next >", "Cancel")
        button.event("EndDialog", "Return")
        button = dialog.pushbutton("Cancel", self.width - 85, self.height - 35, 56, 17, 3, "Cancel", None)
        button.event("SpawnDialog", "CancelDlg")

        # Shown right after the user picks an install directory, before the license
        # dialog -- InstallUISequence order 1235 sits between cx_Freeze's own
        # SelectDirectoryDlg (1230) and LicenseAgreementDlg (1240). Same "not Installed"
        # condition as those two: skip it on a repair/uninstall maintenance run.
        msilib.add_data(
            db,
            "InstallUISequence",
            [("MCPFeatureDlg", "not Installed", 1235)],
        )
