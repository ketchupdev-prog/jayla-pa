# STT and TTS with Groq (from Ava + Groq docs)

Report on how **ava-whatsapp-agent-course** (Ava) does STT/TTS and how **Jayla PA** can use **Groq** for both.

---

## 1. How Ava does STT and TTS

### Ava STT (Speech-to-Text)

- **Provider:** **Groq** (Whisper).
- **Location:** `ava-whatsapp-agent-course/src/ai_companion/modules/speech/speech_to_text.py`
- **Env:** `GROQ_API_KEY`
- **Model:** `whisper-large-v3-turbo` (from settings `STT_MODEL_NAME`).

**Flow:**

1. Incoming audio (e.g. WhatsApp voice message) → download bytes.
2. Write bytes to a temp `.wav` file (Groq SDK expects a file or file-like).
3. Call Groq:
   ```python
   transcription = self.client.audio.transcriptions.create(
       file=audio_file,
       model="whisper-large-v3-turbo",
       language="en",
       response_format="text",
   )
   ```
4. Use returned text as the user message content; push `HumanMessage(content=transcription)` into the graph.

**Usage in Ava:**  
WhatsApp webhook: if `message["type"] == "audio"` → `process_audio_message(message)` → download audio → `speech_to_text.transcribe(audio_data)` → use transcript as `content` for the graph.

### Ava TTS (Text-to-Speech)

- **Provider:** **ElevenLabs** (not Groq).
- **Location:** `ava-whatsapp-agent-course/src/ai_companion/modules/speech/text_to_speech.py`
- **Env:** `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
- **Model:** `eleven_flash_v2_5` (from settings `TTS_MODEL_NAME`).

**Flow:**

1. Router/workflow decides response type; if `workflow == "audio"` → go to `audio_node`.
2. `audio_node` gets the last assistant text reply, then:
   ```python
   output_audio = await text_to_speech_module.synthesize(response)
   return {"messages": response, "audio_buffer": output_audio}
   ```
3. ElevenLabs: `client.text_to_speech.convert(voice_id=..., text=..., model_id=..., voice_settings=...)` → returns audio bytes (generator joined to bytes).
4. Interface (WhatsApp or Chainlit) sends that audio back (e.g. `send_response(..., "audio", audio_buffer)`).

**Summary for Ava:** STT = **Groq Whisper**; TTS = **ElevenLabs**. One Groq key for chat + STT; separate ElevenLabs key for TTS.

---

## 2. Groq models for STT and TTS

### Groq STT (Speech-to-Text)

- **Docs:** [Speech to Text – Groq](https://console.groq.com/docs/speech-to-text)
- **Endpoint:** `POST https://api.groq.com/openai/v1/audio/transcriptions`
- **SDK:** `client.audio.transcriptions.create(...)` (same as Ava).

| Model                    | Use case                         | Cost      | Notes                    |
|--------------------------|----------------------------------|-----------|--------------------------|
| `whisper-large-v3-turbo` | Multilingual, fast, good value   | $0.04/hr  | Ava default; use for Jayla |
| `whisper-large-v3`       | Higher accuracy, + translation   | $0.111/hr | Use when translation needed |

- **File:** max 25 MB (free tier); formats: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm.
- **Params:** `file`, `model`, `language` (e.g. `"en"`), `response_format` (`"text"` or `"json"` / `"verbose_json"`).

**Python (same as Ava):**

```python
from groq import Groq
client = Groq(api_key=os.environ["GROQ_API_KEY"])
with open(temp_path, "rb") as f:
    text = client.audio.transcriptions.create(
        file=f,
        model="whisper-large-v3-turbo",
        language="en",
        response_format="text",
    )
# text is the string when response_format="text"
```

### Groq TTS (Text-to-Speech)

- **Docs:** [Text to Speech – Groq](https://console.groq.com/docs/text-to-speech), [Orpheus](https://console.groq.com/docs/text-to-speech/orpheus)
- **Endpoint:** `POST https://api.groq.com/openai/v1/audio/speech`
- **SDK:** `client.audio.speech.create(...)`.

| Model                            | Language   | Notes                    |
|----------------------------------|------------|--------------------------|
| `canopylabs/orpheus-v1-english`  | English    | Expressive, vocal directions |
| `canopylabs/orpheus-arabic-saudi`| Arabic (SA)| Saudi dialect            |

- **Params:** `model`, `input` (text), `voice` (e.g. `troy`, `hannah`, `austin`), `response_format` (e.g. `"wav"`).
- **Vocal directions:** In text use e.g. `[cheerful]`, `[sad]` for style.

**Python:**

```python
response = client.audio.speech.create(
    model="canopylabs/orpheus-v1-english",
    voice="hannah",  # or troy, austin, etc.
    input="Your reply text here. [cheerful] Optional direction.",
    response_format="wav",
)
# response can be written to file: response.write_to_file(path)
# or read as bytes for Telegram: response.content or iterate chunks
```

So for **Jayla we can use Groq for both STT and TTS**: one `GROQ_API_KEY` for chat, STT, and TTS (no ElevenLabs required).

---

## 3. Using Groq for STT and TTS in Jayla

### STT (voice messages in Telegram)

- **Where:** In `telegram_bot/webhook.py`, when `message.voice` is present (and optionally `message.audio`).
- **Steps:**
  1. Get `file_id` from `message.voice` (or `message.audio`).
  2. Call Telegram `bot.get_file(file_id)` → download bytes (e.g. to temp file or `BytesIO`).
  3. Call Groq `client.audio.transcriptions.create(file=..., model="whisper-large-v3-turbo", language="en", response_format="text")`.
  4. Use returned string as `content` for `HumanMessage(content=content)` and pass into the graph as today (no other change).

**Env:** Reuse existing `GROQ_API_KEY` (same as for chat).

**Optional:** Add a small `speech_to_text.py` module (e.g. under `telegram_bot/` or `modules/speech/`) that wraps Groq transcription so the webhook stays thin.

### TTS (reply as voice in Telegram)

- **Where:** When we want to send a voice reply (e.g. user asked “reply with voice” or a future “workflow” like Ava’s `audio` workflow).
- **Steps:**
  1. After the graph returns the assistant text reply, call Groq TTS: `client.audio.speech.create(model="canopylabs/orpheus-v1-english", voice="hannah", input=reply_text, response_format="wav")`.
  2. Get audio bytes from the response (e.g. `response.content` or `response.write_to_file` then read).
  3. Send via Telegram: `bot.send_voice(chat_id=chat_id, voice=audio_bytes)` (or from file). Telegram accepts various formats; WAV/OGG/MP3 typically work.

**Env:** Same `GROQ_API_KEY`. Optional: `GROQ_TTS_VOICE` (default e.g. `hannah`), `GROQ_TTS_MODEL` (default `canopylabs/orpheus-v1-english`).

**Flow:** Either (a) always send text and only send voice when the user explicitly asks (“reply with voice”), or (b) add a router that sets a “workflow” (e.g. `audio`) and in the webhook, if workflow is audio, run TTS and send_voice instead of send_message (similar to Ava).

---

## 4. Summary

| Component | Ava                       | Jayla with Groq only        |
|-----------|---------------------------|-----------------------------|
| **STT**   | Groq `whisper-large-v3-turbo` | Same: Groq Whisper, same API |
| **TTS**   | ElevenLabs                 | **Groq Orpheus** (`canopylabs/orpheus-v1-english`) |
| **Keys**  | `GROQ_API_KEY` + `ELEVENLABS_*` | Single `GROQ_API_KEY`       |

**Recommendation for Jayla:** Use **Groq for both STT and TTS** so we only need `GROQ_API_KEY`. Implement voice-in (STT) in the webhook when `message.voice` exists; add optional voice-out (TTS) via Orpheus and `send_voice` when the user requests a voice reply or when a future “audio” workflow is set.

**References**

- Ava STT: `ava-whatsapp-agent-course/src/ai_companion/modules/speech/speech_to_text.py`
- Ava TTS: `ava-whatsapp-agent-course/src/ai_companion/modules/speech/text_to_speech.py` (ElevenLabs)
- Ava webhook usage: `ava-whatsapp-agent-course/src/ai_companion/interfaces/whatsapp/whatsapp_response.py` (`process_audio_message`, workflow `audio` → `audio_buffer`)
- Groq STT: https://console.groq.com/docs/speech-to-text
- Groq TTS: https://console.groq.com/docs/text-to-speech and https://console.groq.com/docs/text-to-speech/orpheus
