"""Tests for template lockfile — SHA256 hash tracking and drift detection."""

from __future__ import annotations

from pathlib import Path

from n3rverberage.init.lockfile import (
    LOCKFILE_NAME,
    LOCKFILE_VERSION,
    _sha256,
    check_drift,
    diff_lockfile,
    load_lockfile,
    lockfile_path,
    record_entry,
    save_lockfile,
    update_lockfile_entry,
)

# ---------------------------------------------------------------------------
# _sha256
# ---------------------------------------------------------------------------


def test_sha256_deterministic(tmp_path: Path):
    """Same content produces same hash."""
    f = tmp_path / "a.txt"
    f.write_text("hello")
    assert _sha256(f) == _sha256(f)


def test_sha256_differs_for_diff_content(tmp_path: Path):
    """Different content produces different hash."""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("hello")
    b.write_text("world")
    assert _sha256(a) != _sha256(b)


def test_sha256_is_hex_string(tmp_path: Path):
    """Hash is a 64-char hex string (SHA256)."""
    f = tmp_path / "a.txt"
    f.write_text("data")
    h = _sha256(f)
    assert len(h) == 64
    int(h, 16)  # does not raise


# ---------------------------------------------------------------------------
# lockfile_path
# ---------------------------------------------------------------------------


def test_lockfile_path(tmp_path: Path):
    """lockfile_path returns path under .n3rverberage/."""
    assert lockfile_path(tmp_path) == tmp_path / ".n3rverberage" / LOCKFILE_NAME


# ---------------------------------------------------------------------------
# load_lockfile
# ---------------------------------------------------------------------------


def test_load_missing_lockfile(tmp_path: Path):
    """Missing lockfile returns empty dict."""
    assert load_lockfile(tmp_path) == {}


def test_load_corrupt_lockfile(tmp_path: Path):
    """Corrupt JSON lockfile returns empty dict."""
    lp = lockfile_path(tmp_path)
    lp.parent.mkdir(parents=True)
    lp.write_text("{broken")
    assert load_lockfile(tmp_path) == {}


def test_load_not_a_dict_lockfile(tmp_path: Path):
    """Lockfile that is not a dict returns empty dict."""
    lp = lockfile_path(tmp_path)
    lp.parent.mkdir(parents=True)
    lp.write_text('"string"')
    assert load_lockfile(tmp_path) == {}


# ---------------------------------------------------------------------------
# save_lockfile + load_lockfile round-trip
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path: Path):
    """Saved lockfile can be loaded and contains expected structure."""
    entries = {"some/file.txt": {"sha256": "abc123", "template": "tpl.j2"}}
    save_lockfile(tmp_path, entries)

    loaded = load_lockfile(tmp_path)
    assert loaded["lockfile_version"] == LOCKFILE_VERSION
    assert loaded["entries"] == entries


def test_save_creates_directory(tmp_path: Path):
    """save_lockfile creates .n3rverberage/ directory if missing."""
    save_lockfile(tmp_path, {})
    assert lockfile_path(tmp_path).is_file()


# ---------------------------------------------------------------------------
# record_entry
# ---------------------------------------------------------------------------


def test_record_entry_contains_expected_keys(tmp_path: Path):
    """record_entry returns a dict with sha256, template, context_hash, updated_at."""
    f = tmp_path / "out.txt"
    f.write_text("content")
    entry = record_entry(f, "tpl.j2", context_hash="ctx123")

    assert "sha256" in entry
    assert "template" in entry
    assert "context_hash" in entry
    assert "updated_at" in entry
    assert entry["sha256"] == _sha256(f)
    assert entry["template"] == "tpl.j2"
    assert entry["context_hash"] == "ctx123"


# ---------------------------------------------------------------------------
# check_drift
# ---------------------------------------------------------------------------


def test_check_drift_not_tracked(tmp_path: Path):
    """File not in lockfile reports 'not tracked'."""
    reason = check_drift(tmp_path, "some/file.txt", "abc")
    assert reason == "not tracked"


def test_check_drift_match(tmp_path: Path):
    """Hash matches lockfile returns None."""
    f = tmp_path / "out.txt"
    f.write_text("stable")
    h = _sha256(f)

    save_lockfile(tmp_path, {"out.txt": {"sha256": h, "template": "tpl.j2"}})
    assert check_drift(tmp_path, "out.txt", h) is None


def test_check_drift_mismatch(tmp_path: Path):
    """Hash differs from lockfile reports mismatch."""
    f = tmp_path / "out.txt"
    f.write_text("original")
    h = _sha256(f)

    save_lockfile(tmp_path, {"out.txt": {"sha256": h, "template": "tpl.j2"}})

    # Modify file
    f.write_text("modified")
    new_h = _sha256(f)

    reason = check_drift(tmp_path, "out.txt", new_h)
    assert reason is not None
    assert "mismatch" in reason


def test_check_drift_no_hash_stored(tmp_path: Path):
    """Entry exists but has no sha256 value."""
    save_lockfile(tmp_path, {"out.txt": {"template": "tpl.j2"}})
    reason = check_drift(tmp_path, "out.txt", "abc")
    assert reason == "no hash stored"


# ---------------------------------------------------------------------------
# update_lockfile_entry
# ---------------------------------------------------------------------------


def test_update_lockfile_entry_add(tmp_path: Path):
    """Add a new entry and verify it persists."""
    f = tmp_path / "out.txt"
    f.write_text("data")
    entry = record_entry(f, "tpl.j2")

    update_lockfile_entry(tmp_path, "rel/out.txt", entry)

    loaded = load_lockfile(tmp_path)
    assert loaded["entries"]["rel/out.txt"]["sha256"] == entry["sha256"]


def test_update_lockfile_entry_overwrite(tmp_path: Path):
    """Update an existing entry."""
    f = tmp_path / "out.txt"
    f.write_text("data")
    entry1 = record_entry(f, "old.j2")

    update_lockfile_entry(tmp_path, "out.txt", entry1)

    f.write_text("new data")
    entry2 = record_entry(f, "new.j2")
    update_lockfile_entry(tmp_path, "out.txt", entry2)

    loaded = load_lockfile(tmp_path)
    assert loaded["entries"]["out.txt"]["sha256"] == entry2["sha256"]
    assert loaded["entries"]["out.txt"]["template"] == "new.j2"


# ---------------------------------------------------------------------------
# diff_lockfile
# ---------------------------------------------------------------------------


def test_diff_lockfile_empty_when_match(tmp_path: Path):
    """All rendered files match lockfile, so drift is empty."""
    f = tmp_path / "out.txt"
    f.write_text("stable")
    h = _sha256(f)
    save_lockfile(tmp_path, {"out.txt": {"sha256": h, "template": "tpl.j2"}})

    drift = diff_lockfile(tmp_path, {"out.txt": f})
    assert drift == {}


def test_diff_lockfile_file_missing(tmp_path: Path):
    """Rendered file is listed but missing from disk."""
    save_lockfile(tmp_path, {"out.txt": {"sha256": "x", "template": "tpl.j2"}})
    missing = tmp_path / "out.txt"

    drift = diff_lockfile(tmp_path, {"out.txt": missing})
    assert "out.txt" in drift
    assert "missing" in drift["out.txt"]


def test_diff_lockfile_drift_reported(tmp_path: Path):
    """Modified file is reported as drift."""
    f = tmp_path / "out.txt"
    f.write_text("original")
    h = _sha256(f)
    save_lockfile(tmp_path, {"out.txt": {"sha256": h, "template": "tpl.j2"}})

    f.write_text("modified")

    drift = diff_lockfile(tmp_path, {"out.txt": f})
    assert "out.txt" in drift


def test_diff_lockfile_not_in_manifest(tmp_path: Path):
    """Entry in lockfile but not in rendered manifest is reported."""
    save_lockfile(tmp_path, {"stale.txt": {"sha256": "x", "template": "old.j2"}})
    drift = diff_lockfile(tmp_path, {})
    assert "stale.txt" in drift
    assert "manifest" in drift["stale.txt"]


def test_diff_lockfile_mixed(tmp_path: Path):
    """Multiple drift states reported simultaneously."""
    f_good = tmp_path / "good.txt"
    f_good.write_text("match")
    h = _sha256(f_good)

    f_bad = tmp_path / "bad.txt"
    f_bad.write_text("original")
    bad_h = _sha256(f_bad)

    save_lockfile(
        tmp_path,
        {
            "good.txt": {"sha256": h, "template": "good.j2"},
            "bad.txt": {"sha256": bad_h, "template": "bad.j2"},
            "stale.txt": {"sha256": "x", "template": "old.j2"},
        },
    )

    f_bad.write_text("modified")

    drift = diff_lockfile(tmp_path, {"good.txt": f_good, "bad.txt": f_bad})
    assert "good.txt" not in drift  # no drift
    assert "bad.txt" in drift  # mismatched
    assert "stale.txt" in drift  # not in manifest


# ---------------------------------------------------------------------------
# Integration: save → diff → update → diff
# ---------------------------------------------------------------------------


def test_lockfile_lifecycle(tmp_path: Path):
    """End-to-end: save, verify no drift, modify, verify drift, update, no drift."""
    f = tmp_path / "app.py"
    f.write_text("print('hello')")
    h1 = _sha256(f)

    # Save initial
    save_lockfile(tmp_path, {"app.py": {"sha256": h1, "template": "app.py.j2"}})
    assert diff_lockfile(tmp_path, {"app.py": f}) == {}

    # Modify file → drift detected
    f.write_text("print('goodbye')")
    drift = diff_lockfile(tmp_path, {"app.py": f})
    assert "app.py" in drift

    # Record new hash → no drift
    update_lockfile_entry(tmp_path, "app.py", record_entry(f, "app.py.j2"))
    assert diff_lockfile(tmp_path, {"app.py": f}) == {}
