"""Jinja2 template rendering engine with context validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    UndefinedError,
    select_autoescape,
)

logger = logging.getLogger("n3rverberage.renderer")

CONTEXT_SCHEMA_FILE = "context.json"

_TYPES: dict[str, type] = {
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": float,
    "array": list,
    "object": dict,
}


class TemplateRenderError(Exception):
    """Error during template rendering."""


class ContextValidationError(TemplateRenderError):
    """Context failed schema validation."""


def _load_schema(templates_dir: Path) -> dict[str, Any]:
    """Load the context schema from the templates directory."""
    schema_path = templates_dir / CONTEXT_SCHEMA_FILE
    if not schema_path.is_file():
        logger.debug("No context schema found at %s", schema_path)
        return {}
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        return data.get("variables", {}) if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load context schema: %s", exc)
        return {}


def validate_context(context: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate template context against the schema.

    Args:
        context: The context dict to validate.
        schema: Variable definitions from context.json.

    Raises:
        ContextValidationError: If validation fails.
    """
    errors: list[str] = []

    for var_name, spec in schema.items():
        if not isinstance(spec, dict):
            continue

        required = spec.get("required", False)
        var_type = spec.get("type", "string")
        enum_vals = spec.get("enum")
        default = spec.get("default")

        # Check required
        if required and var_name not in context:
            errors.append(f"Missing required context variable: '{var_name}'")
            continue

        if var_name not in context:
            if default is not None:
                context[var_name] = default
            continue

        value = context[var_name]

        # Type check
        py_type = _TYPES.get(var_type)
        if py_type and not isinstance(value, py_type):
            errors.append(f"Context variable '{var_name}': expected {var_type}, got {type(value).__name__}")
            continue

        # Enum check
        if enum_vals and value not in enum_vals:
            errors.append(f"Context variable '{var_name}': '{value}' not in allowed values {enum_vals}")

    # Warn about unknown variables
    known = set(schema.keys())
    provided = set(context.keys())
    unknown = provided - known
    if unknown:
        logger.debug("Unknown context variables (ignored): %s", sorted(unknown))

    if errors:
        raise ContextValidationError("Template context validation failed:\n  " + "\n  ".join(errors))


class TemplateEngine:
    """Jinja2-based template rendering engine.

    Supports template resolution with the following priority chain:
        user_overrides > shared > bundled

    When *shared_templates_dir* is provided, shared templates override bundled
    (template name collision => shared wins). Project-level overrides are added
    by the caller prepending another FileSystemLoader to the ChoiceLoader list.

    Context validation is performed against ``context.json`` (if present in the
    bundled templates directory) before each render call.
    """

    def __init__(
        self,
        templates_dir: Path,
        shared_templates_dir: Path | None = None,
        user_overrides_dir: Path | None = None,
    ) -> None:
        loaders = []
        if user_overrides_dir is not None:
            loaders.append(FileSystemLoader(str(user_overrides_dir)))
        if shared_templates_dir is not None:
            loaders.append(FileSystemLoader(str(shared_templates_dir)))
        loaders.append(FileSystemLoader(str(templates_dir)))
        loader = ChoiceLoader(loaders) if len(loaders) > 1 else loaders[0]
        self.env = Environment(
            loader=loader,
            autoescape=select_autoescape(default_for_string=False, default=False),
            undefined=StrictUndefined,
        )
        self._schema = _load_schema(templates_dir)

    def validate(self, context: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize context against the bundled schema.

        Returns a (possibly mutated) copy of *context* with defaults applied.
        The original dict is not modified.
        """
        ctx = dict(context)
        validate_context(ctx, self._schema)
        return ctx

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context.

        Validates *context* against the bundled schema first.
        """
        ctx = self.validate(context)
        try:
            template = self.env.get_template(template_name)
            return template.render(ctx)
        except TemplateNotFound as exc:
            raise TemplateRenderError(f"Template not found: {template_name}") from exc
        except UndefinedError as exc:
            raise TemplateRenderError(f"Undefined variable in template {template_name}: {exc}") from exc
