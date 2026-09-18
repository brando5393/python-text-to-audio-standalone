"""Bumps the app's version everywhere it needs to match in one command, instead of
hand-editing version.py and pyproject.toml separately and risking them drifting -- see
RELEASING.md's "Releasing a new version" step 1, and tests/test_version_sync.py, which
fails the whole test suite (so on every push/PR, not just at tag time) if they ever do.

Run: `poetry run python scripts/bump_version.py X.Y.Z`
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = ROOT / "version.py"
PYPROJECT = ROOT / "pyproject.toml"

_VERSION_ARG_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _replace_one(path, pattern, replacement, description):
    text = path.read_text(encoding="utf-8")
    new_text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit(f"Could not find {description} in {path}")
    path.write_text(new_text, encoding="utf-8")


def main():
    if len(sys.argv) != 2 or not _VERSION_ARG_RE.match(sys.argv[1]):
        raise SystemExit("Usage: poetry run python scripts/bump_version.py X.Y.Z")
    new_version = sys.argv[1]

    _replace_one(
        VERSION_PY,
        re.compile(r'__version__ = "[^"]+"'),
        f'__version__ = "{new_version}"',
        "__version__",
    )
    _replace_one(
        PYPROJECT,
        re.compile(r'(?m)^version = "[^"]+"'),
        f'version = "{new_version}"',
        "[tool.poetry] version",
    )
    print(f"Bumped version.py and pyproject.toml to {new_version}.")


if __name__ == "__main__":
    main()
