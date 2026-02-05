# OCR / vision: describe images using Groq (llama-3.2-90b-vision). See docs/AVA_VS_JAYLA_IMAGE_OCR.md.
# Used when the user sends a Telegram photo; description is injected into the message so the agent can "see" the image.

import base64
import os

# Load .env from jayla-pa root so GROQ_API_KEY is set when vision is imported (e.g. by webhook)
_vision_root = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_vision_root, ".env")
if os.path.isfile(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "llama-3.2-90b-vision-preview")


async def analyze_image(image_bytes: bytes, prompt: str = "") -> str:
    """Describe an image using Groq vision. Returns a short description for the agent context.
    Requires GROQ_API_KEY. If missing or call fails, returns a fallback message."""
    if not image_bytes:
        return "(No image data)"
    api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not api_key:
        return "(Vision not configured: GROQ_API_KEY not set)"
    try:
        from groq import Groq
    except ImportError:
        return "(Vision not available: install groq)"
    prompt = (prompt or "Describe what you see in this image in one or two short sentences, suitable for a personal assistant context.").strip()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }
    ]
    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=GROQ_VISION_MODEL,
            messages=messages,
            max_tokens=500,
        )
        if resp.choices and getattr(resp.choices[0].message, "content", None):
            return (resp.choices[0].message.content or "").strip() or "(No description)"
    except Exception as e:
        return f"(Could not analyze image: {str(e)[:80]})"
    return "(No description)"
