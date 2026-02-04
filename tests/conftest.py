# Pytest fixtures for jayla-pa tests. See PERSONAL_ASSISTANT_PATTERNS.md Appendix D.7.

import os
import pytest


@pytest.fixture(autouse=True)
def env_jayla(monkeypatch):
    """Ensure test env has minimal jayla vars; don't override if already set."""
    if not os.environ.get("EMAIL"):
        monkeypatch.setenv("EMAIL", "test@example.com")
    if not os.environ.get("USER_ID"):
        monkeypatch.setenv("USER_ID", "test@example.com")
