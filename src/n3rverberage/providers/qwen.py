"""Qwen (DashScope) provider implementation."""

from __future__ import annotations

import json
import os
from typing import Any

import openai
from pydantic import BaseModel

from n3rverberage.config import DEFAULTS
from n3rverberage.providers.base import ModelProvider
from n3rverberage.providers.models import (
    ProviderError,
    QuotaExhaustedError,
    ToolCall,
    ToolResult,
)

# NOTE: dashscope-intl.aliyuncs.com is deprecated but still works.
# Alibaba recommends migrating to:
#   https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
# Set via N3RVERBERAGE_QWEN_BASE_URL env var or the base_url constructor arg.
#
# IPv6: dashscope-intl.aliyuncs.com has NO AAAA records.
# IPv6-only environments must use the workspace-specific domain or an IPv4 proxy.
_TIMEOUT_SEC = 60.0
_MAX_TOKENS = 4096
_BASE_URL_ENV_VAR = "N3RVERBERAGE_QWEN_BASE_URL"


class QwenProvider(ModelProvider):
    """Provider for Alibaba Cloud DashScope (Qwen) API.

    Detects free-tier quota exhaustion (HTTP 429 + ``AllocationQuota.FreeTierOnly``)
    and raises :class:`QuotaExhaustedError` for automatic fallback handling.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(api_key, model, base_url)
        resolved_key = self._api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "DASHSCOPE_API_KEY is not set. Provide api_key or set the DASHSCOPE_API_KEY environment variable."
            )
        self._client = openai.OpenAI(
            api_key=resolved_key,
            base_url=self.base_url,
            timeout=_TIMEOUT_SEC,
        )
        self._last_quota_remaining: int | None = None

    def _default_model(self) -> str:
        return os.environ.get("N3RVERBERAGE_DEFAULT_MODEL") or DEFAULTS.model

    def _default_base_url(self) -> str:
        return os.environ.get(_BASE_URL_ENV_VAR) or os.environ.get("N3RVERBERAGE_DEFAULT_BASE_URL") or DEFAULTS.base_url

    @property
    def last_quota_remaining(self) -> int | None:
        """``x-qwen-quota-remaining`` from the most successful API call."""
        return self._last_quota_remaining

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
            self._raise_quota_or_forward(exc)
            raise  # unreachable, keep linters happy
        self._capture_quota(response)
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
            self._raise_quota_or_forward(exc)
            raise
        self._capture_quota(response)
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
            self._raise_quota_or_forward(exc)
            raise
        self._capture_quota(response)
        message = response.choices[0].message
        content = message.content or ""

        if not message.tool_calls:
            return ToolResult(content=content)

        tcs = []
        for tc in message.tool_calls:
            args = _safe_parse_args(tc.function.arguments)
            tcs.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return ToolResult(content=content, tool_calls=tcs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _capture_quota(self, response: Any) -> None:
        """Extract ``x-qwen-quota-remaining`` header if present."""
        try:
            value = response.headers.get("x-qwen-quota-remaining")
            if value is not None:
                self._last_quota_remaining = int(value)
        except (AttributeError, ValueError, TypeError):
            pass

    def _raise_quota_or_forward(self, exc: openai.APIStatusError) -> None:
        """Raise :class:`QuotaExhaustedError` for free-tier 429, else re-raise."""
        if exc.status_code == 429 and _is_free_tier_exhausted(exc):
            raise QuotaExhaustedError(self.model, 429, str(exc.body)) from exc
        body_str = str(exc.body) if exc.body else None
        raise ProviderError(self.model, exc.status_code, body_str) from exc


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _safe_parse_args(raw: str | None) -> dict[str, Any]:
    """Parse JSON tool-call arguments, defaulting to ``{}`` on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _is_free_tier_exhausted(exc: openai.APIStatusError) -> bool:
    """Check whether a 429 is due to ``AllocationQuota.FreeTierOnly``."""
    body = exc.body
    body_str = json.dumps(body) if isinstance(body, dict) else str(body or "")
    return "AllocationQuota.FreeTierOnly" in body_str
