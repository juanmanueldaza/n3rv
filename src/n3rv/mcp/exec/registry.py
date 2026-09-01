"""Registry: all coding languages that codebase-memory-mcp tree-sitter covers (20+)."""

from __future__ import annotations

# ── Language → extensions, linter, typechecker, test runner, config files ──
# Twin to CodeGraph tree-sitter multilang (#51) — every grammar gets a lint entry.
# Data structure > code: single source of truth for watcher/service/server.

REGISTRY: dict[str, dict] = {
    "python": {
        "exts": [".py", ".pyi"],
        "lint": ("ruff", ["ruff", "check"]),
        "typecheck": ("mypy", ["mypy"]),
        "test": ("pytest", ["pytest", "-q"]),
        "configs": ["pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg"],
    },
    "javascript": {
        "exts": [".js", ".jsx", ".mjs", ".cjs"],
        "lint": ("eslint", ["eslint", "."]),
        "typecheck": ("tsc", ["tsc", "--noEmit"]),
        "test": ("npm", ["npm", "test", "--"]),
        "configs": ["package.json", ".eslintrc", ".eslintrc.json", "eslint.config.js"],
    },
    "typescript": {
        "exts": [".ts", ".tsx", ".mts", ".cts"],
        "lint": ("eslint", ["eslint", "."]),
        "typecheck": ("tsc", ["tsc", "--noEmit"]),
        "test": ("npm", ["npm", "test", "--"]),
        "configs": ["package.json", "tsconfig.json", ".eslintrc.json"],
    },
    "go": {
        "exts": [".go"],
        "lint": ("golangci-lint", ["golangci-lint", "run"]),
        "typecheck": ("go", ["go", "vet", "./..."]),
        "test": ("go", ["go", "test", "./..."]),
        "configs": ["go.mod", "go.sum", ".golangci.yml", ".golangci.yaml"],
    },
    "rust": {
        "exts": [".rs"],
        "lint": ("cargo", ["cargo", "clippy"]),
        "typecheck": ("cargo", ["cargo", "check"]),
        "test": ("cargo", ["cargo", "test"]),
        "configs": ["Cargo.toml", "Cargo.lock", "clippy.toml"],
    },
    "java": {
        "exts": [".java"],
        "lint": ("checkstyle", ["checkstyle"]),
        "typecheck": ("javac", ["javac"]),
        "test": ("mvn", ["mvn", "test"]),
        "configs": ["pom.xml", "build.gradle", "checkstyle.xml"],
    },
    "kotlin": {
        "exts": [".kt", ".kts"],
        "lint": ("ktlint", ["ktlint"]),
        "typecheck": ("kotlinc", ["kotlinc"]),
        "test": ("gradle", ["gradle", "test"]),
        "configs": ["build.gradle.kts"],
    },
    "swift": {
        "exts": [".swift"],
        "lint": ("swiftlint", ["swiftlint"]),
        "typecheck": ("swiftc", ["swiftc"]),
        "test": ("swift", ["swift", "test"]),
        "configs": ["Package.swift", ".swiftlint.yml"],
    },
    "objc": {
        "exts": [".m", ".mm", ".h"],
        "lint": ("clang-tidy", ["clang-tidy"]),
        "typecheck": ("clang", ["clang", "--analyze"]),
        "test": ("xcodebuild", ["xcodebuild", "test"]),
        "configs": [".clang-tidy"],
    },
    "ruby": {
        "exts": [".rb", ".rake"],
        "lint": ("rubocop", ["rubocop"]),
        "typecheck": ("ruby", ["ruby", "-c"]),
        "test": ("rspec", ["rspec"]),
        "configs": ["Gemfile", ".rubocop.yml"],
    },
    "php": {
        "exts": [".php"],
        "lint": ("phpcs", ["phpcs"]),
        "typecheck": ("phpstan", ["phpstan", "analyse"]),
        "test": ("phpunit", ["phpunit"]),
        "configs": ["composer.json", "phpcs.xml", "phpstan.neon"],
    },
    "csharp": {
        "exts": [".cs"],
        "lint": ("dotnet", ["dotnet", "format", "--verify-no-changes"]),
        "typecheck": ("dotnet", ["dotnet", "build"]),
        "test": ("dotnet", ["dotnet", "test"]),
        "configs": ["*.csproj", "*.sln", ".editorconfig"],
    },
    "cpp": {
        "exts": [".cpp", ".cc", ".cxx", ".hpp", ".hh", ".c", ".h"],
        "lint": ("clang-tidy", ["clang-tidy"]),
        "typecheck": ("clang", ["clang", "--analyze"]),
        "test": ("ctest", ["ctest"]),
        "configs": ["CMakeLists.txt", ".clang-tidy", "compile_commands.json"],
    },
    "scala": {
        "exts": [".scala", ".sc"],
        "lint": ("scalastyle", ["scalastyle"]),
        "typecheck": ("scalac", ["scalac"]),
        "test": ("sbt", ["sbt", "test"]),
        "configs": ["build.sbt"],
    },
    "dart": {
        "exts": [".dart"],
        "lint": ("dart", ["dart", "analyze"]),
        "typecheck": ("dart", ["dart", "analyze"]),
        "test": ("dart", ["dart", "test"]),
        "configs": ["pubspec.yaml", "analysis_options.yaml"],
    },
    "lua": {
        "exts": [".lua"],
        "lint": ("luacheck", ["luacheck", "."]),
        "typecheck": ("lua", ["luac", "-p"]),
        "test": ("busted", ["busted"]),
        "configs": [".luacheckrc"],
    },
    "shell": {
        "exts": [".sh", ".bash", ".zsh"],
        "lint": ("shellcheck", ["shellcheck"]),
        "typecheck": ("bash", ["bash", "-n"]),
        "test": ("bats", ["bats"]),
        "configs": [".shellcheckrc"],
    },
    "zig": {
        "exts": [".zig"],
        "lint": ("zig", ["zig", "fmt", "--check"]),
        "typecheck": ("zig", ["zig", "build-exe", "--check"]),
        "test": ("zig", ["zig", "test"]),
        "configs": ["build.zig"],
    },
    "elixir": {
        "exts": [".ex", ".exs"],
        "lint": ("credo", ["mix", "credo"]),
        "typecheck": ("dialyzer", ["mix", "dialyzer"]),
        "test": ("exunit", ["mix", "test"]),
        "configs": ["mix.exs", ".credo.exs"],
    },
    "haskell": {
        "exts": [".hs"],
        "lint": ("hlint", ["hlint"]),
        "typecheck": ("ghc", ["ghc", "-fno-code"]),
        "test": ("cabal", ["cabal", "test"]),
        "configs": ["*.cabal", "stack.yaml"],
    },
}

# Derived sets — used by watcher/service (no duplication)
ALL_EXTS: set[str] = {ext for info in REGISTRY.values() for ext in info["exts"]}
ALL_CONFIGS: set[str] = {cfg for info in REGISTRY.values() for cfg in info["configs"]}
# Flatten lint/typecheck/test tool names ordered by registry insertion (python first)
LINT_CHAIN: list[tuple[str, list[str]]] = [info["lint"] for info in REGISTRY.values()]
TYPECHECK_CHAIN: list[tuple[str, list[str]]] = [info["typecheck"] for info in REGISTRY.values()]
TEST_CHAIN: list[tuple[str, list[str]]] = [info["test"] for info in REGISTRY.values()]

# Extension → lint mapping for per-file dispatch (universal, not global first-available)
EXT_TO_LINT: dict[str, tuple[str, list[str]]] = {}
for _lang, info in REGISTRY.items():
    for ext in info["exts"]:
        EXT_TO_LINT[ext] = info["lint"]


def get_lint_for_ext(ext: str) -> tuple[str, list[str]] | None:
    return EXT_TO_LINT.get(ext)


def get_all_exts() -> set[str]:
    return ALL_EXTS


def get_all_configs() -> set[str]:
    return ALL_CONFIGS
