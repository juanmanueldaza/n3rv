"""Tests for FallbackProvider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from n3rverberage.providers.fallback import FallbackProvider
from n3rverberage.providers.models import (
    AllProvidersExhaustedError,
    ProviderError,
    QuotaExhaustedError,
    ToolResult,
)


def _make_provider(name: str = "provider_a") -> MagicMock:
    """Build a mock provider that succeeds."""
    provider = MagicMock()
    provider.model = name
    provider.complete.return_value = f"response from {name}"
    provider.complete_structured.return_value = None
    provider.complete_with_tools.return_value = ToolResult(content=f"tools from {name}")
    return provider


def _make_quota_provider(name: str = "exhausted", model_id: str | None = None) -> MagicMock:
    """Build a mock provider that raises QuotaExhaustedError."""
    provider = MagicMock()
    provider.model = name
    provider.complete.side_effect = QuotaExhaustedError(model_id or name, 429, "quota exhausted")
    provider.complete_structured.side_effect = QuotaExhaustedError(model_id or name, 429, "quota exhausted")
    provider.complete_with_tools.side_effect = QuotaExhaustedError(model_id or name, 429, "quota exhausted")
    return provider


def _make_error_provider(name: str = "broken") -> MagicMock:
    """Build a mock provider that raises generic ProviderError."""
    provider = MagicMock()
    provider.model = name
    provider.complete.side_effect = ProviderError(name, 500, "internal error")
    provider.complete_structured.side_effect = ProviderError(name, 500, "internal error")
    provider.complete_with_tools.side_effect = ProviderError(name, 500, "internal error")
    return provider


class TestConstructor:
    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one"):
            FallbackProvider([])

    def test_single_provider(self) -> None:
        p = _make_provider("a")
        fb = FallbackProvider([p])
        assert fb._default_model() == "a"


class TestComplete:
    def test_first_succeeds(self) -> None:
        a = _make_provider("a")
        b = _make_provider("b")
        fb = FallbackProvider([a, b])

        result = fb.complete([{"role": "user", "content": "Hi"}])
        assert result == "response from a"
        a.complete.assert_called_once()
        b.complete.assert_not_called()

    def test_fallback_to_second(self) -> None:
        a = _make_quota_provider("a")
        b = _make_provider("b")
        fb = FallbackProvider([a, b])

        result = fb.complete([{"role": "user", "content": "Hi"}])
        assert result == "response from b"
        a.complete.assert_called_once()
        b.complete.assert_called_once()

    def test_all_exhausted(self) -> None:
        a = _make_quota_provider("a")
        b = _make_quota_provider("b")
        fb = FallbackProvider([a, b])

        with pytest.raises(AllProvidersExhaustedError) as exc:
            fb.complete([{"role": "user", "content": "Hi"}])
        assert exc.value.exhausted_model_ids == ["a", "b"]

    def test_non_quota_error_propagates(self) -> None:
        """Non-quota errors should NOT trigger fallback."""
        a = _make_error_provider("a")
        b = _make_provider("b")
        fb = FallbackProvider([a, b])

        with pytest.raises(ProviderError):
            fb.complete([{"role": "user", "content": "Hi"}])
        b.complete.assert_not_called()


class TestCompleteStructured:
    def test_fallback(self) -> None:
        from pydantic import BaseModel

        class Dummy(BaseModel):
            x: str

        a = _make_quota_provider("a")
        b = _make_provider("b")
        b.complete_structured.return_value = Dummy(x="from b")
        fb = FallbackProvider([a, b])

        result = fb.complete_structured([{"role": "user", "content": "extract"}], Dummy)
        assert isinstance(result, Dummy)
        assert result.x == "from b"

    def test_all_exhausted(self) -> None:
        from pydantic import BaseModel

        class Dummy(BaseModel):
            x: str

        a = _make_quota_provider("a")
        b = _make_quota_provider("b")
        fb = FallbackProvider([a, b])

        with pytest.raises(AllProvidersExhaustedError) as exc:
            fb.complete_structured([{"role": "user", "content": "extract"}], Dummy)
        assert len(exc.value.exhausted_model_ids) == 2


class TestCompleteWithTools:
    def test_fallback(self) -> None:
        a = _make_quota_provider("a")
        b = _make_provider("b")
        fb = FallbackProvider([a, b])

        result = fb.complete_with_tools(
            [{"role": "user", "content": "Hi"}],
            [{"type": "function", "function": {"name": "f"}}],
        )
        assert result.content == "tools from b"

    def test_all_exhausted(self) -> None:
        a = _make_quota_provider("a")
        b = _make_quota_provider("b")
        fb = FallbackProvider([a, b])

        with pytest.raises(AllProvidersExhaustedError):
            fb.complete_with_tools(
                [{"role": "user", "content": "Hi"}],
                [{"type": "function", "function": {"name": "f"}}],
            )


class TestMixedProviders:
    def test_mixed_quota_and_error(self) -> None:
        a = _make_provider("a")
        b = _make_error_provider("b")
        c = _make_provider("c")
        fb = FallbackProvider([a])

        result = fb.complete([])
        assert result == "response from a"

        fb2 = FallbackProvider([_make_quota_provider("q"), b, c])
        with pytest.raises(ProviderError):
            fb2.complete([])
        c.complete.assert_not_called()
