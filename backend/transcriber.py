import os
import subprocess
import tempfile
from faster_whisper import WhisperModel

MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"[Whisper] Loading faster-whisper model: {MODEL_SIZE}")
        # cpu + int8 = fastest on Surface (no GPU required)
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        print("[Whisper] Model ready.")
    return _model


def _convert_to_wav(input_path: str) -> str:
    """Convert any audio format to 16kHz mono WAV."""
    wav_path = input_path + ".wav"
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            wav_path,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr.decode()}")
    return wav_path


def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio file and return the text.
    Returns empty string on silence or error.
    """
    wav_path = None
    try:
        wav_path = _convert_to_wav(file_path)
        model = _get_model()

        segments, info = model.transcribe(
            wav_path,
            language=None,          # auto-detect Arabic/English
            beam_size=5,
            vad_filter=True,        # skip silent segments automatically
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text
    except Exception as e:
        print(f"[Whisper] Transcription error: {e}")
        return ""
    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)
