"""Guards against version.py and pyproject.toml drifting apart -- nothing at runtime
reads pyproject.toml's [tool.poetry] version (package-mode is off; version.py is what
setup.py and AppUpdater.py actually use), so a stale value there would go unnoticed by
every other test. This runs on every push/PR (see .github/workflows/tests.yml), not just
at release/tag time, so drift is caught immediately rather than surfacing only when
someone happens to read pyproject.toml. See scripts/bump_version.py for the one-command
way to update both together."""

import tomllib
from pathlib import Path

from version import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_version_matches_version_py():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["poetry"]["version"] == __version__
