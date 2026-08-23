"""Input validation for satellite engines.

Pure stdlib module — no n3rverberage imports, no third-party deps.
Importable standalone by any satellite.

Usage in engine:
    from n3rverberage.limits import validate_audio_file, InputValidationError

    def transcribe(self, audio, ...):
        path = Path(audio) if isinstance(audio, str) else audio.path
        validate_audio_file(path, model=self.provider.model)
        # ... API call ...
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


class InputValidationError(ValueError):
    """Raised when input exceeds model-specific API limits."""


# ---------------------------------------------------------------------------
# Audio file size limits by model (bytes)
# Sources:
#   - whisper-1: OpenAI Whisper API 25 MB limit
#   - qwen3-asr-flash: 10 MB in OpenAI-compat mode (base64 in request body)
#     BUT base64 inflates ~33% → effective raw file limit = 7.5 MB
#   - fun-asr: 2 GB native API (file upload/URL mode)
#   - qwen3.5-omni-plus/flash: same 7.5 MB raw limit (base64 mode)
# ---------------------------------------------------------------------------
_AUDIO_SIZE_LIMITS: dict[str, int] = {
    "whisper-1": 25 * 1024 * 1024,
    # Base64-mode: 10 MB base64 payload → ~7.5 MB raw (base64 inflates ~33%)
    "qwen3-asr-flash": int(10 * 1024 * 1024 * 0.75),
    # URL-mode models (filetrans/native API): correct at 2 GB
    "fun-asr": 2 * 1024 * 1024 * 1024,
    "fun-asr-realtime": 2 * 1024 * 1024 * 1024,
    # Base64-mode: same 7.5 MB raw equivalent of 10 MB base64
    "qwen3.5-omni-plus": int(10 * 1024 * 1024 * 0.75),
    "qwen3.5-omni-flash": int(10 * 1024 * 1024 * 0.75),
}
_DEFAULT_AUDIO_LIMIT = 25 * 1024 * 1024  # conservative: 25 MB

# ---------------------------------------------------------------------------
# Audio duration limits by model (seconds)
# Sources:
#   - qwen3-asr-flash: 5 min (300s) OpenAI-compat mode
#   - qwen3-asr-flash-filetrans: 12h (43200s) filetrans API
#   - qwen3.5-omni-plus/flash: 3h (10800s)
#   - fun-asr/fun-asr-realtime: 12h (43200s)
#   - whisper-1: ~2h practical (7200s)
#   - Unknown models default to 5 min (most restrictive)
# ---------------------------------------------------------------------------
_AUDIO_DURATION_LIMITS: dict[str, int] = {
    "qwen3-asr-flash": 300,
    "qwen3-asr-flash-filetrans": 43200,
    "qwen3.5-omni-plus": 10800,
    "qwen3.5-omni-flash": 10800,
    "fun-asr": 43200,
    "fun-asr-realtime": 43200,
    "whisper-1": 7200,
}
_DEFAULT_AUDIO_DURATION = 300  # conservative: 5 minutes

# ---------------------------------------------------------------------------
# Text input token limits by model
# Sources:
#   - qwen3-coder-plus/flash: 1M context
#   - qwen3-coder-next: 256K
#   - qwen3.7-plus/max, qwen3.6-plus/flash, qwen3.5-plus: 1M
#   - qwen3-max: 256K
#   - qwen-plus: 1M
#   - qwen-long: 10M
#   - gpt-4/4o/4-turbo: 128K
# Token estimation: ~4 chars per token (Qwen/GPT-family approximation)
# ---------------------------------------------------------------------------
_TEXT_TOKEN_LIMITS: dict[str, int] = {
    "qwen3-coder-plus": 1_048_576,
    "qwen3-coder-flash": 1_048_576,
    "qwen3-coder-next": 262_144,
    "qwen3.7-plus": 1_048_576,
    "qwen3.7-max": 1_048_576,
    "qwen3.6-plus": 1_048_576,
    "qwen3.6-flash": 1_048_576,
    "qwen3.5-plus": 1_048_576,
    "qwen3-max": 262_144,
    "qwen-plus": 1_048_576,
    "qwen-long": 10_485_760,
    "gpt-4": 128_000,
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
}
_DEFAULT_TEXT_TOKEN_LIMIT = 1_048_576  # conservative: 1M

# ---------------------------------------------------------------------------
# Image file size limits (bytes) — base64 payload limit
# The API limit is on the base64-encoded payload. Raw file must be <= 75%
# of this limit because base64 inflates by ~33%.
# Sources:
#   - qwen3.7-plus: 10 MB base64 payload
#   - gpt-4o: 10 MB base64 payload
# ---------------------------------------------------------------------------
_IMAGE_SIZE_LIMITS: dict[str, int] = {
    "qwen3.7-plus": 10 * 1024 * 1024,
    "qwen3.6-plus": 10 * 1024 * 1024,
    "gpt-4o": 10 * 1024 * 1024,
}
_DEFAULT_IMAGE_LIMIT = 10 * 1024 * 1024  # conservative: 10 MB


def estimate_tokens(text: str) -> int:
    """Approximate token count. Qwen/GPT-family: ~4 chars per token."""
    return len(text) // 4


def validate_audio_file(path: Path, model: str = "whisper-1") -> None:
    """Validate audio file size against model-specific limits.

    Raises:
        FileNotFoundError: if path does not exist.
        InputValidationError: if file exceeds the model's size limit.
    """
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    file_size = path.stat().st_size
    limit = _AUDIO_SIZE_LIMITS.get(model, _DEFAULT_AUDIO_LIMIT)
    limit_mb = limit / (1024 * 1024)
    file_mb = file_size / (1024 * 1024)

    if file_size > limit:
        raise InputValidationError(
            f"Audio file too large: {file_mb:.1f} MB. "
            f"{model} limit is {limit_mb:.0f} MB. "
            f"Split the file or use a model with higher limits."
        )


def validate_text_input(text: str, model: str = "qwen3-coder-plus") -> None:
    """Validate text input length against model-specific token limits.

    Raises:
        InputValidationError: if estimated tokens exceed the model's limit.
    """
    tokens = estimate_tokens(text)
    limit = _TEXT_TOKEN_LIMITS.get(model, _DEFAULT_TEXT_TOKEN_LIMIT)

    if tokens > limit:
        raise InputValidationError(
            f"Text input too long: ~{tokens:,} tokens. "
            f"{model} limit is {limit:,} tokens. "
            f"Shorten the text or use a model with a larger context window."
        )


def validate_image_input(path: Path, model: str = "qwen3.7-plus") -> None:
    """Validate image file size against model-specific base64 payload limits.

    Raises:
        FileNotFoundError: if path does not exist.
        InputValidationError: if file exceeds the model's size limit.
    """
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    file_size = path.stat().st_size
    # Base64 encoding inflates by ~33%, but the API limit is on the
    # base64 payload, not the raw file. We check raw file size against
    # the limit * 0.75 to account for inflation.
    effective_limit = _IMAGE_SIZE_LIMITS.get(model, _DEFAULT_IMAGE_LIMIT)
    limit_mb = effective_limit / (1024 * 1024)
    file_mb = file_size / (1024 * 1024)

    # Raw file must be <= 75% of base64 limit (because b64 adds ~33%)
    max_raw = int(effective_limit * 0.75)
    if file_size > max_raw:
        raise InputValidationError(
            f"Image file too large: {file_mb:.1f} MB. "
            f"{model} base64 limit is {limit_mb:.0f} MB "
            f"(max raw file: {max_raw / (1024 * 1024):.0f} MB). "
            f"Reduce image size or use a model with higher limits."
        )


# ---------------------------------------------------------------------------
# Audio duration validation
# Uses ffprobe (part of ffmpeg) — zero Python deps, requires system binary.
# ---------------------------------------------------------------------------


def _ffprobe_available() -> bool:
    """Check if ffprobe is on the system PATH."""
    cmd = ["where", "ffprobe"] if sys.platform == "win32" else ["which", "ffprobe"]
    try:
        result = subprocess.run(cmd, capture_output=True, check=False)
        return result.returncode == 0
    except Exception:
        return False


def _get_audio_duration(path: Path) -> float:
    """Get audio duration in seconds via ffprobe subprocess.

    Raises:
        RuntimeError: if ffprobe is not found or duration cannot be determined.
    """
    if not _ffprobe_available():
        raise RuntimeError(
            "ffprobe not found. Install ffmpeg to enable duration validation.\n"
            "  Ubuntu/Debian: sudo apt install ffmpeg\n"
            "  macOS: brew install ffmpeg\n"
            "  Windows: choco install ffmpeg"
        )

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a:0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        result.check_returncode()
        data = json.loads(result.stdout)
        duration = float(data["streams"][0].get("duration", 0))
        if duration <= 0:
            raise ValueError("Zero or negative duration")
        return duration
    except FileNotFoundError:
        raise RuntimeError("ffprobe not found. Install ffmpeg to enable duration validation.") from None
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        raise RuntimeError(
            f"Could not determine audio duration for {path}: {e}. The file may be empty or corrupted."
        ) from e
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out reading {path}. The file may be corrupted or unusually large.") from None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed for {path}: {e.stderr.strip() if e.stderr else e}") from e


def validate_audio_duration(path: Path, model: str = "whisper-1") -> None:
    """Validate audio duration against model-specific limits.

    Uses ffprobe subprocess. Raises RuntimeError if ffprobe is not found.

    Raises:
        FileNotFoundError: if path does not exist.
        RuntimeError: if ffprobe is not available or fails.
        InputValidationError: if duration exceeds the model's limit.
    """
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    # Skip if ffprobe not available — size validation still works
    if not _ffprobe_available():
        return

    try:
        duration = _get_audio_duration(path)
    except RuntimeError:
        # ffprobe couldn't determine duration (corrupt file, no audio stream, etc.)
        # Size validation already passed; let the API decide.
        return

    limit = _AUDIO_DURATION_LIMITS.get(model, _DEFAULT_AUDIO_DURATION)

    if duration > limit:
        minutes = duration / 60
        limit_minutes = limit / 60
        raise InputValidationError(
            f"Audio too long: {minutes:.1f} minutes ({duration:.0f}s). "
            f"{model} limit is {limit_minutes:.0f} minutes ({limit}s). "
            f"Trim the audio or use a model with longer duration limits."
        )
