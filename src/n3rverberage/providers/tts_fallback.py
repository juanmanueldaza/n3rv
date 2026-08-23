"""TTS fallback provider — chains TTSProvider instances on quota exhaustion."""

from __future__ import annotations

import sys
from typing import Any

from n3rverberage.providers.models import AllTTSProvidersExhaustedError
from n3rverberage.providers.tts import TTSProvider, TTSQuotaExhaustedError


class TTSFallbackProvider:
    """Provider that chains multiple TTS providers, falling back on quota exhaustion.

    Only :class:`TTSQuotaExhaustedError` triggers the next provider.
    All other errors propagate immediately.

    Parameters
    ----------
    providers:
        Ordered list of TTS providers to try. At least one is required.
    """

    def __init__(self, providers: list[TTSProvider]) -> None:
        if not providers:
            raise ValueError("At least one TTS provider is required")
        self._providers = providers

    @property
    def model(self) -> str:
        return self._providers[0].model if self._providers else "unknown"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        language_type: str | None = None,
        **kwargs: Any,
    ) -> bytes:
        """Convert text to speech, falling back on quota exhaustion.

        Parameters
        ----------
        text:
            Text to synthesize.
        voice:
            Voice override.
        language_type:
            Language hint.

        Returns
        -------
        bytes
            Complete WAV audio data from the first provider that succeeds.

        Raises
        ------
        AllTTSProvidersExhaustedError
            All providers exhausted quota.
        TTSProviderError
            Non-quota error from any provider (propagated immediately).
        """
        exhausted: list[str] = []
        for provider in self._providers:
            try:
                return provider.synthesize(
                    text,
                    voice=voice,
                    language_type=language_type,
                    **kwargs,
                )
            except TTSQuotaExhaustedError as exc:
                exhausted.append(exc.model)
                _log_fallback(exc.model)
        raise AllTTSProvidersExhaustedError(exhausted)


def _log_fallback(model_id: str) -> None:
    """Log fallback message to stderr."""
    print(f"[tts-fallback] {model_id} exhausted, trying next.", file=sys.stderr)
