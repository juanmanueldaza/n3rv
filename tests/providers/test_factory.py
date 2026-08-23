"""Tests for factory.py — get_provider, list_providers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from n3rverberage.providers.base import ModelProvider
from n3rverberage.providers.factory import get_provider, list_providers
from n3rverberage.providers.fallback import FallbackProvider


class TestListProviders:
    def test_returns_list(self) -> None:
        providers = list_providers()
        assert isinstance(providers, list)
        assert "qwen" in providers
        assert "openai" in providers
        assert "local" in providers
        assert "fallback" not in providers

    def test_all_strings(self) -> None:
        assert all(isinstance(p, str) for p in list_providers())


class TestGetProvider:
    def test_default_is_qwen(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", {"DASHSCOPE_API_KEY": "k"}):
            p = get_provider()
            assert isinstance(p, ModelProvider)
            assert p.model == "qwen3-coder-plus"

    def test_env_var_default(self) -> None:
        with (
            patch("openai.OpenAI"),
            patch.dict("os.environ", {"N3RVERBERAGE_PROVIDER": "openai", "OPENAI_API_KEY": "k"}),
        ):
            p = get_provider()
            assert p.model == "gpt-4"

    def test_explicit_name(self) -> None:
        with (
            patch("openai.OpenAI"),
            patch.dict("os.environ", {"N3RVERBERAGE_PROVIDER": "openai", "DASHSCOPE_API_KEY": "k"}),
        ):
            p = get_provider("qwen")
            assert isinstance(p, ModelProvider)
            assert p.model == "qwen3-coder-plus"

    def test_model_override_colon(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", {"DASHSCOPE_API_KEY": "k"}):
            p = get_provider("qwen:qwen3.7-plus")
            assert p.model == "qwen3.7-plus"

    def test_openai_with_model(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", {"OPENAI_API_KEY": "k"}):
            p = get_provider("openai:gpt-4-turbo")
            assert p.model == "gpt-4-turbo"

    def test_case_insensitive(self) -> None:
        with patch("openai.OpenAI"), patch.dict("os.environ", {"DASHSCOPE_API_KEY": "k"}):
            p = get_provider("QWEN")
            assert p.model == "qwen3-coder-plus"

    def test_unknown_provider(self) -> None:
        with patch.dict("os.environ", clear=True):
            with pytest.raises(ValueError, match="Unknown provider"):
                get_provider("nonexistent")

    def test_too_many_parts(self) -> None:
        with pytest.raises(ValueError, match="Invalid provider"):
            get_provider("a:b:c")

    def test_fallback_rejects_model_override(self) -> None:
        with pytest.raises(ValueError, match="does not accept"):
            get_provider("fallback:anything")

    def test_local_constructs_successfully(self) -> None:
        with patch("openai.OpenAI"):
            p = get_provider("local")
            assert p.model == "qwen2.5"
            assert "127.0.0.1" in p.base_url


class TestGetProviderFallback:
    def test_fallback_from_env(self) -> None:
        with (
            patch("openai.OpenAI"),
            patch.dict(
                "os.environ",
                {
                    "N3RVERBERAGE_FALLBACK_PROVIDERS": "qwen,local",
                    "DASHSCOPE_API_KEY": "k",
                },
            ),
        ):
            p = get_provider("fallback")
            assert isinstance(p, FallbackProvider)

    def test_fallback_env_missing(self) -> None:
        with patch.dict("os.environ", clear=True):
            with pytest.raises(ValueError, match="N3RVERBERAGE_FALLBACK_PROVIDERS"):
                get_provider("fallback")

    def test_fallback_env_mixed_model_overrides(self) -> None:
        with (
            patch("openai.OpenAI"),
            patch.dict(
                "os.environ",
                {
                    "N3RVERBERAGE_FALLBACK_PROVIDERS": "qwen:model-a,qwen:model-b",
                    "DASHSCOPE_API_KEY": "k",
                },
            ),
        ):
            p = get_provider("fallback")
            assert isinstance(p, FallbackProvider)
            assert p._providers[0].model == "model-a"
            assert p._providers[1].model == "model-b"

    def test_fallback_single_provider(self) -> None:
        with (
            patch("openai.OpenAI"),
            patch.dict(
                "os.environ",
                {
                    "N3RVERBERAGE_FALLBACK_PROVIDERS": "qwen",
                    "DASHSCOPE_API_KEY": "k",
                },
            ),
        ):
            p = get_provider("fallback")
            assert isinstance(p, FallbackProvider)
            assert len(p._providers) == 1
            assert p._providers[0].model == "qwen3-coder-plus"
