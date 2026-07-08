"""Speech-to-text: Whisper ASR sidecar or Microsoft Azure Speech.

Voice notes come as opus/mp4; they are converted to WAV with ffmpeg before
transcription. The transcription is stored on the message so it flows into the
text analyzers.
"""

import subprocess
import tempfile
from pathlib import Path

import httpx

from ...config import get_settings
from ..types import AnalyzerStatus, Message

TIMEOUT = 120.0

_WHISPER_PARAMS = {"encode": "true", "task": "transcribe", "output": "txt"}


def _to_wav(source: Path) -> Path:
    """Convert an audio file to WAV in a temp location; requires ffmpeg."""
    target = Path(tempfile.mkdtemp(prefix="fw-audio-")) / (source.stem + ".wav")
    subprocess.run(["ffmpeg", "-y", "-i", str(source), str(target)], check=True, capture_output=True)
    return target


def _transcribe_whisper(wav_path: Path) -> str:
    endpoint = get_settings().whisper_endpoint
    with open(wav_path, "rb") as audio:
        response = httpx.post(
            endpoint,
            params=_WHISPER_PARAMS,
            files={"audio_file": ("audio", audio, "audio/wav")},
            headers={"accept": "application/json"},
            timeout=TIMEOUT,
        )
    response.raise_for_status()
    return response.text.strip()


def _transcribe_azure(wav_path: Path) -> str:
    import azure.cognitiveservices.speech as speechsdk

    settings = get_settings()
    speech_config = speechsdk.SpeechConfig(subscription=settings.ms_s2t_key, region=settings.ms_s2t_region)
    speech_config.speech_recognition_language = settings.ms_s2t_language
    audio_config = speechsdk.AudioConfig(filename=str(wav_path))
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    return recognizer.recognize_once_async().get().text


def transcribe(message: Message) -> None:
    """Populate ``message.transcription`` from its audio file."""
    if message.media_path is None:
        return

    audio_path = message.media_path
    mime = message.mime_type or ""
    if "opus" in mime or "mp4" in mime:
        audio_path = _to_wav(audio_path)

    settings = get_settings()
    if settings.use_ms_s2t and settings.ms_s2t_key:
        message.transcription = _transcribe_azure(audio_path)
    elif settings.whisper_endpoint:
        message.transcription = _transcribe_whisper(audio_path)


def _test_audio_path() -> Path | None:
    assets = get_settings().assets_dir
    if assets is None:
        return None
    candidate = assets / "analyzer_checks" / "TestAvailabilityS2T.wav"
    return candidate if candidate.is_file() else None


def check_status_whisper() -> AnalyzerStatus:
    if not get_settings().whisper_endpoint:
        return AnalyzerStatus("WhisperAI", False, "Endpoint not configured")
    test_audio = _test_audio_path()
    if test_audio is None:
        return AnalyzerStatus("WhisperAI", True, "Configured (no test audio available for a full check)")
    try:
        text = _transcribe_whisper(test_audio)
        return AnalyzerStatus("WhisperAI", bool(text), f"Transcribed test audio: {text!r}")
    except Exception as exc:
        return AnalyzerStatus("WhisperAI", False, str(exc))


def check_status_microsoft() -> AnalyzerStatus:
    settings = get_settings()
    if not (settings.use_ms_s2t and settings.ms_s2t_key and settings.ms_s2t_region):
        return AnalyzerStatus("MS_S2T", False, "Not enabled or not configured")
    test_audio = _test_audio_path()
    if test_audio is None:
        return AnalyzerStatus("MS_S2T", True, "Configured (no test audio available for a full check)")
    try:
        text = _transcribe_azure(test_audio)
        return AnalyzerStatus("MS_S2T", bool(text), f"Transcribed test audio: {text!r}")
    except Exception as exc:
        return AnalyzerStatus("MS_S2T", False, str(exc))
