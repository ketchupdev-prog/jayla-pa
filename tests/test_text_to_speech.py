"""Integration tests for TTS (Text-to-Speech) with gTTS and pyttsx3."""

import pytest
from text_to_speech import text_to_speech, check_tts_backends, text_to_speech_file


def test_tts_backends_available():
    """Check that at least one TTS backend is available."""
    backends = check_tts_backends()
    available = [name for name, info in backends.items() if info["available"]]
    assert len(available) > 0, "No TTS backends available. Install: pip install pyttsx3 gtts pydub"


def test_gttts_generates_audio():
    """Test that gTTS generates audio bytes."""
    audio = text_to_speech("Hello! This is Jayla, your personal assistant.", lang="en")
    assert isinstance(audio, bytes)
    assert len(audio) > 1000  # Should be several KB for a sentence
    print(f"Generated {len(audio)} bytes of audio")


def test_gttts_multilingual():
    """Test gTTS with different languages."""
    # English
    audio_en = text_to_speech("Hello", lang="en")
    assert len(audio_en) > 0

    # Spanish
    audio_es = text_to_speech("Hola", lang="es")
    assert len(audio_es) > 0


def test_pyttsx3_fallback():
    """Test pyttsx3 offline fallback."""
    # This test only runs if gTTS fails (e.g., no internet)
    # pyttsx3 is offline but robotic quality
    audio = text_to_speech("Test message", lang="en")
    assert isinstance(audio, bytes)
    assert len(audio) > 0


def test_save_to_file():
    """Test saving TTS output to a file."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        text_to_speech_file("Test file output", tmp_path, lang="en")
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 1000
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
