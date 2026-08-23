"""Tests for QwenProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from conftest import make_429_error, make_mock_response
from pydantic import BaseModel

from n3rverberage.providers.models import ProviderError, QuotaExhaustedError
from n3rverberage.providers.qwen import QwenProvider, _is_free_tier_exhausted


@pytest.fixture
def provider(mock_openai_client: MagicMock) -> QwenProvider:
    with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
        return QwenProvider()


@pytest.fixture
def mock_create(mock_openai_client: MagicMock) -> MagicMock:
    return mock_openai_client.chat.completions.create


class TestConstructor:
    def test_from_env(self) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-env"}):
            p = QwenProvider()
        assert p.model == "qwen3-coder-plus"

    def test_explicit_args(self) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-env"}):
            p = QwenProvider(
                api_key="sk-custom",
                model="qwen3.7-plus",
                base_url="http://custom/v1",
            )
        assert p.model == "qwen3.7-plus"
        assert p.base_url == "http://custom/v1"

    def test_missing_api_key(self) -> None:
        with patch.dict("os.environ", clear=True):
            with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
                QwenProvider()

    def test_base_url_from_env_var(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_QWEN_BASE_URL": "https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
            },
        ):
            p = QwenProvider()
        assert p.base_url == "https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"

    def test_explicit_base_url_overrides_env_var(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_QWEN_BASE_URL": "https://env-override/v1",
            },
        ):
            p = QwenProvider(base_url="https://explicit/v1")
        assert p.base_url == "https://explicit/v1"


class TestComplete:
    def test_basic(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="Hello world")
        result = provider.complete([{"role": "user", "content": "Hi"}])
        assert result == "Hello world"

    def test_sends_correct_payload(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response()
        provider.complete([{"role": "user", "content": "Hi"}], temperature=0.5)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "qwen3-coder-plus"
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 4096

    def test_429_free_tier_exhausted(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_create.side_effect = make_429_error(
            body={"code": "AllocationQuota.FreeTierOnly", "message": "Quota exhausted"}
        )
        with pytest.raises(QuotaExhaustedError) as exc:
            provider.complete([{"role": "user", "content": "Hi"}])
        assert exc.value.status_code == 429
        assert "FreeTierOnly" in (exc.value.body or "")

    def test_429_without_free_tier(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_create.side_effect = make_429_error(body={"message": "Rate limited, slow down"})
        with pytest.raises(ProviderError) as exc:
            provider.complete([{"role": "user", "content": "Hi"}])
        assert exc.value.status_code == 429
        assert not isinstance(exc.value, QuotaExhaustedError)

    def test_401_unauthorized(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        import httpx
        from openai import APIStatusError

        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        response.headers = {}
        mock_create.side_effect = APIStatusError(
            message="Unauthorized",
            response=response,
            body={"message": "Invalid API key"},
        )
        with pytest.raises(ProviderError) as exc:
            provider.complete([{"role": "user", "content": "Hi"}])
        assert exc.value.status_code == 401

    def test_empty_content(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="")
        result = provider.complete([{"role": "user", "content": "Hi"}])
        assert result == ""

    def test_quota_header_capture(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        assert provider.last_quota_remaining is None
        mock_create.return_value = make_mock_response(content="ok", headers={"x-qwen-quota-remaining": "999986"})
        provider.complete([{"role": "user", "content": "Hi"}])
        assert provider.last_quota_remaining == 999986


class TestCompleteStructured:
    def test_basic(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        class Person(BaseModel):
            name: str
            age: int

        mock_create.return_value = make_mock_response(content='{"name": "Alice", "age": 30}')
        result = provider.complete_structured([{"role": "user", "content": "Extract person"}], Person)
        assert isinstance(result, Person)
        assert result.name == "Alice"
        assert result.age == 30

    def test_sends_response_format(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        class Item(BaseModel):
            name: str

        mock_create.return_value = make_mock_response(content='{"name": "x"}')
        provider.complete_structured([{"role": "user", "content": "Extract"}], Item)
        call_kwargs = mock_create.call_args[1]
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["strict"] is True

    def test_empty_response(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        class Item(BaseModel):
            name: str

        mock_create.return_value = make_mock_response(content="")
        with pytest.raises(ProviderError, match="Empty"):
            provider.complete_structured([{"role": "user", "content": "Extract"}], Item)

    def test_invalid_json(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        class Item(BaseModel):
            name: str

        mock_create.return_value = make_mock_response(content="not json")
        with pytest.raises(ProviderError, match="Invalid JSON"):
            provider.complete_structured([{"role": "user", "content": "Extract"}], Item)

    def test_validation_error(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        class Item(BaseModel):
            name: str

        mock_create.return_value = make_mock_response(content='{"name": 123}')
        with pytest.raises(ProviderError, match="Validation failed"):
            provider.complete_structured([{"role": "user", "content": "Extract"}], Item)


class TestCompleteWithTools:
    def test_no_tool_calls(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="Text response")
        result = provider.complete_with_tools([{"role": "user", "content": "Hi"}], [])
        assert result.content == "Text response"
        assert result.tool_calls == []

    def test_with_tool_calls(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_msg = MagicMock()
        mock_msg.content = ""
        tc1 = MagicMock()
        tc1.id = "call_1"
        tc1.function.name = "get_weather"
        tc1.function.arguments = '{"city": "Tokyo"}'
        tc2 = MagicMock()
        tc2.id = "call_2"
        tc2.function.name = "get_time"
        tc2.function.arguments = '{"tz": "UTC"}'
        mock_msg.tool_calls = [tc1, tc2]
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        resp = MagicMock()
        resp.choices = [mock_choice]
        resp.headers = {}
        mock_create.return_value = resp

        result = provider.complete_with_tools(
            [{"role": "user", "content": "Get weather"}],
            [{"type": "function", "function": {"name": "get_weather"}}],
        )
        assert result.content == ""
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0].id == "call_1"
        assert result.tool_calls[0].name == "get_weather"
        assert result.tool_calls[0].arguments == {"city": "Tokyo"}
        assert result.tool_calls[1].name == "get_time"

    def test_sends_tool_choice_auto(self, provider: QwenProvider, mock_create: MagicMock) -> None:
        mock_msg = MagicMock()
        mock_msg.content = "ok"
        mock_msg.tool_calls = None
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        resp = MagicMock()
        resp.choices = [mock_choice]
        resp.headers = {}
        mock_create.return_value = resp

        tools = [{"type": "function", "function": {"name": "f"}}]
        provider.complete_with_tools([{"role": "user", "content": "Hi"}], tools)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["tool_choice"] == "auto"
        assert call_kwargs["tools"] == tools


class TestIsFreeTierExhausted:
    def test_matching_body(self) -> None:
        exc = make_429_error(body={"code": "AllocationQuota.FreeTierOnly"})
        assert _is_free_tier_exhausted(exc)

    def test_non_matching_body(self) -> None:
        exc = make_429_error(body={"code": "RateLimitExceeded"})
        assert not _is_free_tier_exhausted(exc)

    def test_body_as_string(self) -> None:
        from unittest.mock import MagicMock

        from openai import APIStatusError

        exc = APIStatusError(
            message="test",
            response=MagicMock(status_code=429, headers={}),
            body="AllocationQuota.FreeTierOnly",
        )
        assert _is_free_tier_exhausted(exc)
