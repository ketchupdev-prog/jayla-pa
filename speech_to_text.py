# Speech-to-text via Groq Whisper. See docs/STT_TTS_GROQ.md.

import os
import tempfile
from typing import Optional

try:
    from groq import Groq
except ImportError:
    Groq = None


def _get_client() -> "Groq":
    if Groq is None:
        raise RuntimeError("Install groq: pip install groq")
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return Groq(api_key=key)


def transcribe(audio_data: bytes, language: str = "en", model: str = "whisper-large-v3-turbo") -> str:
    """Convert speech to text using Groq Whisper.

    Args:
        audio_data: Raw audio bytes (ogg, wav, mp3, m4a, etc.).
        language: ISO-639-1 language code (e.g. "en").
        model: Whisper model id (whisper-large-v3-turbo or whisper-large-v3).

    Returns:
        Transcribed text.

    Raises:
        ValueError: If audio_data is empty.
        RuntimeError: If transcription fails or GROQ_API_KEY missing.
    """
    if not audio_data:
        raise ValueError("Audio data cannot be empty")
    client = _get_client()
    suffix = ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_data)
        path = tmp.name
    try:
        with open(path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=f,
                model=model,
                language=language,
                response_format="text",
            )
        text = result if isinstance(result, str) else getattr(result, "text", str(result))
        return (text or "").strip()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def transcribe_async(audio_data: bytes, language: str = "en", model: str = "whisper-large-v3-turbo") -> str:
    """Async wrapper for transcribe (runs in executor to avoid blocking)."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: transcribe(audio_data, language=language, model=model))
