# Ava vs Jayla: OCR and image generation

**Jayla** has **OCR/vision** (Groq) and **free image generation** (Pollinations.ai). **Ava** has vision and text-to-image via Together AI.

---

## What each has

| Capability | Ava | Jayla |
|------------|-----|--------|
| **Image-to-text (OCR / vision)** | ✅ `ImageToText` (Groq vision) | ✅ **Groq vision** (`vision.py` + webhook photo handling): user sends a photo → download → `analyze_image(bytes)` → description injected as `[Image: ...]` in the message. Uses **GROQ_API_KEY** and **llama-3.2-90b-vision-preview**. |
| **Text-to-image** | ✅ `TextToImage` (Together AI) | ✅ **Pollinations.ai** (`tools_custom/image_gen_tools.py`): tool `generate_image(prompt)` returns a link; free, no API key. |

**Ava implementation:**

- **OCR/vision:** `ava-whatsapp-agent-course/src/ai_companion/modules/image/image_to_text.py` — Groq vision API; when `message.type == "image"`, download media, `analyze_image(image_bytes, prompt)`, append description to content.
- **Image generation:** `ava-whatsapp-agent-course/src/ai_companion/modules/image/text_to_image.py` — Together AI `images.generate`; graph has `image_node` and workflow `"image"`; creates scenario from chat history, then generates image.

---

## What Jayla has today

- **Voice:** Telegram voice messages → Groq Whisper STT → transcript as user message (see `speech_to_text.py`).
- **Documents:** Telegram document (PDF/DOCX) → download → RAG ingest (parse, chunk, embed when available).
- **OCR / vision:** Telegram **photo** → download largest size → **Groq vision** (`vision.analyze_image`) with **llama-3.2-90b-vision-preview** → description injected as `[Image: ...]` in the user message so the agent can "see" the image. Optional caption is prepended. Requires **GROQ_API_KEY** (same key as for LLM/STT).
- **Image generation:** Tool **generate_image(prompt)** uses **Pollinations.ai** (free, no API key). Returns a URL the user can open to view the image. See `tools_custom/image_gen_tools.py`.

---

## Adding OCR/vision to Jayla (like Ava)

1. **Webhook:** Handle `message.photo` (or `message.document` for images): download file via Bot API, get bytes.
2. **Vision:** Call a vision-capable model (e.g. Groq with a vision model, or OpenAI/DeepSeek vision) with the image bytes (e.g. base64 data URL) and an optional user caption/prompt.
3. **Message:** Append the vision description to the user message content (e.g. `[Image: ...]`) and pass the combined message into the graph so the agent can “see” the image.

**Minimal dependency:** Groq supports vision (e.g. `llama-3.2-90b-vision-preview` in Ava’s settings); no extra API key if you already use Groq.

---

## Adding image generation to Jayla (like Ava)

1. **Tool or node:** Add a tool (e.g. `generate_image(prompt)`) that calls an image API (Together AI, Replicate, DALL·E, etc.), or add an `image_node` that runs when the user explicitly asks for an image.
2. **Response:** Return the image (e.g. file path or bytes); webhook sends it back via `send_photo` (Telegram).
3. **Env:** Add the chosen provider’s API key (e.g. `TOGETHER_API_KEY` for Ava’s stack).

---

## Summary

| Feature | Ava | Jayla |
|---------|-----|--------|
| OCR / image understanding | ✅ Groq vision | ✅ Groq vision |
| Image generation | ✅ Together AI | ✅ Pollinations.ai (free) |
| Voice (STT) | ✅ | ✅ Groq Whisper |
| Documents (RAG) | — | ✅ PDF/DOCX ingest |

To give Jayla Ava-like OCR and image generation, add photo handling + vision in the webhook and a text-to-image tool or node; see Ava’s `modules/image` and graph `image_node` for reference.
