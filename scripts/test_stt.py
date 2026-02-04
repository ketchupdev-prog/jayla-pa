#!/usr/bin/env python3
"""
Test STT (Groq Whisper). Run: python scripts/test_stt.py [path_to_audio]
  With no path: creates a short sample WAV and runs STT (verifies pipeline).
  With path: transcribes the given file (wav, ogg, mp3, m4a, etc.).
Requires GROQ_API_KEY in .env. See docs/STT_TTS_GROQ.md.
"""

import io
import os
import sys
import wave

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PA_ROOT = os.path.dirname(SCRIPT_DIR)
os.chdir(PA_ROOT)
sys.path.insert(0, PA_ROOT)

_env_path = os.path.join(PA_ROOT, ".env")
if os.path.isfile(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass


def make_sample_wav_bytes() -> bytes:
    """Minimal 1s 16kHz mono WAV (silence) for pipeline test."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)  # 1 second
    return buf.getvalue()


def main():
    path = (sys.argv[1:] or [None])[0]
    if path and os.path.isfile(path):
        with open(path, "rb") as f:
            audio_bytes = f.read()
        if not audio_bytes:
            print("File is empty.")
            sys.exit(1)
        print(f"Loaded {len(audio_bytes)} bytes from {path}")
    else:
        if path:
            print(f"File not found: {path}. Using sample WAV instead.\n")
        audio_bytes = make_sample_wav_bytes()
        print(f"Using sample WAV ({len(audio_bytes)} bytes). Set GROQ_API_KEY and run with a real file for real transcripts.\n")
    try:
        from speech_to_text import transcribe
        text = transcribe(audio_bytes)
        print("Transcript:")
        print(text.strip() or "(empty or silence)")
    except Exception as e:
        print(f"STT failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
