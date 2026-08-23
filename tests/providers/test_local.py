"""Tests for LocalProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from conftest import make_mock_response

from n3rverberage.providers.local import LocalProvider


@pytest.fixture
def provider(mock_openai_client: MagicMock) -> LocalProvider:
    return LocalProvider()


@pytest.fixture
def mock_create(mock_openai_client: MagicMock) -> MagicMock:
    return mock_openai_client.chat.completions.create


class TestConstructor:
    def test_defaults(self) -> None:
        with patch("openai.OpenAI"):
            p = LocalProvider()
        assert p.model == "qwen2.5"
        assert p.base_url == "http://127.0.0.1:11434/v1"

    def test_explicit_base_url(self) -> None:
        with patch("openai.OpenAI"):
            p = LocalProvider(base_url="http://localhost:8080/v1")
        assert p.base_url == "http://localhost:8080/v1"

    def test_explicit_model(self) -> None:
        with patch("openai.OpenAI"):
            p = LocalProvider(model="llama3")
        assert p.model == "llama3"

    def test_no_auth_required(self) -> None:
        """LocalProvider does not require an API key."""
        with patch("openai.OpenAI"):
            p = LocalProvider()
        assert p._api_key is None


class TestComplete:
    def test_basic(self, provider: LocalProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="Local response")
        result = provider.complete([{"role": "user", "content": "Hi"}])
        assert result == "Local response"

    def test_sends_correct_payload(self, provider: LocalProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response()
        provider.complete([{"role": "user", "content": "Hi"}], temperature=0.7)
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["model"] == "qwen2.5"
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hi"}]
        assert call_kwargs["temperature"] == 0.7


class TestCompleteStructured:
    def test_basic(self, provider: LocalProvider, mock_create: MagicMock) -> None:
        from pydantic import BaseModel

        class Person(BaseModel):
            name: str

        mock_create.return_value = make_mock_response(content='{"name": "Local"}')
        result = provider.complete_structured([{"role": "user", "content": "Extract"}], Person)
        assert isinstance(result, Person)
        assert result.name == "Local"


class TestCompleteWithTools:
    def test_basic(self, provider: LocalProvider, mock_create: MagicMock) -> None:
        mock_create.return_value = make_mock_response(content="Local response with tools")
        result = provider.complete_with_tools(
            [{"role": "user", "content": "Hi"}],
            [{"type": "function", "function": {"name": "f"}}],
        )
        assert result.content == "Local response with tools"
        assert result.tool_calls == []
