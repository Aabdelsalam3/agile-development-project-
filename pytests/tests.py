import os
import sys
from pathlib import Path

import pytest

# Add the voice-ai module directory to sys.path so tests can import main.py directly.
ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT_DIR/"voice-ai"/"speech-assistant-openai-realtime-api-python"


@pytest.fixture(scope="session", autouse=True)
def voice_ai_test_setup():
    """Set up the environment so main.py can be imported in tests."""
    os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
    sys.path.insert(0, str(SOURCE_DIR))


@pytest.fixture(scope="session")
def main_module():
    """Import the voice-ai main module after test environment setup."""
    import importlib

    return importlib.import_module("main")


def test_normalize_text(main_module):
    assert main_module.normalize_text(" Hello! ") == "hello"


def test_parse_time_to_object(main_module):
    assert main_module.parse_time_to_object("4:30 PM").hour == 16
    assert main_module.parse_time_to_object("10 AM").minute == 0


def test_format_booking_time(main_module):
    assert main_module.format_booking_time("10:00 am") == "10 AM"
    assert main_module.format_booking_time("4:30 pm") == "4:30 PM"


def test_is_valid_booking_time(main_module):
    assert main_module.is_valid_booking_time("10:00 AM")
    assert not main_module.is_valid_booking_time("9:30 AM")
