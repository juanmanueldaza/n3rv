"""Tests for models.py."""

from __future__ import annotations

import pickle

import pytest
from pydantic import ValidationError

from n3rverberage.providers.models import (
    AllProvidersExhaustedError,
    ProviderError,
    QuotaExhaustedError,
    ToolCall,
    ToolResult,
)


class TestToolCall:
    def test_basic(self) -> None:
        tc = ToolCall(id="call_1", name="get_weather", arguments={"city": "Tokyo"})
        assert tc.id == "call_1"
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Tokyo"}

    def test_default_arguments(self) -> None:
        tc = ToolCall(id="c1", name="fn")
        assert tc.arguments == {}

    def test_empty_arguments(self) -> None:
        tc = ToolCall(id="c1", name="fn", arguments={})
        assert tc.arguments == {}

    def test_validates_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ToolCall(id="c1")  # type: ignore[call-arg]


class TestToolResult:
    def test_no_tool_calls(self) -> None:
        tr = ToolResult(content="Hello")
        assert tr.content == "Hello"
        assert tr.tool_calls == []

    def test_with_tool_calls(self) -> None:
        tc = ToolCall(id="c1", name="fn", arguments={"x": 1})
        tr = ToolResult(content=None, tool_calls=[tc])
        assert tr.content is None
        assert len(tr.tool_calls) == 1
        assert tr.tool_calls[0].name == "fn"

    def test_default_content(self) -> None:
        tr = ToolResult()
        assert tr.content is None
        assert tr.tool_calls == []


class TestProviderError:
    def test_basic(self) -> None:
        err = ProviderError("model-1", 429, "rate limited")
        assert err.model_id == "model-1"
        assert err.status_code == 429
        assert err.body == "rate limited"
        assert "model-1" in str(err)
        assert "429" in str(err)

    def test_default_body(self) -> None:
        err = ProviderError("m", 500)
        assert err.status_code == 500
        assert err.body is None

    def test_pickling(self) -> None:
        err = pickle.loads(pickle.dumps(ProviderError("m", 401, "bad auth")))
        assert err.model_id == "m"
        assert err.status_code == 401
        assert err.body == "bad auth"


class TestQuotaExhaustedError:
    def test_is_provider_error(self) -> None:
        err = QuotaExhaustedError("m", 429, "code: AllocationQuota.FreeTierOnly")
        assert isinstance(err, ProviderError)
        assert isinstance(err, RuntimeError)
        assert err.model_id == "m"
        assert err.status_code == 429
        assert "FreeTierOnly" in (err.body or "")

    def test_pickling(self) -> None:
        err = pickle.loads(pickle.dumps(QuotaExhaustedError("m", 429, "quota")))
        assert isinstance(err, QuotaExhaustedError)
        assert err.model_id == "m"


class TestAllProvidersExhaustedError:
    def test_basic(self) -> None:
        err = AllProvidersExhaustedError(["m1", "m2"])
        assert err.exhausted_model_ids == ["m1", "m2"]
        assert "m1" in str(err)
        assert "m2" in str(err)

    def test_empty_list(self) -> None:
        err = AllProvidersExhaustedError([])
        assert err.exhausted_model_ids == []
