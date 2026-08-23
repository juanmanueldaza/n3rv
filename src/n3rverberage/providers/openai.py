"""OpenAI provider implementation."""

from __future__ import annotations

import json
import os
from typing import Any

import openai
from pydantic import BaseModel

from n3rverberage.providers.base import ModelProvider
from n3rverberage.providers.models import ProviderError, ToolCall, ToolResult

_MAX_TOKENS = 4096


class OpenAIProvider(ModelProvider):
    """Provider for the standard OpenAI API.

    No quota-detection logic. Every API error is raised as a generic
    :class:`ProviderError`.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key, model, base_url)
        resolved_key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Provide api_key or set the OPENAI_API_KEY environment variable."
            )
        self._client = openai.OpenAI(
            api_key=resolved_key,
            base_url=self.base_url,
            timeout=60.0,
        )

    def _default_model(self) -> str:
        return os.environ.get("N3RVERBERAGE_DEFAULT_MODEL") or "gpt-4"

    def _default_base_url(self) -> str:
        return os.environ.get("N3RVERBERAGE_DEFAULT_BASE_URL") or "https://api.openai.com/v1"

    def complete(self, messages: list[dict], **kwargs: Any) -> str:
        max_tokens = kwargs.pop("max_tokens", _MAX_TOKENS)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                **kwargs,
            )
        except openai.APIStatusError as exc:
            raise ProviderError(self.model, exc.status_code, str(exc.body)) from exc
        return response.choices[0].message.content or ""

    def complete_structured(
        self,
        messages: list[dict],
        output_type: type[BaseModel],
        **kwargs: Any,
    ) -> BaseModel:
        schema = output_type.model_json_schema()
        response_format: dict[str, Any] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.get("title", output_type.__name__),
                "schema": schema,
                "strict": True,
            },
        }
        max_tokens = kwargs.pop("max_tokens", _MAX_TOKENS)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                max_tokens=max_tokens,
                **kwargs,
            )
        except openai.APIStatusError as exc:
            raise ProviderError(self.model, exc.status_code, str(exc.body)) from exc
        raw = response.choices[0].message.content
        if not raw:
            raise ProviderError(self.model, 200, "Empty structured response")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(self.model, 200, f"Invalid JSON: {exc}") from exc
        try:
            return output_type.model_validate(parsed)
        except Exception as exc:
            raise ProviderError(self.model, 200, f"Validation failed: {exc}") from exc

    def complete_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        **kwargs: Any,
    ) -> ToolResult:
        max_tokens = kwargs.pop("max_tokens", _MAX_TOKENS)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=max_tokens,
                **kwargs,
            )
        except openai.APIStatusError as exc:
            raise ProviderError(self.model, exc.status_code, str(exc.body)) from exc
        message = response.choices[0].message
        content = message.content or ""

        if not message.tool_calls:
            return ToolResult(content=content)

        tcs = []
        for tc in message.tool_calls:
            args = _safe_parse_args(tc.function.arguments)
            tcs.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return ToolResult(content=content, tool_calls=tcs)


def _safe_parse_args(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
