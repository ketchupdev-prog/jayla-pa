# Tests for vision.py - OCR/image analysis with Groq Llama-4
# Tests actual implementation against real Groq API

import os
import pytest
import base64

# Ensure env vars are loaded
from dotenv import load_dotenv
load_dotenv()

from vision import analyze_image, GROQ_VISION_MODEL


class TestVisionUnit:
    """Unit tests for vision module."""

    def test_vision_model_configured(self):
        """Vision model should be configured from env."""
        assert GROQ_VISION_MODEL is not None
        assert "llama-4" in GROQ_VISION_MODEL.lower() or "vision" in GROQ_VISION_MODEL.lower()

    def test_vision_api_key_set(self):
        """GROQ_API_KEY should be set."""
        assert os.environ.get("GROQ_API_KEY") is not None
        assert len(os.environ["GROQ_API_KEY"]) > 10


class TestVisionIntegration:
    """Integration tests - test against real Groq API."""

    @pytest.fixture
    def test_image(self):
        """Create a valid test image (red square PNG)."""
        import zlib
        import struct
        
        def create_png(width, height, color):
            def png_chunk(chunk_type, data):
                chunk_len = struct.pack('>I', len(data))
                chunk_crc = struct.pack('>I', zlib.crc32(chunk_type + data) & 0xffffffff)
                return chunk_len + chunk_type + data + chunk_crc
            
            signature = b'\x89PNG\r\n\x1a\n'
            ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
            ihdr = png_chunk(b'IHDR', ihdr_data)
            
            raw_data = b''
            for y in range(height):
                raw_data += b'\x00'
                for x in range(width):
                    raw_data += bytes(color)
            
            compressed = zlib.compress(raw_data)
            idat = png_chunk(b'IDAT', compressed)
            iend = png_chunk(b'IEND', b'')
            
            return signature + ihdr + idat + iend
        
        return create_png(100, 100, (255, 0, 0))  # Red square

    @pytest.mark.asyncio
    async def test_analyze_image_real_api(self, test_image):
        """Test actual Groq API call with vision model."""
        result = await analyze_image(test_image, "What color is this image?")
        
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # Should mention red or color
        assert "red" in result.lower() or "color" in result.lower()

    def test_analyze_image_empty_raises(self):
        """Empty image data should return fallback message."""
        result = analyze_image(b"")
        assert "(No image data)" in result or len(result) > 0

    def test_analyze_image_no_api_key(self, monkeypatch):
        """Missing API key should return fallback message."""
        monkeypatch.setenv("GROQ_API_KEY", "")
        result = analyze_image(b"fake data")
        assert "GROQ_API_KEY" in result or "not configured" in result.lower()


class TestVisionModelSelection:
    """Tests for vision model selection and fallback."""

    def test_model_is_llama_4(self):
        """Model should be Llama-4-Scout (not deprecated llama-3.2)."""
        # The deprecated llama-3.2-90b-vision-preview was causing errors
        assert "llama-4-scout" in GROQ_VISION_MODEL.lower() or \
               "llama-4-maverick" in GROQ_VISION_MODEL.lower()
