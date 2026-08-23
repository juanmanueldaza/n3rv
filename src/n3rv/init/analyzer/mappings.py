"""Framework and tool detection mappings – pure data, no logic.

To add a new framework: add an entry to KNOWN_FRAMEWORKS or KNOWN_NPM_FRAMEWORKS.
To add a new tool command: add to TOOL_SCRIPT_KEYS.
"""

from __future__ import annotations

from typing import TypedDict


class FrameworkMapping(TypedDict):
    name: str
    category: str
    guidance: str


KNOWN_FRAMEWORKS: dict[str, FrameworkMapping] = {
    # Web
    "fastapi": {
        "name": "FastAPI",
        "category": "web",
        "guidance": (
            "FastAPI patterns:\n"
            "- Use `@app.get/post/put/delete` decorators for route handlers\n"
            "- Use `Depends()` for dependency injection\n"
            "- Use Pydantic models for request/response validation\n"
            "- Use `HTTPException` for error responses\n"
            "- Prefer `async def` handlers for I/O-bound endpoints"
        ),
    },
    "flask": {
        "name": "Flask",
        "category": "web",
        "guidance": (
            "Flask patterns:\n"
            "- Use `@app.route()` decorators for endpoints\n"
            "- Use `flask.g` for request-scoped state\n"
            "- Use `flask.current_app` for app config access\n"
            "- Use `flask.Blueprint` for modular route groups"
        ),
    },
    "django": {
        "name": "Django",
        "category": "web",
        "guidance": (
            "Django patterns:\n"
            "- Use class-based views (CBV) for CRUD operations\n"
            "- Use `django.forms` for form handling and validation\n"
            "- Use `django.views.decorators.csrf.csrf_exempt` for API views\n"
            "- Use `manage.py` as the entry point for Django commands"
        ),
    },
    # ORM
    "sqlalchemy": {
        "name": "SQLAlchemy",
        "category": "orm",
        "guidance": (
            "SQLAlchemy patterns:\n"
            "- Use `session.execute(select(Model))` for queries (2.0 style)\n"
            "- Use `Mapped` and `mapped_column` for ORM models (2.0 declarative)\n"
            "- Use `selectinload()` for eager loading relationships\n"
            "- Always use context managers with sessions: `with Session() as session:`"
        ),
    },
    "tortoise-orm": {
        "name": "Tortoise ORM",
        "category": "orm",
        "guidance": (
            "Tortoise ORM patterns:\n"
            "- Use `await Model.filter(...).first()` for async queries\n"
            "- Use `await Model.create(...)` or `await model.save()` for writes\n"
            "- Use `tortoise.contrib.pydantic` for Pydantic integration\n"
            "- Initialize with `Tortoise.init(config=...)` at startup"
        ),
    },
    # Testing
    "pytest": {
        "name": "pytest",
        "category": "testing",
        "guidance": (
            "pytest patterns:\n"
            "- Use `conftest.py` for shared fixtures\n"
            "- Use `@pytest.mark.parametrize` for table-driven tests\n"
            "- Use `tmp_path` fixture for temporary file system\n"
            "- Use `monkeypatch` fixture for mocking\n"
            "- Name test files `test_*.py` and functions `test_*`"
        ),
    },
    # Linting & formatting
    "ruff": {
        "name": "ruff",
        "category": "linting",
        "guidance": (
            "ruff conventions:\n"
            "- Run `ruff check .` for linting, `ruff format .` for formatting\n"
            "- Configure rules in `pyproject.toml` under `[tool.ruff]`\n"
            "- Use `# noqa: RULE` for inline suppressions, not blanket disable"
        ),
    },
    "black": {
        "name": "black",
        "category": "formatting",
        "guidance": (
            "black conventions:\n"
            "- Run `black .` for formatting\n"
            "- Configure line length in `pyproject.toml` `[tool.black]`\n"
            "- Use `# fmt: off` / `# fmt: on` sparingly"
        ),
    },
    "mypy": {
        "name": "mypy",
        "category": "typechecking",
        "guidance": (
            "mypy conventions:\n"
            "- Run `mypy src/` for type checking\n"
            "- Configure in `pyproject.toml` under `[tool.mypy]`\n"
            "- Use `# type: ignore[code]` with specific error codes"
        ),
    },
}

KNOWN_NPM_FRAMEWORKS: dict[str, FrameworkMapping] = {
    "react": {
        "name": "React",
        "category": "web",
        "guidance": (
            "React patterns:\n"
            "- Use functional components with hooks\n"
            "- Use `useState` for local state, `useEffect` for side effects\n"
            "- Use `useCallback`/`useMemo` for performance optimization\n"
            "- Prefer controlled components"
        ),
    },
    "next": {
        "name": "Next.js",
        "category": "web",
        "guidance": (
            "Next.js patterns:\n"
            "- Use App Router (app/) for new projects\n"
            "- Use Server Components by default, opt-in to Client Components\n"
            "- Use `next/link` for client-side navigation\n"
            "- Use Route Handlers for API endpoints"
        ),
    },
    "express": {
        "name": "Express",
        "category": "web",
        "guidance": (
            "Express patterns:\n"
            "- Use `app.use()` for middleware\n"
            "- Use `express.Router()` for modular route groups\n"
            "- Always call `next(err)` for error propagation\n"
            "- Use environment variables for configuration"
        ),
    },
    "jest": {
        "name": "Jest",
        "category": "testing",
        "guidance": (
            "Jest patterns:\n"
            "- Use `describe`/`it` for test organization\n"
            "- Use `jest.mock()` for module mocking\n"
            "- Use `expect().toMatchSnapshot()` for snapshots\n"
            "- Name test files `*.test.js` or `*.spec.js`"
        ),
    },
}

TOOL_SCRIPT_KEYS: dict[str, dict] = {
    "test": {"name": "test", "category": "testing"},
    "lint": {"name": "lint", "category": "linting"},
    "format": {"name": "format", "category": "formatting"},
    "typecheck": {"name": "typecheck", "category": "typechecking"},
    "check": {"name": "check", "category": "linting"},
    "build": {"name": "build", "category": "build"},
}

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".opencode",
        ".n3rv",
        ".githooks",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        ".env",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        "egg-info",
        ".eggs",
    }
)
