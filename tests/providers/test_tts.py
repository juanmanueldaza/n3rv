"""Tests for TTSProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from n3rverberage.providers.tts import (
    TTSProvider,
    TTSProviderError,
    TTSQuotaExhaustedError,
)

_AUDIO_BYTES = b"\x00\x01\x02mock_audio_data"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def provider_no_mock() -> TTSProvider:
    """Basic provider for validation tests (no HTTP mocking)."""
    with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
        return TTSProvider()


@pytest.fixture
def mock_http() -> MagicMock:
    """Mock httpx.Client for all HTTP calls.

    Returns a mock Client instance. All tests that exercise ``synthesize()``
    must activate this fixture before constructing a ``TTSProvider`` so that
    ``httpx.Client()`` is patched at construction time.

    Usage::

        @patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"})
        def test_something(self, mock_http: MagicMock) -> None:
            p = TTSProvider()
            ...
    """
    mock_client = MagicMock(spec=httpx.Client)
    patcher = patch("httpx.Client", return_value=mock_client)
    patcher.start()
    yield mock_client
    patcher.stop()


def _generate_response_json(audio_url: str = "https://audio.example.com/out.wav") -> dict:
    """Build a realistic TTS generation response."""
    return {
        "output": {
            "audio": {
                "url": audio_url,
                "id": "audio_test123",
                "expires_at": 1783571451,
            },
            "finish_reason": "stop",
        },
        "usage": {"characters": 56},
        "request_id": "test-request-id",
    }


# ------------------------------------------------------------------
# Constructor
# ------------------------------------------------------------------


class TestConstructor:
    def test_from_env(self) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-env"}):
            p = TTSProvider()
        assert p.model == "qwen3-tts-flash"
        assert p.voice == "Cherry"
        assert p.base_url == "https://dashscope-intl.aliyuncs.com/api/v1"

    def test_explicit_args(self) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-env"}):
            p = TTSProvider(
                api_key="sk-custom",
                model="qwen3-tts-instruct-flash",
                base_url="https://custom/api/v1",
                voice="Serena",
            )
        assert p.model == "qwen3-tts-instruct-flash"
        assert p.base_url == "https://custom/api/v1"
        assert p.voice == "Serena"

    def test_missing_api_key(self) -> None:
        with patch.dict("os.environ", clear=True):
            with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
                TTSProvider()

    def test_env_var_voice(self) -> None:
        with patch.dict(
            "os.environ",
            {"DASHSCOPE_API_KEY": "sk-test", "N3RVERBERAGE_TTS_VOICE": "Serena"},
        ):
            p = TTSProvider()
        assert p.voice == "Serena"

    def test_env_var_base_url(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_TTS_BASE_URL": "https://custom/api/v1",
            },
        ):
            p = TTSProvider()
        assert p.base_url == "https://custom/api/v1"

    def test_fallback_to_general_base_url(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_BASE_URL": "https://general/api/v1",
            },
        ):
            p = TTSProvider()
        assert p.base_url == "https://general/api/v1"

    def test_tts_base_url_takes_priority(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DASHSCOPE_API_KEY": "sk-test",
                "N3RVERBERAGE_TTS_BASE_URL": "https://tts/api/v1",
                "N3RVERBERAGE_BASE_URL": "https://general/api/v1",
            },
        ):
            p = TTSProvider()
        assert p.base_url == "https://tts/api/v1"

    def test_constructor_no_http_call(self) -> None:
        """Constructor should not make HTTP calls — just store config."""
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            with patch("httpx.Client") as mock_cls:
                p = TTSProvider()
        mock_cls.assert_called_once()
        assert p.model == "qwen3-tts-flash"


# ------------------------------------------------------------------
# synthesize() — validation errors
# ------------------------------------------------------------------


class TestSynthesizeValidation:
    def test_empty_text(self, provider_no_mock: TTSProvider) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            provider_no_mock.synthesize("")

    def test_whitespace_text(self, provider_no_mock: TTSProvider) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            provider_no_mock.synthesize("   \n  ")


# ------------------------------------------------------------------
# synthesize() — HTTP interaction (mocked)
# ------------------------------------------------------------------


class TestSynthesizeHTTP:
    def _setup_mock_responses(
        self,
        mock_client: MagicMock,
        gen_status: int = 200,
        gen_json: dict | None = None,
        audio_status: int = 200,
        audio_content: bytes = _AUDIO_BYTES,
    ) -> None:
        """Configure mock responses for generation POST and audio GET."""
        gen_response = MagicMock(spec=httpx.Response)
        gen_response.status_code = gen_status
        if gen_json is not None:
            gen_response.json.return_value = gen_json
            gen_response.text = str(gen_json)
        mock_client.post.return_value = gen_response

        audio_response = MagicMock(spec=httpx.Response)
        audio_response.status_code = audio_status
        audio_response.content = audio_content
        mock_client.get.return_value = audio_response

    # --- Success cases ---

    def test_basic_success(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            result = p.synthesize("Hello world")

            assert isinstance(result, bytes)
            assert result == _AUDIO_BYTES

    def test_sends_correct_payload(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello", voice="Serena", language_type="English")

            call_args, call_kwargs = mock_http.post.call_args
            # POST is called with keyword args only (url=..., headers=..., json=...)
            assert "services/aigc/multimodal-generation/generation" in call_kwargs["url"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer sk-test"
            payload = call_kwargs["json"]
            assert payload["model"] == "qwen3-tts-flash"
            assert payload["input"]["text"] == "Hello"
            assert payload["input"]["voice"] == "Serena"
            assert payload["input"]["language_type"] == "English"

    def test_downloads_audio_from_url(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            audio_url = "https://storage.example.com/output.wav"
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json(audio_url))

            p.synthesize("Hello")

            # Verify GET was called with the audio URL
            get_call = mock_http.get.call_args
            assert get_call is not None
            assert get_call[0][0] == audio_url

    def test_voice_override(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello", voice="Ethan")
            payload = mock_http.post.call_args[1]["json"]
            assert payload["input"]["voice"] == "Ethan"

    def test_language_type_omitted_by_default(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello")
            payload = mock_http.post.call_args[1]["json"]
            assert "language_type" not in payload["input"]

    def test_default_voice_in_payload(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello")
            payload = mock_http.post.call_args[1]["json"]
            assert payload["input"]["voice"] == "Cherry"

    def test_extra_kwargs_go_to_input(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello", instructions="Speak slowly")
            payload = mock_http.post.call_args[1]["json"]
            assert payload["input"]["instructions"] == "Speak slowly"

    # --- Error cases ---

    def test_429_free_tier_exhausted(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 429
            gen_response.text = '{"code": "AllocationQuota.FreeTierOnly"}'
            mock_http.post.return_value = gen_response

            with pytest.raises(TTSQuotaExhaustedError) as exc:
                p.synthesize("Hello")
            assert exc.value.status_code == 429

    def test_429_other(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 429
            gen_response.text = '{"code": "RateLimitExceeded"}'
            mock_http.post.return_value = gen_response

            with pytest.raises(TTSProviderError) as exc:
                p.synthesize("Hello")
            assert exc.value.status_code == 429

    def test_401_unauthorized(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 401
            gen_response.text = "Unauthorized"
            mock_http.post.return_value = gen_response

            with pytest.raises(TTSProviderError) as exc:
                p.synthesize("Hello")
            assert exc.value.status_code == 401

    def test_timeout(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            mock_http.post.side_effect = httpx.TimeoutException("timeout", request=MagicMock())

            with pytest.raises(TTSProviderError, match="timed out"):
                p.synthesize("Hello")

    def test_network_error(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            mock_http.post.side_effect = httpx.RequestError("connection failed")

            with pytest.raises(TTSProviderError, match="TTS request failed"):
                p.synthesize("Hello")

    def test_server_error(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 500
            gen_response.text = "Internal error"
            mock_http.post.return_value = gen_response

            with pytest.raises(TTSProviderError) as exc:
                p.synthesize("Hello")
            assert exc.value.status_code == 500

    def test_response_missing_url(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            bad_json = {"output": {"audio": {}}, "usage": {}}
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 200
            gen_response.json.return_value = bad_json
            gen_response.text = str(bad_json)
            mock_http.post.return_value = gen_response

            with pytest.raises(TTSProviderError, match="No audio URL"):
                p.synthesize("Hello")

    def test_response_with_error_code(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            err_json = {"code": "InvalidParameter", "message": "Bad voice"}
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 200
            gen_response.json.return_value = err_json
            gen_response.text = str(err_json)
            mock_http.post.return_value = gen_response

            with pytest.raises(TTSProviderError, match="Bad voice"):
                p.synthesize("Hello")

    def test_audio_download_fails(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(
                mock_http,
                gen_json=_generate_response_json(),
                audio_status=403,
            )

            with pytest.raises(TTSProviderError, match="Failed to download audio"):
                p.synthesize("Hello")

    def test_audio_download_network_error(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            gen_response = MagicMock(spec=httpx.Response)
            gen_response.status_code = 200
            gen_response.json.return_value = _generate_response_json()
            gen_response.text = str(_generate_response_json())
            mock_http.post.return_value = gen_response
            mock_http.get.side_effect = httpx.RequestError("download failed")

            with pytest.raises(TTSProviderError, match="Failed to download"):
                p.synthesize("Hello")

    def test_model_override_via_kwargs(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello", model="qwen3-tts-instruct-flash")
            payload = mock_http.post.call_args[1]["json"]
            assert payload["model"] == "qwen3-tts-instruct-flash"

    def test_input_override_via_kwargs(self, mock_http: MagicMock) -> None:
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            p = TTSProvider()
            self._setup_mock_responses(mock_http, gen_json=_generate_response_json())

            p.synthesize("Hello", input={"text": "Override!", "voice": "Vivian"})
            payload = mock_http.post.call_args[1]["json"]
            assert payload["input"]["text"] == "Override!"
            assert payload["input"]["voice"] == "Vivian"


# ------------------------------------------------------------------
# Exception classes
# ------------------------------------------------------------------


class TestTTSProviderError:
    def test_basic(self) -> None:
        err = TTSProviderError(model="qwen3-tts-flash", status_code=500, message="boom")
        assert err.model == "qwen3-tts-flash"
        assert err.status_code == 500
        assert "boom" in str(err)

    def test_defaults(self) -> None:
        err = TTSProviderError(model="test")
        assert err.status_code == 0
        assert "unknown error" in str(err)


class TestTTSQuotaExhaustedError:
    def test_is_provider_error(self) -> None:
        err = TTSQuotaExhaustedError(model="qwen3-tts-flash")
        assert isinstance(err, TTSProviderError)
        assert err.status_code == 429
        assert "quota" in str(err).lower()
