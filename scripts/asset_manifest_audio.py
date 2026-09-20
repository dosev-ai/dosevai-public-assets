"""Bounded MP3 byte validation for governed audio assets."""
from __future__ import annotations

from pathlib import Path

import soundfile as sf


class AudioValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def validate_mp3_audio(path: Path) -> None:
    """Decode the complete MP3 stream without deriving semantic metadata."""
    try:
        info = sf.info(str(path))
        if info.format != "MP3" or info.subtype != "MPEG_LAYER_III":
            raise AudioValidationError(
                "AUDIO_SIGNATURE_MISMATCH",
                f"{path.name}: {info.format}/{info.subtype} is not MP3/MPEG_LAYER_III",
            )
        if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
            raise AudioValidationError(
                "AUDIO_STREAM_INVALID",
                f"{path.name}: frames={info.frames} samplerate={info.samplerate} channels={info.channels}",
            )
        decoded_frames = 0
        with sf.SoundFile(str(path), mode="r") as handle:
            while True:
                block = handle.read(8192, dtype="float32", always_2d=True)
                if len(block) == 0:
                    break
                decoded_frames += len(block)
        if decoded_frames <= 0:
            raise AudioValidationError("AUDIO_DECODE_FAILED", f"{path.name}: no PCM frames decoded")
    except FileNotFoundError as exc:
        raise AudioValidationError("ASSET_NOT_FOUND", str(path)) from exc
    except AudioValidationError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise AudioValidationError("AUDIO_DECODE_FAILED", f"{path.name}: {exc}") from exc
