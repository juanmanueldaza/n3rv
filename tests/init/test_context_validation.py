"""Tests for context schema validation and schema loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from n3rverberage.init.renderer import (
    ContextValidationError,
    TemplateEngine,
    _load_schema,
    validate_context,
)

# ---------------------------------------------------------------------------
# _load_schema
# ---------------------------------------------------------------------------


def test_load_schema_missing_file(tmp_path: Path):
    """Missing context.json returns empty dict."""
    assert _load_schema(tmp_path) == {}


def test_load_schema_invalid_json(tmp_path: Path):
    """Malformed context.json returns empty dict gracefully."""
    (tmp_path / "context.json").write_text("not json{{{")
    assert _load_schema(tmp_path) == {}


def test_load_schema_not_a_dict(tmp_path: Path):
    """context.json containing a list returns empty dict."""
    (tmp_path / "context.json").write_text('["a", "b"]')
    assert _load_schema(tmp_path) == {}


def test_load_schema_no_variables_key(tmp_path: Path):
    """context.json without 'variables' key returns empty dict."""
    (tmp_path / "context.json").write_text(json.dumps({"version": "1.0"}))
    assert _load_schema(tmp_path) == {}


def test_load_schema_valid(tmp_path: Path):
    """Valid context.json returns the variables dict."""
    schema = {"variables": {"name": {"type": "string", "required": True}}}
    (tmp_path / "context.json").write_text(json.dumps(schema))
    assert _load_schema(tmp_path) == schema["variables"]


# ---------------------------------------------------------------------------
# validate_context — required
# ---------------------------------------------------------------------------


def test_validate_required_var_present():
    """Required variable present does not error."""
    validate_context({"name": "foo"}, {"name": {"required": True, "type": "string"}})


def test_validate_required_var_missing():
    """Missing required variable raises ContextValidationError."""
    with pytest.raises(ContextValidationError) as exc:
        validate_context({}, {"name": {"required": True, "type": "string"}})
    assert "name" in str(exc.value)


def test_validate_required_var_missing_reports_all():
    """All missing required vars are reported together."""
    schema = {
        "a": {"required": True},
        "b": {"required": True},
        "c": {"required": False},
    }
    with pytest.raises(ContextValidationError) as exc:
        validate_context({}, schema)
    msg = str(exc.value)
    assert "a" in msg
    assert "b" in msg


# ---------------------------------------------------------------------------
# validate_context — types
# ---------------------------------------------------------------------------


def test_validate_type_string():
    """String type accepts str."""
    validate_context({"x": "hello"}, {"x": {"type": "string"}})


def test_validate_type_boolean():
    """Boolean type accepts bool."""
    validate_context({"x": True}, {"x": {"type": "boolean"}})


def test_validate_type_integer():
    """Integer type accepts int."""
    validate_context({"x": 42}, {"x": {"type": "integer"}})


def test_validate_type_number():
    """Number type accepts float."""
    validate_context({"x": 3.14}, {"x": {"type": "number"}})


def test_validate_type_number_also_int():
    """Number type also accepts int."""
    with pytest.raises(ContextValidationError):
        validate_context({"x": 42}, {"x": {"type": "number"}})


def test_validate_type_array():
    """Array type accepts list."""
    validate_context({"x": [1, 2]}, {"x": {"type": "array"}})


def test_validate_type_object():
    """Object type accepts dict."""
    validate_context({"x": {"k": "v"}}, {"x": {"type": "object"}})


def test_validate_wrong_type():
    """Wrong type raises ContextValidationError."""
    with pytest.raises(ContextValidationError) as exc:
        validate_context({"x": 42}, {"x": {"type": "string"}})
    assert "x" in str(exc.value)


# ---------------------------------------------------------------------------
# validate_context — enums
# ---------------------------------------------------------------------------


def test_validate_enum_valid():
    """Value in enum passes."""
    validate_context({"x": "a"}, {"x": {"enum": ["a", "b", "c"]}})


def test_validate_enum_invalid():
    """Value not in enum raises ContextValidationError."""
    with pytest.raises(ContextValidationError) as exc:
        validate_context({"x": "z"}, {"x": {"enum": ["a", "b", "c"]}})
    assert "z" in str(exc.value)


def test_validate_enum_with_type():
    """Enum and type check work together."""
    with pytest.raises(ContextValidationError) as exc:
        validate_context({"x": 42}, {"x": {"type": "string", "enum": ["a", "b"]}})
    assert "x" in str(exc.value)


# ---------------------------------------------------------------------------
# validate_context — defaults
# ---------------------------------------------------------------------------


def test_validate_default_applied_when_missing():
    """Default value is injected when variable is absent and not required."""
    ctx = {}
    validate_context(ctx, {"x": {"type": "string", "default": "default_val"}})
    assert ctx["x"] == "default_val"


def test_validate_default_does_not_override():
    """Default is NOT applied when variable is already present."""
    ctx = {"x": "explicit"}
    validate_context(ctx, {"x": {"type": "string", "default": "default_val"}})
    assert ctx["x"] == "explicit"


def test_validate_default_none_is_noop():
    """Default of None does nothing."""
    ctx = {}
    validate_context(ctx, {"x": {"type": "string", "default": None}})
    assert "x" not in ctx


# ---------------------------------------------------------------------------
# validate_context — unknown vars
# ---------------------------------------------------------------------------


def test_validate_unknown_vars_ignored():
    """Unknown variables do not cause validation errors."""
    validate_context({"unknown_key": "whatever"}, {"known": {"type": "string"}})


# ---------------------------------------------------------------------------
# validate_context — no schema (empty dict)
# ---------------------------------------------------------------------------


def test_validate_empty_schema_passes_anything():
    """Empty schema means no validation — everything passes."""
    validate_context({"anything": "goes", "nums": [1, 2]}, {})


# ---------------------------------------------------------------------------
# TemplateEngine.validate — mutation safety
# ---------------------------------------------------------------------------


def test_validate_does_not_mutate_original(tmp_path: Path):
    """TemplateEngine.validate returns a new dict without modifying the original."""
    engine = TemplateEngine(tmp_path)
    original = {"name": "test"}
    result = engine.validate(original)
    assert result == original
    assert result is not original


# ---------------------------------------------------------------------------
# TemplateEngine.render — schema integration
# ---------------------------------------------------------------------------


def test_engine_render_validates_context(tmp_path: Path):
    """TemplateEngine.render runs context validation."""
    schema = {"variables": {"name": {"type": "string", "required": True}}}
    (tmp_path / "context.json").write_text(json.dumps(schema))
    (tmp_path / "greet.txt.j2").write_text("Hi {{ name }}!")

    engine = TemplateEngine(tmp_path)
    result = engine.render("greet.txt.j2", {"name": "Alice"})
    assert result == "Hi Alice!"


def test_engine_render_validation_error(tmp_path: Path):
    """TemplateEngine.render raises ContextValidationError for invalid context."""
    schema = {"variables": {"name": {"type": "string", "required": True}}}
    (tmp_path / "context.json").write_text(json.dumps(schema))
    (tmp_path / "greet.txt.j2").write_text("Hi {{ name }}!")

    engine = TemplateEngine(tmp_path)
    with pytest.raises(ContextValidationError):
        engine.render("greet.txt.j2", {})


def test_engine_render_applies_defaults(tmp_path: Path):
    """TemplateEngine.render applies defaults from schema."""
    schema = {
        "variables": {
            "name": {"type": "string", "required": True},
            "greeting": {"type": "string", "default": "Hello"},
        }
    }
    (tmp_path / "context.json").write_text(json.dumps(schema))
    (tmp_path / "greet.txt.j2").write_text("{{ greeting }} {{ name }}!")

    engine = TemplateEngine(tmp_path)
    result = engine.render("greet.txt.j2", {"name": "World"})
    assert result == "Hello World!"


# ---------------------------------------------------------------------------
# TemplateEngine — user_overrides_dir (override integration)
# ---------------------------------------------------------------------------


def test_engine_user_overrides_shadow_bundled(tmp_path: Path):
    """user_overrides_dir templates take priority over bundled."""
    (tmp_path / "greet.txt.j2").write_text("BUNDLED: {{ name }}")
    overrides = tmp_path / "overrides"
    overrides.mkdir()
    (overrides / "greet.txt.j2").write_text("OVERRIDE: {{ name }}")

    engine = TemplateEngine(tmp_path, user_overrides_dir=overrides)
    result = engine.render("greet.txt.j2", {"name": "test"})
    assert result == "OVERRIDE: test"


def test_engine_user_overrides_fall_through(tmp_path: Path):
    """When a template exists only in bundled, overrides dir doesn't interfere."""
    (tmp_path / "greet.txt.j2").write_text("BUNDLED: {{ name }}")
    overrides = tmp_path / "overrides"
    overrides.mkdir()

    engine = TemplateEngine(tmp_path, user_overrides_dir=overrides)
    result = engine.render("greet.txt.j2", {"name": "test"})
    assert result == "BUNDLED: test"


def test_engine_user_overrides_dir_none_is_safe(tmp_path: Path):
    """Passing None for user_overrides_dir is safe."""
    (tmp_path / "greet.txt.j2").write_text("BUNDLED")

    engine = TemplateEngine(tmp_path, user_overrides_dir=None)
    assert engine.render("greet.txt.j2", {}) == "BUNDLED"


def test_engine_priority_chain(tmp_path: Path):
    """Priority: user_overrides > shared > bundled."""
    # Bundled
    (tmp_path / "conf.txt.j2").write_text("BUNDLED")
    # Shared
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "conf.txt.j2").write_text("SHARED")
    # User overrides
    overrides = tmp_path / "overrides"
    overrides.mkdir()
    (overrides / "conf.txt.j2").write_text("OVERRIDE")

    engine = TemplateEngine(
        tmp_path,
        shared_templates_dir=shared,
        user_overrides_dir=overrides,
    )
    assert engine.render("conf.txt.j2", {}) == "OVERRIDE"


def test_engine_shared_overrides_bundled(tmp_path: Path):
    """Without user_overrides, shared takes priority."""
    (tmp_path / "conf.txt.j2").write_text("BUNDLED")
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "conf.txt.j2").write_text("SHARED")

    engine = TemplateEngine(tmp_path, shared_templates_dir=shared)
    assert engine.render("conf.txt.j2", {}) == "SHARED"
