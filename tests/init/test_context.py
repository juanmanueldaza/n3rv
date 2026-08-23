"""Tests for ProjectContext model."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from n3rverberage.init.context import ProjectContext, Stack


def test_stack_enum_values():
    """Test Stack enum has required values."""
    assert Stack.PYTHON == "python"
    assert Stack.NODE == "node"
    assert Stack.GO == "go"
    assert Stack.GENERIC == "generic"


def test_project_context_build():
    """Test ProjectContext.build() creates valid context with auto-populated fields."""
    ctx = ProjectContext.build(project_name="myapp", stack=Stack.PYTHON, project_root=Path("/tmp/myapp"))

    assert ctx.project_name == "myapp"
    assert ctx.stack == Stack.PYTHON
    assert isinstance(ctx.n3rverberage_version, str)
    assert len(ctx.n3rverberage_version) > 0
    assert isinstance(ctx.timestamp, str)
    assert "T" in ctx.timestamp  # ISO 8601 format


def test_project_context_to_dict():
    """Test to_dict() returns correct structure for Jinja2 rendering."""
    ctx = ProjectContext.build(
        project_name="testproject",
        stack=Stack.NODE,
        project_root=Path("/tmp/testproject"),
    )
    result = ctx.to_dict()

    assert result["project_name"] == "testproject"
    assert result["stack"] == "node"  # Stack enum converted to string
    assert result["n3rverberage_version"] in ("dev", "0.1.0", "0.1.1")
    assert "timestamp" in result


def test_project_context_validates_project_name():
    """Test that empty or invalid project names raise ValidationError."""
    with pytest.raises(ValidationError):
        ProjectContext.build(project_name="", stack=Stack.PYTHON, project_root=Path("/tmp"))


def test_stack_validation():
    """Test that invalid stack values raise ValidationError."""
    # Direct construction with invalid stack should fail
    with pytest.raises(ValidationError):
        ProjectContext(
            project_name="test",
            stack="invalid",  # type: ignore
            n3rverberage_version="0.1.0",
            timestamp="2025-01-15T00:00:00Z",
        )
