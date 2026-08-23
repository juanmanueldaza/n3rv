"""Data models for n3rverberage.providers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """A function call requested by the model."""

    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result of a completion with optional tool calls."""

    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ProviderError(RuntimeError):
    """Generic provider error during a completion call."""

    def __init__(
        self,
        model_id: str,
        status_code: int,
        body: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.status_code = status_code
        self.body = body
        super().__init__(f"[{model_id}] HTTP {status_code}: {body or 'unknown error'}")

    def __reduce__(self) -> tuple:
        return (type(self), (self.model_id, self.status_code, self.body))


class QuotaExhaustedError(ProviderError):
    """Quota exhausted for a model (429 + FreeTierOnly)."""


class AllProvidersExhaustedError(Exception):
    """All providers in a fallback chain were exhausted."""

    def __init__(self, exhausted_model_ids: list[str]) -> None:
        self.exhausted_model_ids = exhausted_model_ids
        models = ", ".join(exhausted_model_ids)
        super().__init__(f"All providers exhausted: {models}")


class AllTTSProvidersExhaustedError(Exception):
    """All TTS providers in a fallback chain were exhausted."""

    def __init__(self, exhausted_model_ids: list[str]) -> None:
        self.exhausted_model_ids = exhausted_model_ids
        models = ", ".join(exhausted_model_ids)
        super().__init__(f"All TTS providers exhausted: {models}")
