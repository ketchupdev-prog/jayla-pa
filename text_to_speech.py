# TTS: Free Text-to-Speech alternatives.
# Primary: gTTS (Google Translate) - free, requires internet
# Fallback: pyttsx3 - offline, needs file

import io
import os
import tempfile
from typing import Optional


def text_to_speech(
    text: str,
    lang: str = "en",
) -> bytes:
    """
    Generate speech from text using free TTS.

    Tries in order:
    1. gTTS (Google Translate) - free, requires internet
    2. pyttsx3 - offline, robotic voice

    Args:
        text: The text to convert to speech
        lang: Language code (e.g., "en", "es", "fr")

    Returns:
        Audio bytes in WAV format
    """
    # Try gTTS first (requires internet)
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang=lang, slow=False)
        
        # gTTS 2.x uses write_to_fp() instead of save()
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        mp3_bytes = buffer.read()

        # Convert MP3 to WAV using pydub
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()
        return wav_bytes

    except ImportError:
        pass
    except AttributeError:
        # Fallback for older gTTS versions
        pass
    except Exception as e:
        print(f"gTTS failed: {e}")

    # Fallback to pyttsx3 (offline)
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        try:
            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()
        finally:
            os.unlink(tmp_path)

        return wav_bytes

    except ImportError:
        pass
    except Exception as e:
        print(f"pyttsx3 failed: {e}")

    raise ValueError("No TTS backend available. Install: pip install pyttsx3 gtts pydub")


def text_to_speech_file(
    text: str,
    output_path: str,
    lang: str = "en",
) -> None:
    """
    Generate speech and save to a file.

    Args:
        text: The text to convert to speech
        output_path: Path to save the audio file
        lang: Language code
    """
    audio_bytes = text_to_speech(text, lang)

    with open(output_path, "wb") as f:
        f.write(audio_bytes)


async def send_voice_message(
    chat_id: str,
    text: str,
    lang: str = "en",
) -> None:
    """
    Generate voice message and send via Telegram.

    Args:
        chat_id: Telegram chat ID
        text: Text to convert to speech
        lang: Language code
    """
    from telegram import Bot

    audio_bytes = text_to_speech(text, lang)

    with io.BytesIO(audio_bytes) as audio_file:
        await Bot(token=os.environ["TELEGRAM_BOT_TOKEN"]).send_voice(
            chat_id=chat_id,
            voice=audio_file,
        )


# Convenience: check available backends
def check_tts_backends() -> dict:
    """Check which TTS backends are available."""
    backends = {}

    try:
        from gtts import gTTS

        backends["gtts"] = {"available": True, "offline": False, "multilingual": True}
    except ImportError:
        backends["gtts"] = {"available": False, "offline": False, "multilingual": True, "install": "pip install gtts"}

    try:
        import pyttsx3

        backends["pyttsx3"] = {"available": True, "offline": True, "multilingual": False}
    except ImportError:
        backends["pyttsx3"] = {"available": False, "offline": True, "multilingual": False, "install": "pip install pyttsx3"}

    try:
        from pydub import AudioSegment

        backends["pydub"] = {"available": True}
    except ImportError:
        backends["pydub"] = {"available": False, "install": "pip install pydub"}

    return backends


if __name__ == "__main__":
    print("Checking TTS backends...")
    backends = check_tts_backends()

    for name, info in backends.items():
        status = "OK" if info["available"] else "MISSING"
        offline = "(offline)" if info.get("offline") else "(online)"
        print(f"  {status}: {name} {offline}")

    print("\nGenerating test audio with gTTS...")
    try:
        audio = text_to_speech("Hello! This is Jayla, your personal assistant.")
        print(f"SUCCESS: Generated {len(audio)} bytes")
    except Exception as e:
        print(f"Error: {e}")
