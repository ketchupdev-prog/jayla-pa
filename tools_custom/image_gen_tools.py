# Optional image generation via Pollinations.ai (free, no API key).
# See docs/AVA_VS_JAYLA_IMAGE_OCR.md. Tool returns image URL for user to open.

from urllib.parse import quote

from langchain_core.tools import tool

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


def _image_url(prompt: str) -> str:
    """Build Pollinations image URL. No auth; GET returns image bytes."""
    encoded = quote(prompt.strip() or "abstract art")
    return f"{POLLINATIONS_BASE}/{encoded}"


@tool
def generate_image(prompt: str) -> str:
    """Generate an image from a text description. Use when the user asks to create, draw, or generate an image. Returns a URL they can open to view the image. Free (Pollinations.ai); no API key required."""
    url = _image_url(prompt)
    return f"Image generated. Open this link to view: {url}"


def get_image_gen_tools() -> list:
    """Return list of image-generation tools (always available; Pollinations is free)."""
    return [generate_image]
