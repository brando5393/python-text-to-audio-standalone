"""Checks GitHub Releases for a newer version of Talebrew, and can fetch + launch the
new installer. This exists so updates reach installed copies without needing a
background service, a paid update host, or anything beyond GitHub's free Releases
hosting. It is NOT a fully silent updater: the .msi still touches Program Files, so
Windows still shows one UAC prompt, same as the original install -- pretending
otherwise would be dishonest about what's actually possible here.

The network calls (check_for_update, download_installer) aren't unit-tested -- that
would be a flaky, slow test hitting a real external API on every run. The parsing and
version-comparison logic that actually decides "is this newer" is pure and is tested
against sample GitHub API responses (see tests/test_app_updater.py).
"""

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Optional

from packaging.version import InvalidVersion, Version

from version import __version__

REPO = "brando5393/python-text-to-audio-standalone"
USER_AGENT = "Talebrew-AppUpdater"
REQUEST_TIMEOUT_SECONDS = 5
DOWNLOAD_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class AvailableUpdate:
    version: Version
    msi_download_url: str
    release_page_url: str
    # GitHub computes and serves a SHA-256 digest for every release asset itself.
    # None only if GitHub's response is ever missing it, in which case
    # download_installer skips verification rather than failing every update.
    expected_sha256: Optional[str]


def parse_update(current: str, body: str) -> Optional[AvailableUpdate]:
    """Parses a GitHub "latest release" API response and returns an update iff its
    version is strictly newer than `current` and it has a .msi asset. Pure and
    unit-tested -- check_for_update is a thin, untested wrapper that just fetches
    this body over HTTP."""
    try:
        release = json.loads(body)
    except json.JSONDecodeError:
        return None

    tag = release.get("tag_name", "")
    tag = tag[1:] if tag.startswith("v") else tag
    try:
        remote_version = Version(tag)
        current_version = Version(current)
    except InvalidVersion:
        return None

    if remote_version <= current_version:
        return None

    msi_asset = next((a for a in release.get("assets", []) if a.get("name", "").endswith(".msi")), None)
    if msi_asset is None:
        return None

    digest = msi_asset.get("digest")
    expected_sha256 = digest[len("sha256:"):] if digest and digest.startswith("sha256:") else None

    return AvailableUpdate(
        version=remote_version,
        msi_download_url=msi_asset["browser_download_url"],
        release_page_url=release.get("html_url", ""),
        expected_sha256=expected_sha256,
    )


def check_for_update(current: str = __version__) -> Optional[AvailableUpdate]:
    """Checks GitHub for a newer release. Never raises; any network/parse failure
    (offline, GitHub down, rate-limited, no releases published yet) just yields None
    -- a background version check failing silently is correct behavior here, not
    something that should ever interrupt using the app."""
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except Exception:
        return None
    return parse_update(current, body)


def verify_checksum(data: bytes, expected: Optional[str]) -> None:
    """Pure (no I/O) so it's directly unit-testable. expected=None (GitHub's response
    was ever missing a digest) passes through without checking anything. Raises
    ValueError on a mismatch."""
    if expected is None:
        return
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(
            f"downloaded installer's checksum doesn't match GitHub's ({actual} != {expected}) "
            "-- refusing to install it"
        )


def download_installer(update: AvailableUpdate) -> str:
    """Downloads the update's installer to a temp file, verifies it against
    expected_sha256 (GitHub's own digest for that asset) when available, and returns
    its path. This isn't a substitute for code signing -- it can't prove the release
    itself is legitimate, only that the bytes on disk are exactly the bytes GitHub
    says it served. It does catch a corrupted download or tampering in transit/at
    rest, for free, using a value already fetched. A mismatch deletes the file and
    raises rather than launching an installer that doesn't match what was promised."""
    path = os.path.join(tempfile.gettempdir(), f"talebrew_update_{update.version}.msi")
    request = urllib.request.Request(update.msi_download_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        data = response.read()

    try:
        verify_checksum(data, update.expected_sha256)
    except ValueError:
        raise

    with open(path, "wb") as f:
        f.write(data)
    return path


def launch_installer(path: str) -> subprocess.Popen:
    """Launches the downloaded installer in "passive" mode (progress UI only, no
    wizard click-through, since the user already went through that on first
    install) -- still shows the one UAC prompt Windows requires for anything
    touching Program Files; that can't be skipped."""
    return subprocess.Popen(["msiexec", "/i", path, "/passive", "/norestart"])
