# Contributing to n3rv

Thank you for your interest in contributing to reverberage! This document provides guidelines for contributing to this project.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, please include as many details as possible:

- Use the bug report template when creating an issue
- Include steps to reproduce the bug
- Describe what you expected to happen
- Describe what actually happened
- Include your environment details (OS, Python version, package version)

### Suggesting Features

Feature suggestions are welcome! When suggesting a feature:

- Use the feature request template when creating an issue
- Explain the use case and why this feature would be useful
- Describe how you envision the feature working
- Consider how this aligns with the project's goals

### Pull Requests

> **Branch protection:** `main` is protected. No direct pushes — all changes go through a PR. CI is a PR gate: 4 required status checks (`Lint & Format`, `Test (Python 3.11/3.12/3.13)`) + 1 approving review, `strict: true`, `enforce_admins: true`. `git push origin main` will be rejected.

1. Fork the repository (or create a feature branch if you have write access: `git checkout -b feat/amazing-feature`)
2. Make your changes (follow SDD: `/sdd-new <change>` → `explore → … → verify`)
3. Add or update tests as needed
4. Ensure all checks pass locally:

   ```bash
   ruff check . && ruff format --check . && pytest -q
   ```

5. Commit with conventional commits (`feat(scope): description`)
6. Push to your branch (`git push origin feat/amazing-feature`)
7. Open a Pull Request against `main` — verify the 4 CI checks are green
8. Address review comments (push fixups to same branch; `strict: true` requires branch up-to-date)
9. Squash-merge only after 1 approving review + all 4 checks pass (`gh pr merge --squash --auto`)

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
cd REPO_NAME

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
ruff format --check .
```

## Coding Standards

- Follow PEP 8 style guidelines
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Write tests for new functionality
- Update documentation as needed

## Commit Messages

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
- `feat(engine): add support for batch processing`
- `fix(cli): handle missing configuration file`
- `docs(readme): update installation instructions`

## Review Process

1. At least one maintainer must approve your PR
2. All 4 CI checks must be green (`Lint & Format`, `Test 3.11`, `Test 3.12`, `Test 3.13`) — branch must be up-to-date with `main` (`strict: true`)
3. Address any review comments
4. Once approved + green, squash-merge (`gh pr merge --squash --auto`); direct pushes to `main` are blocked even for admins

## Questions?

Feel free to open an issue with the "question" label if you need help.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
