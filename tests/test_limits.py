"""Tests for n3rverberage.limits — input validation functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from n3rverberage.limits import (
    InputValidationError,
    estimate_tokens,
    validate_audio_duration,
    validate_audio_file,
    validate_image_input,
    validate_text_input,
)

# ---------------------------------------------------------------------------
# AC-1: limits.py exists (verified by successful import above)
# AC-2: InputValidationError is a ValueError subclass
# ---------------------------------------------------------------------------


class TestInputValidationError:
    def test_is_value_error_subclass(self) -> None:
        assert issubclass(InputValidationError, ValueError)

    def test_can_be_caught_as_value_error(self) -> None:
        with pytest.raises(ValueError):
            raise InputValidationError("test")


# ---------------------------------------------------------------------------
# AC-9: estimate_tokens accuracy
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_four_chars(self) -> None:
        assert estimate_tokens("a" * 4) == 1

    def test_hello_world(self) -> None:
        assert estimate_tokens("hello world") == 2  # 11 chars // 4 = 2

    def test_exact_boundary(self) -> None:
        assert estimate_tokens("a" * 8) == 2


# ---------------------------------------------------------------------------
# AC-3, AC-4: validate_audio_file
# ---------------------------------------------------------------------------


class TestValidateAudioFile:
    def test_raises_on_oversized_file(self, tmp_path: Path) -> None:
        """AC-3: 30 MB file vs whisper-1 25 MB limit."""
        audio_file = tmp_path / "large.mp3"
        audio_file.write_bytes(b"\x00" * 30_000_000)
        with pytest.raises(InputValidationError, match="25 MB"):
            validate_audio_file(audio_file, model="whisper-1")

    def test_accepts_file_under_limit(self, tmp_path: Path) -> None:
        """AC-4: 1 MB file vs whisper-1 25 MB limit."""
        audio_file = tmp_path / "small.mp3"
        audio_file.write_bytes(b"\x00" * 1_000_000)
        validate_audio_file(audio_file, model="whisper-1")  # should not raise

    def test_raises_on_missing_file(self) -> None:
        """AC-11: FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            validate_audio_file(Path("/tmp/nonexistent_audio.mp3"))

    def test_model_aware_limit(self, tmp_path: Path) -> None:
        """AC-10: Different models have different limits."""
        audio_file = tmp_path / "medium.mp3"
        # 50 MB — exceeds whisper-1 (25 MB) but within fun-asr (2 GB)
        audio_file.write_bytes(b"\x00" * 50_000_000)
        with pytest.raises(InputValidationError, match="25 MB"):
            validate_audio_file(audio_file, model="whisper-1")
        validate_audio_file(audio_file, model="fun-asr")  # should not raise

    def test_error_message_includes_guidance(self, tmp_path: Path) -> None:
        """AC-21: Error messages include actionable guidance."""
        audio_file = tmp_path / "huge.mp3"
        audio_file.write_bytes(b"\x00" * 30_000_000)
        with pytest.raises(InputValidationError) as exc_info:
            validate_audio_file(audio_file, model="whisper-1")
        msg = str(exc_info.value)
        assert "MB" in msg
        assert "Split" in msg or "model" in msg

    def test_unknown_model_uses_default(self, tmp_path: Path) -> None:
        """AC-25: Unknown model falls back to conservative default (25 MB)."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"\x00" * 1_000_000)  # 1 MB — under 25 MB default
        validate_audio_file(audio_file, model="unknown-model-xyz")  # should not raise

    def test_zero_byte_file(self, tmp_path: Path) -> None:
        """AC-4 edge case: 0-byte file passes validation."""
        audio_file = tmp_path / "empty.mp3"
        audio_file.write_bytes(b"")
        validate_audio_file(audio_file, model="whisper-1")  # should not raise


# ---------------------------------------------------------------------------
# AC-5, AC-6: validate_text_input
# ---------------------------------------------------------------------------


class TestValidateTextInput:
    def test_raises_on_oversized_text(self) -> None:
        """AC-5: ~1.1M tokens exceeds qwen3-coder-plus 1M limit."""
        # 4 chars per token estimate: need > 1,048,576 * 4 = 4,194,304 chars
        huge_text = "x" * 4_200_000  # ~1,050,000 tokens
        with pytest.raises(InputValidationError, match="token"):
            validate_text_input(huge_text, model="qwen3-coder-plus")

    def test_accepts_text_under_limit(self) -> None:
        """AC-6: Short text passes validation."""
        validate_text_input("Hello world", model="qwen3-coder-plus")  # should not raise

    def test_model_aware_limit(self) -> None:
        """AC-10: qwen-long has 10M token limit — 1M tokens should pass."""
        text_1m = "x" * 4_000_000  # ~1M tokens
        validate_text_input(text_1m, model="qwen-long")  # should not raise (10M limit)

    def test_empty_text(self) -> None:
        """Edge case: 0 tokens passes."""
        validate_text_input("", model="qwen3-coder-plus")

    def test_unknown_model_uses_default(self) -> None:
        """AC-25: Unknown model uses 1M token default."""
        validate_text_input("short text", model="unknown-model-xyz")

    def test_error_message_includes_guidance(self) -> None:
        """AC-21: Error messages include token count and guidance."""
        huge_text = "x" * 4_200_000  # ~1,050,000 tokens
        with pytest.raises(InputValidationError) as exc_info:
            validate_text_input(huge_text, model="qwen3-coder-plus")
        msg = str(exc_info.value)
        assert "token" in msg.lower()
        assert "Shorten" in msg or "context" in msg


# ---------------------------------------------------------------------------
# AC-7, AC-8: validate_image_input
# ---------------------------------------------------------------------------


class TestValidateImageInput:
    def test_raises_on_oversized_file(self, tmp_path: Path) -> None:
        """AC-7: 15 MB file vs 10 MB base64 limit (7.5 MB raw)."""
        img_file = tmp_path / "large.png"
        img_file.write_bytes(b"\x00" * 15_000_000)
        with pytest.raises(InputValidationError, match="MB"):
            validate_image_input(img_file, model="qwen3.7-plus")

    def test_accepts_image_under_limit(self, tmp_path: Path) -> None:
        """AC-8: 1 MB file passes (under 7.5 MB raw limit)."""
        img_file = tmp_path / "small.png"
        img_file.write_bytes(b"\x00" * 1_000_000)
        validate_image_input(img_file, model="qwen3.7-plus")  # should not raise

    def test_raises_on_missing_file(self) -> None:
        """AC-11: FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            validate_image_input(Path("/tmp/nonexistent_image.png"))

    def test_raw_limit_is_75_percent_of_base64(self, tmp_path: Path) -> None:
        """Edge case: 8 MB file exceeds 7.5 MB raw limit (75% of 10 MB)."""
        img_file = tmp_path / "borderline.png"
        img_file.write_bytes(b"\x00" * 8_000_000)  # 8 MB > 7.5 MB
        with pytest.raises(InputValidationError):
            validate_image_input(img_file, model="qwen3.7-plus")

    def test_exactly_at_raw_limit(self, tmp_path: Path) -> None:
        """Edge case: 7.5 MB file is exactly at the raw limit."""
        img_file = tmp_path / "exact.png"
        img_file.write_bytes(b"\x00" * 7_500_000)  # exactly 7.5 MB
        validate_image_input(img_file, model="qwen3.7-plus")  # should not raise

    def test_unknown_model_uses_default(self, tmp_path: Path) -> None:
        """AC-25: Unknown model uses 10 MB default."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x00" * 1_000_000)
        validate_image_input(img_file, model="unknown-model-xyz")


# ---------------------------------------------------------------------------
# AC-4, AC-5, AC-6, AC-7: validate_audio_duration
# ---------------------------------------------------------------------------


class TestValidateAudioDuration:
    """Duration validation tests — uses mock to avoid ffprobe dependency."""

    def test_imports_and_exists(self) -> None:
        """AC-4: validate_audio_duration exists and importable."""
        from n3rverberage.limits import validate_audio_duration

        assert callable(validate_audio_duration)

    def test_raises_on_over_duration(self, tmp_path: Path, mocker) -> None:
        """AC-4: mock ffprobe returning 600s for qwen3-asr-flash (5 min limit)."""
        audio_file = tmp_path / "long.wav"
        audio_file.write_bytes(b"\x00" * 1000)

        # Mock _get_audio_duration to return 600s (10 min)
        mocker.patch(
            "n3rverberage.limits._ffprobe_available",
            return_value=True,
        )
        mocker.patch(
            "n3rverberage.limits._get_audio_duration",
            return_value=600.0,
        )

        with pytest.raises(InputValidationError, match="too long|6"):
            validate_audio_duration(audio_file, model="qwen3-asr-flash")

    def test_passes_under_duration(self, tmp_path: Path, mocker) -> None:
        """AC-5: mock ffprobe returning 120s for qwen3-asr-flash (5 min limit)."""
        audio_file = tmp_path / "short.wav"
        audio_file.write_bytes(b"\x00" * 1000)

        mocker.patch(
            "n3rverberage.limits._ffprobe_available",
            return_value=True,
        )
        mocker.patch(
            "n3rverberage.limits._get_audio_duration",
            return_value=120.0,
        )

        validate_audio_duration(audio_file, model="qwen3-asr-flash")  # should not raise

    def test_raises_on_missing_file(self) -> None:
        """FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            validate_audio_duration(Path("/tmp/nonexistent_audio.wav"))

    def test_skips_when_ffprobe_unavailable(self, tmp_path: Path, mocker) -> None:
        """AC-7: When ffprobe is missing, duration check is skipped (no error)."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"\x00" * 1000)

        mocker.patch(
            "n3rverberage.limits._ffprobe_available",
            return_value=False,
        )

        # Should not raise — silent skip
        validate_audio_duration(audio_file, model="qwen3-asr-flash")

    def test_error_message_includes_guidance(self, tmp_path: Path, mocker) -> None:
        """AC-14: Error messages include actionable guidance."""
        audio_file = tmp_path / "long.wav"
        audio_file.write_bytes(b"\x00" * 1000)

        mocker.patch(
            "n3rverberage.limits._ffprobe_available",
            return_value=True,
        )
        mocker.patch(
            "n3rverberage.limits._get_audio_duration",
            return_value=600.0,
        )

        with pytest.raises(InputValidationError) as exc_info:
            validate_audio_duration(audio_file, model="qwen3-asr-flash")
        msg = str(exc_info.value)
        assert "minutes" in msg or "seconds" in msg or "limit" in msg
        assert "Trim" in msg or "model" in msg

    def test_model_aware_limits(self) -> None:
        """AC-6: Duration limits per model are correct."""
        from n3rverberage.limits import _AUDIO_DURATION_LIMITS

        assert _AUDIO_DURATION_LIMITS["qwen3-asr-flash"] == 300
        assert _AUDIO_DURATION_LIMITS["qwen3.5-omni-plus"] == 10800
        assert _AUDIO_DURATION_LIMITS["fun-asr"] == 43200
        assert _AUDIO_DURATION_LIMITS["whisper-1"] == 7200


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-3: Base64 audio size limit tests
# ---------------------------------------------------------------------------


class TestBase64AudioLimits:
    """Base64-mode audio size limit validation."""

    def test_qwen_asr_flash_base64_limit(self, tmp_path: Path) -> None:
        """AC-1: 15 MB file raises for qwen3-asr-flash (7.5 MB limit)."""
        audio_file = tmp_path / "large.wav"
        audio_file.write_bytes(b"\x00" * 15_000_000)
        with pytest.raises(InputValidationError):
            validate_audio_file(audio_file, model="qwen3-asr-flash")

    def test_qwen_omni_plus_base64_limit(self, tmp_path: Path) -> None:
        """AC-1: 15 MB file raises for qwen3.5-omni-plus (same 7.5 MB limit)."""
        audio_file = tmp_path / "large.wav"
        audio_file.write_bytes(b"\x00" * 15_000_000)
        with pytest.raises(InputValidationError):
            validate_audio_file(audio_file, model="qwen3.5-omni-plus")

    def test_small_file_passes_base64_limit(self, tmp_path: Path) -> None:
        """AC-3: 1 MB file passes for Base64 models."""
        audio_file = tmp_path / "small.wav"
        audio_file.write_bytes(b"\x00" * 1_000_000)
        validate_audio_file(audio_file, model="qwen3.5-omni-plus")  # should not raise

    def test_fun_asr_url_mode_accepts_large_file(self, tmp_path: Path) -> None:
        """AC-2: 100 MB file passes for fun-asr (URL mode, 2 GB limit)."""
        audio_file = tmp_path / "large.wav"
        audio_file.write_bytes(b"\x00" * 100_000_000)
        validate_audio_file(audio_file, model="fun-asr")  # should not raise

    def test_error_boundary(self, tmp_path: Path) -> None:
        """5 MB file passes (under 7.5 MB), 10 MB file fails."""
        audio_file = tmp_path / "under.wav"
        audio_file.write_bytes(b"\x00" * 5_000_000)
        validate_audio_file(audio_file, model="qwen3.5-omni-plus")  # should not raise

        audio_file = tmp_path / "over.wav"
        audio_file.write_bytes(b"\x00" * 10_000_000)
        with pytest.raises(InputValidationError):
            validate_audio_file(audio_file, model="qwen3.5-omni-plus")


# ---------------------------------------------------------------------------
# AC-22: No new hard dependencies
# AC-24: limits.py is importable without n3rverberage (uses only pathlib + json + subprocess)
# ---------------------------------------------------------------------------


class TestModuleStructure:
    def test_only_stdlib_imports(self) -> None:
        """AC-24: limits.py uses only pathlib (stdlib)."""
        import ast
        from pathlib import Path

        limits_path = Path(__file__).parent.parent / "src" / "n3rverberage" / "limits.py"
        tree = ast.parse(limits_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    # Only allow stdlib modules: pathlib, os, etc.
                    top = node.module.split(".")[0]
                    assert top in {
                        "pathlib", "os", "enum", "typing", "__future__",
                        "json", "subprocess",
                    }, (
                        f"Non-stdlib import in limits.py: {node.module}"
                    )
