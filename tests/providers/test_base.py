"""Tests for base.py — ABC enforcement."""

from __future__ import annotations

import pytest

from n3rverberage.providers.base import ModelProvider


def test_abc_cannot_instantiate_directly() -> None:
    """Must subclass and implement all abstract methods."""
    with pytest.raises(TypeError):
        ModelProvider()  # type: ignore[abstract]


def test_partial_implementation_fails() -> None:
    """Subclass missing abstract methods cannot be instantiated."""

    class PartialProvider(ModelProvider):
        def _default_model(self) -> str:
            return "test"

        def _default_base_url(self) -> str:
            return "http://test"

    with pytest.raises(TypeError):
        PartialProvider()  # type: ignore[abstract]


def test_full_implementation_succeeds() -> None:
    """Subclass implementing all 5 abstract methods can be instantiated."""

    class FullProvider(ModelProvider):
        def _default_model(self) -> str:
            return "test"

        def _default_base_url(self) -> str:
            return "http://test"

        def complete(self, messages, **kwargs):
            return "ok"

        def complete_structured(self, messages, output_type, **kwargs):
            return output_type()

        def complete_with_tools(self, messages, tools, **kwargs):
            from n3rverberage.providers.models import ToolResult

            return ToolResult(content="ok")

    provider = FullProvider()
    assert provider.model == "test"
    assert provider.base_url == "http://test"
    assert provider.complete([]) == "ok"


def test_constructor_defaults() -> None:
    """Constructor uses _default_model() / _default_base_url() if None given."""

    class MyProvider(ModelProvider):
        def _default_model(self) -> str:
            return "my-model"

        def _default_base_url(self) -> str:
            return "http://my-url"

        def complete(self, messages, **kwargs):
            return "ok"

        def complete_structured(self, messages, output_type, **kwargs):
            return output_type()

        def complete_with_tools(self, messages, tools, **kwargs):
            from n3rverberage.providers.models import ToolResult

            return ToolResult(content="ok")

    p = MyProvider()
    assert p.model == "my-model"
    assert p.base_url == "http://my-url"

    p2 = MyProvider(model="override", base_url="http://other")
    assert p2.model == "override"
    assert p2.base_url == "http://other"
