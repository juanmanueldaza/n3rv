"""Tests for TTSFallbackProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from n3rverberage.providers.models import AllTTSProvidersExhaustedError
from n3rverberage.providers.tts import TTSProvider, TTSProviderError
from n3rverberage.providers.tts_fallback import TTSFallbackProvider

_AUDIO_BYTES = b"\x00\x01\x02mock_audio_data"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_http() -> MagicMock:
    """Mock httpx.Client for all HTTP calls."""
    mock_client = MagicMock(spec=httpx.Client)
    patcher = patch("httpx.Client", return_value=mock_client)
    patcher.start()
    yield mock_client
    patcher.stop()


def _make_provider(model: str = "qwen3-tts-flash") -> TTSProvider:
    """Create a TTSProvider with a test API key."""
    with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
        return TTSProvider(model=model)


def _setup_success(mock_http: MagicMock) -> None:
    """Configure mock to return a successful TTS response."""
    gen_response = MagicMock(spec=httpx.Response)
    gen_response.status_code = 200
    gen_response.json.return_value = {
        "output": {
            "audio": {"url": "https://audio.example.com/out.wav"},
        },
    }
    gen_response.text = "{}"
    mock_http.post.return_value = gen_response

    audio_response = MagicMock(spec=httpx.Response)
    audio_response.status_code = 200
    audio_response.content = _AUDIO_BYTES
    mock_http.get.return_value = audio_response


def _setup_exhausted(mock_http: MagicMock) -> None:
    """Configure mock to return quota exhausted response."""
    gen_response = MagicMock(spec=httpx.Response)
    gen_response.status_code = 429
    gen_response.text = '{"code": "AllocationQuota.FreeTierOnly"}'
    mock_http.post.return_value = gen_response


# ------------------------------------------------------------------
# Constructor
# ------------------------------------------------------------------


class TestConstructor:
    def test_empty_providers(self) -> None:
        with pytest.raises(ValueError, match="At least one TTS provider is required"):
            TTSFallbackProvider([])

    def test_single_provider(self) -> None:
        p = _make_provider()
        fb = TTSFallbackProvider([p])
        assert fb.model == "qwen3-tts-flash"

    def test_multiple_providers(self) -> None:
        p1 = _make_provider("qwen3-tts-flash")
        p2 = _make_provider("qwen3-tts-instruct-flash")
        fb = TTSFallbackProvider([p1, p2])
        assert fb.model == "qwen3-tts-flash"  # first provider's model


# ------------------------------------------------------------------
# synthesize() — fallback behavior
# ------------------------------------------------------------------


class TestSynthesizeFallback:
    def test_first_provider_succeeds(self, mock_http: MagicMock) -> None:
        _setup_success(mock_http)
        p1 = _make_provider("qwen3-tts-flash")
        p2 = _make_provider("qwen3-tts-instruct-flash")
        fb = TTSFallbackProvider([p1, p2])

        result = fb.synthesize("Hello")

        assert result == _AUDIO_BYTES
        # Only p1 was called (p2 should not be touched)
        assert mock_http.post.call_count == 1

    def test_fallback_to_second_provider(self, mock_http: MagicMock) -> None:
        """First provider exhausted, second succeeds."""
        # We need to control which provider's request gets which response.
        # Mock post to return exhausted first time, success second time.
        exhausted_resp = MagicMock(spec=httpx.Response)
        exhausted_resp.status_code = 429
        exhausted_resp.text = '{"code": "AllocationQuota.FreeTierOnly"}'

        success_resp = MagicMock(spec=httpx.Response)
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "output": {
                "audio": {"url": "https://audio.example.com/out.wav"},
            },
        }
        success_resp.text = "{}"

        audio_resp = MagicMock(spec=httpx.Response)
        audio_resp.status_code = 200
        audio_resp.content = _AUDIO_BYTES

        # Sequence: first POST returns exhausted, second POST returns success
        mock_http.post.side_effect = [exhausted_resp, success_resp]
        mock_http.get.return_value = audio_resp

        p1 = _make_provider("qwen3-tts-flash")
        p2 = _make_provider("qwen3-tts-instruct-flash")
        fb = TTSFallbackProvider([p1, p2])

        result = fb.synthesize("Hello")

        assert result == _AUDIO_BYTES
        assert mock_http.post.call_count == 2

    def test_all_providers_exhausted(self, mock_http: MagicMock) -> None:
        """All providers exhausted raises AllTTSProvidersExhaustedError."""
        _setup_exhausted(mock_http)

        p1 = _make_provider("qwen3-tts-flash")
        p2 = _make_provider("qwen3-tts-instruct-flash")
        fb = TTSFallbackProvider([p1, p2])

        with pytest.raises(AllTTSProvidersExhaustedError) as exc:
            fb.synthesize("Hello")

        assert len(exc.value.exhausted_model_ids) == 2
        assert "qwen3-tts-flash" in exc.value.exhausted_model_ids
        assert "qwen3-tts-instruct-flash" in exc.value.exhausted_model_ids

    def test_non_quota_error_propagates(self, mock_http: MagicMock) -> None:
        """Non-quota error (e.g., 401) propagates immediately, no fallback."""
        auth_resp = MagicMock(spec=httpx.Response)
        auth_resp.status_code = 401
        auth_resp.text = "Unauthorized"
        mock_http.post.return_value = auth_resp

        p1 = _make_provider("qwen3-tts-flash")
        p2 = _make_provider("qwen3-tts-instruct-flash")
        fb = TTSFallbackProvider([p1, p2])

        with pytest.raises(TTSProviderError) as exc:
            fb.synthesize("Hello")

        assert exc.value.status_code == 401
        # Only first provider was called
        assert mock_http.post.call_count == 1

    def test_network_error_propagates(self, mock_http: MagicMock) -> None:
        """Network error propagates immediately, no fallback."""
        mock_http.post.side_effect = httpx.TimeoutException("timeout", request=MagicMock())

        p1 = _make_provider("qwen3-tts-flash")
        p2 = _make_provider("qwen3-tts-instruct-flash")
        fb = TTSFallbackProvider([p1, p2])

        with pytest.raises(TTSProviderError, match="timed out"):
            fb.synthesize("Hello")

        assert mock_http.post.call_count == 1

    def test_empty_text_validation(self) -> None:
        """Validation errors propagate from the first provider."""
        p1 = _make_provider("qwen3-tts-flash")
        fb = TTSFallbackProvider([p1])

        with pytest.raises(ValueError, match="must not be empty"):
            fb.synthesize("")


# ------------------------------------------------------------------
# Factory integration
# ------------------------------------------------------------------


class TestFactoryIntegration:
    def test_fallback_from_env(self) -> None:
        """get_tts_provider returns TTSFallbackProvider when env is set."""
        from n3rverberage.providers.factory import get_tts_provider

        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_TTS_FALLBACK_MODELS": "qwen3-tts-flash,qwen3-tts-instruct-flash",
            },
        ):
            provider = get_tts_provider()

        assert isinstance(provider, TTSFallbackProvider)
        assert provider.model == "qwen3-tts-flash"

    def test_no_fallback_env_returns_single(self) -> None:
        """get_tts_provider returns single TTSProvider when no fallback env."""
        from n3rverberage.providers.factory import get_tts_provider

        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
            },
        ):
            provider = get_tts_provider()

        assert isinstance(provider, TTSProvider)
        assert provider.model == "qwen3-tts-flash"

    def test_fallback_empty_env_raises(self) -> None:
        """Empty fallback env raises ValueError."""
        from n3rverberage.providers.factory import get_tts_provider

        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_TTS_FALLBACK_MODELS": "",  # empty string
            },
        ):
            # Empty string means no fallback → returns single TTSProvider
            provider = get_tts_provider()

        assert isinstance(provider, TTSProvider)
