"""Provider factory — resolves provider names to instances."""

from __future__ import annotations

import importlib
import os
from typing import Any

from n3rverberage.config import DEFAULTS
from n3rverberage.providers.base import ModelProvider
from n3rverberage.providers.fallback import FallbackProvider
from n3rverberage.providers.tts import TTSProvider
from n3rverberage.providers.tts_fallback import TTSFallbackProvider

# Registry: name → fully-qualified class path
_PROVIDER_REGISTRY: dict[str, str] = {
    "qwen": "n3rverberage.providers.qwen.QwenProvider",
    "openai": "n3rverberage.providers.openai.OpenAIProvider",
    "local": "n3rverberage.providers.local.LocalProvider",
    "fallback": "n3rverberage.providers.fallback.FallbackProvider",
}


def list_providers() -> list[str]:
    """Return the list of registered provider names (excluding fallback)."""
    return [name for name in _PROVIDER_REGISTRY if name != "fallback"]


def get_provider(name: str | None = None) -> ModelProvider:
    """Resolve a provider name to an instance.

    The name format is ``<provider_name>[:<model_override>]``.
    If ``name`` is ``None``, the ``N3RVERBERAGE_PROVIDER`` env var is read,
    defaulting to ``"qwen"``.

    =====================  ================================================
    Input                  Result
    =====================  ================================================
    ``None``               Read ``N3RVERBERAGE_PROVIDER`` env, default ``"qwen"``
    ``"qwen"``             ``QwenProvider()`` with env defaults
    ``"qwen:model-id"``    ``QwenProvider(model="model-id")``
    ``"fallback"``         Parse ``N3RVERBERAGE_FALLBACK_PROVIDERS`` env
    ``"fallback:anything"``  ``ValueError`` — fallback doesn't accept model
    ``"a:b:c"``            ``ValueError`` — too many parts
    ``"nonexistent"``      ``ValueError`` — unknown provider
    =====================  ================================================
    """
    resolved_name = (name or os.environ.get("N3RVERBERAGE_PROVIDER") or DEFAULTS.provider).strip().lower()

    # Parse colon-separated parts
    parts = resolved_name.split(":")
    if len(parts) > 2:
        raise ValueError(f"Invalid provider name: '{resolved_name}'. Format: <provider> or <provider>:<model>")

    provider_name = parts[0]
    model_override = parts[1] if len(parts) == 2 else None

    # Validate provider exists
    if provider_name not in _PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: '{provider_name}'. Available: {', '.join(list_providers())}")

    # Fallback is special: it doesn't accept model override
    if provider_name == "fallback":
        if model_override is not None:
            raise ValueError(
                "Fallback provider does not accept a model override. "
                "Configure individual entries in N3RVERBERAGE_FALLBACK_PROVIDERS."
            )
        return _build_fallback()

    # Resolve provider class and instantiate
    return _build_provider(provider_name, model_override)


def _build_provider(provider_name: str, model_override: str | None) -> ModelProvider:
    """Import and instantiate a provider by registry name."""
    class_path = _PROVIDER_REGISTRY[provider_name]
    module_path, class_name = class_path.rsplit(".", 1)

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)

    kwargs: dict[str, Any] = {}
    if model_override:
        kwargs["model"] = model_override

    return cls(**kwargs)


def _build_fallback() -> FallbackProvider:
    """Build a FallbackProvider from N3RVERBERAGE_FALLBACK_PROVIDERS env var."""
    raw = os.environ.get("N3RVERBERAGE_FALLBACK_PROVIDERS")
    if not raw or not raw.strip():
        raise ValueError(
            "N3RVERBERAGE_FALLBACK_PROVIDERS is not set. Set it to a comma-separated list of provider names."
        )
    entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
    providers = [get_provider(entry) for entry in entries]
    return FallbackProvider(providers)


def get_tts_provider(
    *,
    model: str | None = None,
    base_url: str | None = None,
    voice: str | None = None,
) -> TTSProvider | TTSFallbackProvider:
    """Build a TTS provider from environment defaults.

    Returns a single :class:`TTSProvider` by default. If the
    ``N3RVERBERAGE_TTS_FALLBACK_MODELS`` environment variable is set, returns
    a :class:`TTSFallbackProvider` that chains multiple TTS models.

    The fallback list is a comma-separated list of model IDs::

        N3RVERBERAGE_TTS_FALLBACK_MODELS=qwen3-tts-flash,qwen3-tts-instruct-flash

    The first model in the list is the primary. Each subsequent model is a
    fallback when the prior one's quota is exhausted.

    Resolves the API key from ``DASHSCOPE_API_KEY`` and model/voice/URL
    from their respective environment variables or default values.
    """
    fallback_models = os.environ.get("N3RVERBERAGE_TTS_FALLBACK_MODELS", "").strip()

    if fallback_models:
        model_ids = [m.strip() for m in fallback_models.split(",") if m.strip()]
        if not model_ids:
            raise ValueError(
                "N3RVERBERAGE_TTS_FALLBACK_MODELS is set but empty. Set it to a comma-separated list of TTS model IDs."
            )
        providers = [
            TTSProvider(
                model=mid,
                base_url=base_url,
                voice=voice,
            )
            for mid in model_ids
        ]
        return TTSFallbackProvider(providers)

    return TTSProvider(
        model=model,
        base_url=base_url,
        voice=voice,
    )
