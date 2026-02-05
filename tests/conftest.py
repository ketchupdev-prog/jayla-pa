# Pytest configuration and fixtures for jayla-pa tests.
# Tests actual implementations against real APIs/databases.

import os
import pytest
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load .env for all tests
load_dotenv()


# -----------------------------------------------------------------------------
# Environment Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def env_jayla(monkeypatch):
    """Ensure test env has minimal jayla vars; don't override if already set."""
    if not os.environ.get("EMAIL"):
        monkeypatch.setenv("EMAIL", "test@example.com")
    if not os.environ.get("USER_ID"):
        monkeypatch.setenv("USER_ID", "test@example.com")


# -----------------------------------------------------------------------------
# API Keys Check Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def check_groq_api_key():
    """Check if GROQ_API_KEY is set."""
    return os.environ.get("GROQ_API_KEY") is not None


@pytest.fixture
def check_deepseek_api_key():
    """Check if DEEPSEEK_API_KEY is set."""
    return os.environ.get("DEEPSEEK_API_KEY") is not None


@pytest.fixture
def check_database_url():
    """Check if DATABASE_URL is set."""
    return os.environ.get("DATABASE_URL") is not None


@pytest.fixture
def check_qdrant():
    """Check if QDRANT_URL and QDRANT_API_KEY are set."""
    return os.environ.get("QDRANT_URL") and os.environ.get("QDRANT_API_KEY")


# -----------------------------------------------------------------------------
# Test User Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def test_user_id():
    """Generate unique test user ID for isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_thread_id():
    """Generate unique thread ID for isolation."""
    return f"thread-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_timestamp():
    """Return current timestamp for test data."""
    return datetime.now().isoformat()


# -----------------------------------------------------------------------------
# Telegram Config Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def telegram_config(test_user_id, test_thread_id):
    """Telegram webhook-style config (same shape as telegram_bot/webhook.py)."""
    return {
        "configurable": {
            "thread_id": test_thread_id,
            "user_id": f"{test_user_id}@example.com",
            "user_name": "",
            "user_role": "",
            "user_company": "",
            "key_dates": "",
            "communication_preferences": "",
            "current_work_context": "",
            "onboarding_step": 0,
        }
    }


@pytest.fixture
def telegram_config_known_user(test_user_id, test_thread_id):
    """Telegram config with known user profile."""
    return {
        "configurable": {
            "thread_id": test_thread_id,
            "user_id": f"{test_user_id}@example.com",
            "user_name": "Test User",
            "user_role": "Developer",
            "user_company": "Test Corp",
            "key_dates": "",
            "communication_preferences": "Brief responses",
            "current_work_context": "Working on tests",
            "onboarding_step": 5,
        }
    }


# -----------------------------------------------------------------------------
# Test Data Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def test_memory_data(test_timestamp):
    """Sample memory data for testing."""
    return f"Test memory at {test_timestamp} - {uuid.uuid4().hex}"


@pytest.fixture
def test_document_data(test_timestamp):
    """Sample document content for testing."""
    return f"Test document content created at {test_timestamp}"


@pytest.fixture
def test_image_data():
    """Create a valid test image (PNG red square)."""
    import zlib
    import struct
    
    def create_png(width=100, height=100, color=(255, 0, 0)):
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
    
    return create_png()


@pytest.fixture
def test_audio_data():
    """Create a minimal valid WAV file for STT testing."""
    import struct
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        with __import__('wave').open(f.name, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            # 0.5 second of silence
            wav.writeframes(b'\x00' * 8000)
        yield f.name
        
        try:
            os.unlink(f.name)
        except:
            pass


# -----------------------------------------------------------------------------
# Cleanup Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def cleanup_test_data():
    """Cleanup fixture for test data (runs at session end)."""
    yield
    
    # Optional: cleanup test data from databases
    # This is a placeholder - actual cleanup would need implementation
    pass


# -----------------------------------------------------------------------------
# Markers
# -----------------------------------------------------------------------------

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
