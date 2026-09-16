import json

import pytest

import AppUpdater


def sample_release(tag, asset_name, digest=None):
    asset = {"name": asset_name, "browser_download_url": f"https://example.com/{asset_name}"}
    if digest is not None:
        asset["digest"] = digest
    return json.dumps({
        "tag_name": tag,
        "html_url": f"https://github.com/brando5393/python-text-to-audio-standalone/releases/tag/{tag}",
        "assets": [asset],
    })


def test_newer_version_is_detected():
    body = sample_release("v0.2.0", "Talebrew.msi")
    update = AppUpdater.parse_update("0.1.0", body)
    assert update is not None
    assert str(update.version) == "0.2.0"
    assert update.msi_download_url == "https://example.com/Talebrew.msi"


def test_same_version_is_not_an_update():
    body = sample_release("v0.1.0", "Talebrew.msi")
    assert AppUpdater.parse_update("0.1.0", body) is None


def test_older_version_is_not_an_update():
    body = sample_release("v0.9.0", "Talebrew.msi")
    assert AppUpdater.parse_update("1.0.0", body) is None


def test_missing_msi_asset_yields_no_update():
    body = sample_release("v0.2.0", "Talebrew.tar.gz")
    assert AppUpdater.parse_update("0.1.0", body) is None


def test_malformed_json_yields_no_update_not_an_exception():
    assert AppUpdater.parse_update("0.1.0", "not json") is None


def test_tag_without_v_prefix_still_parses():
    body = sample_release("0.2.0", "Talebrew.msi")
    assert AppUpdater.parse_update("0.1.0", body) is not None


def test_digest_is_extracted_with_sha256_prefix_stripped():
    body = sample_release("v0.2.0", "Talebrew.msi", digest="sha256:abc123")
    update = AppUpdater.parse_update("0.1.0", body)
    assert update.expected_sha256 == "abc123"


def test_missing_digest_yields_none_not_an_error():
    body = sample_release("v0.2.0", "Talebrew.msi")
    update = AppUpdater.parse_update("0.1.0", body)
    assert update.expected_sha256 is None


def test_verify_checksum_passes_when_no_expected_digest():
    AppUpdater.verify_checksum(b"anything", None)  # should not raise


def test_verify_checksum_passes_on_a_match():
    import hashlib
    digest = hashlib.sha256(b"hello").hexdigest()
    AppUpdater.verify_checksum(b"hello", digest)  # should not raise


def test_verify_checksum_fails_on_a_mismatch():
    with pytest.raises(ValueError, match="doesn't match"):
        AppUpdater.verify_checksum(b"tampered bytes", "0" * 16)
