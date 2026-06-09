"""
Pytest configuration and shared fixtures.
"""
import pytest
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("API_KEY", "test-api-key")
