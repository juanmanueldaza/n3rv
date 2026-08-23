"""Text-to-speech provider for Qwen-TTS (CosyVoice) models via HTTP API.

Uses the ``services/aigc/multimodal-generation/generation`` endpoint
(Qwen-TTS non-realtime speech synthesis). Returns complete audio bytes.

The old ``services/audio/tts/SpeechSynthesizer`` endpoint (CosyVoice legacy)
is NOT available for ``sk-ws-*`` workspace API keys — those keys only work
with the ``services/aigc/multimodal-generation/generation`` endpoint.

Supported models (Singapore):
- ``qwen3-tts-flash`` — English/Chinese TTS, 15+ system voices (default)
- ``qwen3-tts-instruct-flash`` — instruction-controlled speech

Voices: Cherry (default), Serena, Ethan, Chelsie, Vivian, Moon, Bella,
Jennifer, Ryan, Katerina, Aiden, and many more. See the Qwen-TTS voice list
for the complete catalog.

``cosyvoice-*`` models use a WebSocket protocol — not this provider.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

# NOTE: dashscope-intl.aliyuncs.com is deprecated but still works.
# Alibaba recommends migrating to:
#   https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1
# Set via N3RVERBERAGE_TTS_BASE_URL env var or the base_url constructor arg.
#
# IPv6: dashscope-intl.aliyuncs.com has NO AAAA records.
# IPv6-only environments must use the workspace-specific domain or an IPv4 proxy.
_DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/api/v1"
_DEFAULT_MODEL = "qwen3-tts-flash"
_DEFAULT_VOICE = "Cherry"
_TTS_TIMEOUT_SEC = 60.0


class TTSProvider:
    """Non-realtime text-to-speech via Qwen-TTS HTTP API.

    Wraps the ``POST /api/v1/services/aigc/multimodal-generation/generation``
    endpoint. Returns complete audio bytes (non-streaming).

    Parameters
    ----------
    api_key:
        DashScope API key. Falls back to ``DASHSCOPE_API_KEY`` env var.
    model:
        Qwen-TTS model ID. Default: ``qwen3-tts-flash``.
    base_url:
        API base URL. Falls back to ``N3RVERBERAGE_TTS_BASE_URL`` env var,
        then ``N3RVERBERAGE_BASE_URL`` env var,
        then ``https://dashscope-intl.aliyuncs.com/api/v1``.
    voice:
        Default voice. Falls back to ``N3RVERBERAGE_TTS_VOICE`` env var,
        then ``Cherry``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        voice: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self._api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY is not set. Provide api_key or set the DASHSCOPE_API_KEY environment variable."
            )

        self.model = model or _DEFAULT_MODEL
        # Resolve base_url: explicit > TTS env > general provider env > default
        self.base_url = (
            base_url
            or os.environ.get("N3RVERBERAGE_TTS_BASE_URL")
            or os.environ.get("N3RVERBERAGE_BASE_URL")
            or _DEFAULT_BASE_URL
        )
        self.voice = voice or os.environ.get("N3RVERBERAGE_TTS_VOICE") or _DEFAULT_VOICE
        self._client = httpx.Client(timeout=_TTS_TIMEOUT_SEC)

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
        """Convert text to speech audio.

        Parameters
        ----------
        text:
            Text to synthesize. Maximum 512 tokens.
        voice:
            Voice override. Uses instance default if omitted.
            See the Qwen-TTS voice list for available voices.
        language_type:
            Language hint. One of ``Auto`` (default), ``Chinese``, ``English``,
            ``German``, ``Italian``, ``Portuguese``, ``Spanish``, ``Japanese``,
            ``Korean``, ``French``, ``Russian``.

        Returns
        -------
        bytes
            Complete WAV audio data.

        Raises
        ------
        ValueError
            Invalid parameters.
        TTSProviderError
            API error or quota exhaustion.
        """
        if not text or not text.strip():
            raise ValueError("Text to synthesize must not be empty")

        payload = self._build_payload(
            text=text.strip(),
            voice=voice or self.voice,
            language_type=language_type,
            **kwargs,
        )

        endpoint = f"{self.base_url}/services/aigc/multimodal-generation/generation"

        try:
            response = self._client.post(
                url=endpoint,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.TimeoutException:
            raise TTSProviderError(
                model=self.model,
                message="TTS request timed out",
            ) from None
        except httpx.RequestError as exc:
            raise TTSProviderError(
                model=self.model,
                message=f"TTS request failed: {exc}",
            ) from exc

        if response.status_code == 429:
            body = response.text
            if "AllocationQuota.FreeTierOnly" in body:
                raise TTSQuotaExhaustedError(self.model)
            raise TTSProviderError(
                model=self.model,
                status_code=429,
                message=f"Rate limited: {body}",
            )

        if response.status_code == 401:
            raise TTSProviderError(
                model=self.model,
                status_code=401,
                message="Invalid API key",
            )

        if response.status_code != 200:
            raise TTSProviderError(
                model=self.model,
                status_code=response.status_code,
                message=response.text,
            )

        # Non-streaming response: JSON with audio URL
        try:
            resp_data = response.json()
        except json.JSONDecodeError as exc:
            raise TTSProviderError(
                model=self.model,
                message=f"Invalid JSON response: {exc}",
            ) from exc

        audio_info = resp_data.get("output", {}).get("audio", {})
        audio_url = audio_info.get("url", "")

        if not audio_url:
            # Check for error in response
            code = resp_data.get("code", "")
            msg = resp_data.get("message", "")
            if code or msg:
                raise TTSProviderError(
                    model=self.model,
                    status_code=response.status_code,
                    message=f"{code}: {msg}" if code else msg,
                )
            raise TTSProviderError(
                model=self.model,
                message="No audio URL in response",
            )

        # Download the audio from the returned URL
        try:
            audio_resp = self._client.get(audio_url)
        except httpx.RequestError as exc:
            raise TTSProviderError(
                model=self.model,
                message=f"Failed to download audio: {exc}",
            ) from exc

        if audio_resp.status_code != 200:
            raise TTSProviderError(
                model=self.model,
                status_code=audio_resp.status_code,
                message=f"Failed to download audio from {audio_url}",
            )

        return audio_resp.content

    def _build_payload(
        self,
        text: str,
        voice: str,
        language_type: str | None = None,
        **kwargs: Any,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": {
                "text": text,
                "voice": voice,
            },
        }

        if language_type:
            payload["input"]["language_type"] = language_type

        # Extract reserved kwargs
        input_overrides = kwargs.pop("input", None)
        model_override = kwargs.pop("model", None)

        # Any remaining kwargs go into input (arbitrary API metadata)
        if kwargs:
            payload["input"].update(kwargs)

        # Top-level overrides
        if input_overrides:
            payload["input"].update(input_overrides)
        if model_override:
            payload["model"] = model_override

        return payload


class TTSProviderError(Exception):
    """Error during TTS synthesis."""

    def __init__(
        self,
        model: str,
        status_code: int = 0,
        message: str = "unknown error",
    ) -> None:
        self.model = model
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{model}] {message}")


class TTSQuotaExhaustedError(TTSProviderError):
    """Free-tier quota exhausted for TTS model."""

    def __init__(self, model: str) -> None:
        super().__init__(
            model=model,
            status_code=429,
            message="Free-tier quota exhausted for TTS model",
        )
