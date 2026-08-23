"""Tests for OpenAIProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from conftest import make_mock_response

from n3rverberage.providers.models import ProviderError
from n3rverberage.providers.openai import OpenAIProvider


@pytest.fixture
def provider(mock_openai_client: MagicMock) -> OpenAIProvider:
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        return OpenAIProvider()


@pytest.fixture
def mock_create(mock_openai_client: MagicMock) -> MagicMock:
    return mock_openai_client.chat.completions.create


class TestConstructor:
    def test_from_env(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}):
            p = OpenAIProvider()
        assert p.model == "gpt-4"

    def test_explicit_args(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}):
            p = OpenAIProvider(
                api_key="sk-custom",
                model="gpt-4-turbo",
                base_url="http://custom/v1",
            )
        assert p.model == "gpt-4-turbo"
        assert p.base_url == "http://custom/v1"

    def test_missing_api_key(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIProvider()


class TestComplete:
    def test_basic(self, provider: OpenAIProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="Hello from OpenAI")
        result = provider.complete([{"role": "user", "content": "Hi"}])
        assert result == "Hello from OpenAI"

    def test_sends_correct_payload(self, provider: OpenAIProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response()
        provider.complete([{"role": "user", "content": "Hi"}], temperature=0.5)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "gpt-4"
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]
        assert call_kwargs["temperature"] == 0.5


class TestCompleteStructured:
    def test_basic(self, provider: OpenAIProvider, mock_create: MagicMock) -> None:
        from pydantic import BaseModel

        class Person(BaseModel):
            name: str
            age: int

        mock_create.return_value = make_mock_response(content='{"name": "Bob", "age": 25}')
        result = provider.complete_structured([{"role": "user", "content": "Extract"}], Person)
        assert isinstance(result, Person)
        assert result.name == "Bob"


class TestCompleteWithTools:
    def test_basic(self, provider: OpenAIProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="No tools needed")
        result = provider.complete_with_tools(
            [{"role": "user", "content": "Hi"}],
            [{"type": "function", "function": {"name": "f"}}],
        )
        assert result.content == "No tools needed"
        assert result.tool_calls == []


class TestErrors:
    def test_api_error_becomes_provider_error(self, provider: OpenAIProvider, mock_create: MagicMock) -> None:
        import httpx
        from openai import APIStatusError

        response = MagicMock(spec=httpx.Response)
        response.status_code = 500
        response.headers = {}
        mock_create.side_effect = APIStatusError(
            message="Server error",
            response=response,
            body={"error": "internal"},
        )
        with pytest.raises(ProviderError) as exc:
            provider.complete([{"role": "user", "content": "Hi"}])
        assert exc.value.status_code == 500
