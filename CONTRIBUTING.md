# Contributing to reverberage

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

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add or update tests as needed
5. Ensure all tests pass (`pytest`)
6. Ensure code follows style guidelines (`ruff check .` and `ruff format --check .`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

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

1. At least one maintainer must review your PR
2. All CI checks must pass
3. Address any review comments
4. Once approved, a maintainer will merge your PR

## Questions?

Feel free to open an issue with the "question" label if you need help.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
