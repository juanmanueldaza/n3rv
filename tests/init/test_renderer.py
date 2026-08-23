"""Tests for Jinja2 template rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from n3rverberage.init.renderer import TemplateEngine, TemplateRenderError


@pytest.fixture
def templates_dir(tmp_path: Path) -> Path:
    """Create a temporary templates directory with test templates."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()

    # Simple template
    (tpl_dir / "simple.txt.j2").write_text("Hello {{ name }}!")

    # Template with stack conditional
    (tpl_dir / "conditional.txt.j2").write_text(
        "Stack: {% if stack == 'python' %}Python{% elif stack == 'node' %}Node.js{% else %}Other{% endif %}"
    )

    # Template with undefined variable
    (tpl_dir / "undefined.txt.j2").write_text("Value: {{ undefined_var }}")

    return tpl_dir


def test_render_simple_template(templates_dir: Path):
    """Test rendering a simple template with variables."""
    engine = TemplateEngine(templates_dir)
    result = engine.render("simple.txt.j2", {"name": "World"})
    assert result == "Hello World!"


def test_render_with_stack_conditional(templates_dir: Path):
    """Test template with stack-conditional blocks."""
    engine = TemplateEngine(templates_dir)

    result_python = engine.render("conditional.txt.j2", {"stack": "python"})
    assert result_python == "Stack: Python"

    result_node = engine.render("conditional.txt.j2", {"stack": "node"})
    assert result_node == "Stack: Node.js"

    result_other = engine.render("conditional.txt.j2", {"stack": "go"})
    assert result_other == "Stack: Other"


def test_undefined_variable_raises_error(templates_dir: Path):
    """Test that undefined variables raise TemplateRenderError."""
    engine = TemplateEngine(templates_dir)

    with pytest.raises(TemplateRenderError) as exc_info:
        engine.render("undefined.txt.j2", {"name": "test"})

    assert "undefined_var" in str(exc_info.value).lower()


def test_template_not_found_raises_error(templates_dir: Path):
    """Test that missing templates raise TemplateRenderError."""
    engine = TemplateEngine(templates_dir)

    with pytest.raises(TemplateRenderError) as exc_info:
        engine.render("nonexistent.txt.j2", {})

    assert "nonexistent.txt.j2" in str(exc_info.value).lower()


def test_shared_templates_override_bundled(templates_dir: Path, tmp_path: Path):
    """Shared templates override bundled templates with the same name."""
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()
    (shared_dir / "override.txt.j2").write_text("SHARED: {{ value }}")
    # Bundled version (different content)
    (templates_dir / "override.txt.j2").write_text("BUNDLED: {{ value }}")

    engine = TemplateEngine(templates_dir, shared_templates_dir=shared_dir)
    result = engine.render("override.txt.j2", {"value": "win"})
    assert result == "SHARED: win"


def test_shared_templates_fall_through_to_bundled(templates_dir: Path, tmp_path: Path):
    """When a template only exists in bundled, shared doesn't interfere."""
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()

    engine = TemplateEngine(templates_dir, shared_templates_dir=shared_dir)
    result = engine.render("simple.txt.j2", {"name": "World"})
    assert result == "Hello World!"


def test_shared_templates_dir_none_is_backward_compat(templates_dir: Path):
    """Passing None for shared_templates_dir produces identical behavior."""
    engine = TemplateEngine(templates_dir, shared_templates_dir=None)
    result = engine.render("simple.txt.j2", {"name": "World"})
    assert result == "Hello World!"


def test_shared_templates_dir_default_is_none(templates_dir: Path):
    """Omitting shared_templates_dir produces identical behavior."""
    engine = TemplateEngine(templates_dir)
    result = engine.render("simple.txt.j2", {"name": "World"})
    assert result == "Hello World!"


def test_context_with_project_context(templates_dir: Path):
    """Test rendering with ProjectContext-like dict."""
    (templates_dir / "full.txt.j2").write_text(
        "Project: {{ project_name }}\nStack: {{ stack }}\nVersion: {{ n3rverberage_version }}"
    )

    engine = TemplateEngine(templates_dir)
    result = engine.render(
        "full.txt.j2",
        {
            "project_name": "myapp",
            "stack": "python",
            "n3rverberage_version": "0.1.0",
        },
    )

    assert "Project: myapp" in result
    assert "Stack: python" in result
    assert "Version: 0.1.0" in result
