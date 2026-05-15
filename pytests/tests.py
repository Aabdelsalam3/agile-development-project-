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

class TestNormalizedText:
    """More tests for normalize_text function"""

    def test_normalize_text_basic(self, main_module):
        assert main_module.normalize_text(" Hello! ") == "hello"

    def test_normalize_text_special_characters(self, main_module):
        assert main_module.normalize_text("YES!!!!") == "yes"
        assert main_module.normalize_text("NO?") == "no"
        assert main_module.normalize_text("Maybe...") == "maybe"

    def test_normalize_text_whitespace(self, main_module):
        assert main_module.normalize_text("   spaces   ") == "spaces"
        # Note: normalize_text only strips spaces, punctuation; tabs are kept
        assert main_module.normalize_text("leading   ") == "leading"
        assert main_module.normalize_text("   leading") == "leading"

    def test_normalize_text_apostrophe(self, main_module):
        assert main_module.normalize_text("that's") == "that's"
        assert main_module.normalize_text("don't") == "don't"

    def test_normalize_text_mixed_case(self, main_module):
        assert main_module.normalize_text("HeLLo WoRLd") == "hello world"


class TestParseTimeToObject:
    """A few more tests for parse_time_to_object function"""

    def test_parse_time_valid_am(self, main_module):
        result = main_module.parse_time_to_object("10 AM")
        assert result.hour == 10
        assert result.minute == 0

    def test_parse_time_valid_pm(self, main_module):
        result = main_module.parse_time_to_object("4:30 PM")
        assert result.hour == 16
        assert result.minute == 30

    def test_parse_time_noon(self, main_module):
        result = main_module.parse_time_to_object("12:00 PM")
        assert result.hour == 12

    def test_parse_time_midnight(self, main_module):
        result = main_module.parse_time_to_object("12:00 AM")
        assert result.hour == 0

    def test_parse_time_invalid_format(self, main_module):
        assert main_module.parse_time_to_object("not a time") is None
        assert main_module.parse_time_to_object("25:00 PM") is None
        assert main_module.parse_time_to_object("10:75 AM") is None

    def test_parse_time_case_insensitive(self, main_module):
        result1 = main_module.parse_time_to_object("3:00 pm")
        result2 = main_module.parse_time_to_object("3:00 PM")
        assert result1.hour == result2.hour == 15


class TestFormatBookingTime:
    """More tests for format_booking_time function"""

    def test_format_booking_time_lowercase_input(self, main_module):
        assert main_module.format_booking_time("10:00 am") == "10 AM"
        assert main_module.format_booking_time("4:30 pm") == "4:30 PM"

    def test_format_booking_time_without_minutes(self, main_module):
        assert main_module.format_booking_time("3 PM") == "3 PM"
        assert main_module.format_booking_time("10 AM") == "10 AM"

    def test_format_booking_time_with_minutes(self, main_module):
        assert main_module.format_booking_time("3:30 PM") == "3:30 PM"
        assert main_module.format_booking_time("10:30 AM") == "10:30 AM"

    def test_format_booking_time_noon(self, main_module):
        result = main_module.format_booking_time("12:00 PM")
        assert result == "12 PM"

    def test_format_booking_time_midnight(self, main_module):
        result = main_module.format_booking_time("12:00 AM")
        assert result == "12 AM"


class TestIsValidBookingTime:
    """More tests for is_valid_booking_time function"""

    def test_is_valid_booking_time_boundaries(self, main_module):
        # 10 AM - valid start time
        assert main_module.is_valid_booking_time("10:00 AM")
        # 4:30 PM - valid end time
        assert main_module.is_valid_booking_time("4:30 PM")

    def test_is_valid_booking_time_before_hours(self, main_module):
        assert not main_module.is_valid_booking_time("9:00 AM")
        assert not main_module.is_valid_booking_time("8:30 AM")

    def test_is_valid_booking_time_after_hours(self, main_module):
        assert not main_module.is_valid_booking_time("5:00 PM")
        assert not main_module.is_valid_booking_time("6:00 PM")

    def test_is_valid_booking_time_within_hours(self, main_module):
        assert main_module.is_valid_booking_time("12:00 PM")
        assert main_module.is_valid_booking_time("2:30 PM")
        assert main_module.is_valid_booking_time("3:00 PM")

    def test_is_valid_booking_time_invalid_format(self, main_module):
        assert not main_module.is_valid_booking_time("not a time")
        assert not main_module.is_valid_booking_time("25:00 PM")


class TestIs30MinInterval:
    """Some tests for is_30_min_interval function"""

    def test_is_30_min_interval_valid(self, main_module):
        assert main_module.is_30_min_interval("10:00 AM")
        assert main_module.is_30_min_interval("10:30 AM")
        assert main_module.is_30_min_interval("3:00 PM")
        assert main_module.is_30_min_interval("3:30 PM")

    def test_is_30_min_interval_invalid(self, main_module):
        assert not main_module.is_30_min_interval("10:15 AM")
        assert not main_module.is_30_min_interval("2:45 PM")
        assert not main_module.is_30_min_interval("3:20 PM")

    def test_is_30_min_interval_invalid_format(self, main_module):
        assert not main_module.is_30_min_interval("not a time")
        assert not main_module.is_30_min_interval("10:00")  # Missing AM/PM

class TestValidateAndStoreBookingTime:
    def test_validate_valid_time_with_ampm(self, main_module):
        call_details = {
            "booking_date": "2026-05-19",
            "booking_day": "Monday",
            "booking_time": "",
            "_time_error": "",
        }
        result = main_module.validate_and_store_booking_time(call_details, "2:00 PM")
        assert result is True
        # format_booking_time removes :00 minutes, so "2:00 PM" becomes "2 PM"
        assert call_details["booking_time"] == "2 PM"
        assert call_details["_time_error"] == ""

    def test_validate_time_without_ampm_stores_raw(self, main_module):
        call_details = {
            "booking_time": "",
            "_time_error": "",
        }
        result = main_module.validate_and_store_booking_time(call_details, "3")
        assert result is True
        assert call_details["booking_time"] == "3"
        assert call_details["_time_error"] == ""

    def test_validate_time_outside_hours_fails(self, main_module):
        call_details = {
            "booking_date": "2026-05-19",
            "booking_day": "Monday",
            "booking_time": "",
            "_time_error": "",
        }
        result = main_module.validate_and_store_booking_time(call_details, "9:00 AM")
        assert result is False
        assert call_details["booking_time"] == ""
        assert "outside our booking hours" in call_details["_time_error"]

    def test_validate_time_not_30_min_interval_fails(self, main_module):
        call_details = {
            "booking_date": "2026-05-19",
            "booking_day": "Monday",
            "booking_time": "",
            "_time_error": "",
        }
        result = main_module.validate_and_store_booking_time(
            call_details, "2:15 PM"
        )
        assert result is False
        assert call_details["booking_time"] == ""
        assert "30 minute intervals" in call_details["_time_error"]

    def test_validate_valid_30_min_intervals(self, main_module):
        test_cases = [
            ("10:00 AM", "10 AM"),
            ("10:30 AM", "10:30 AM"),
            ("12:00 PM", "12 PM"),
            ("2:30 PM", "2:30 PM"),
            ("4:00 PM", "4 PM"),
            ("4:30 PM", "4:30 PM"),
        ]
        for time_str, expected_formatted in test_cases:
            call_details = {
                "booking_date": "2026-05-19",
                "booking_day": "Monday",
                "booking_time": "",
                "_time_error": "",
            }
            result = main_module.validate_and_store_booking_time(call_details, time_str)
            assert result is True, f"Failed for {time_str}"
            assert call_details["booking_time"] == expected_formatted


class TestBuildTimeErrorMessage:
    def test_error_message_not_30_min_interval(self, main_module):
        call_details = {
            "booking_date": "2026-05-19",
            "booking_day": "Monday",
        }
        msg = main_module.build_time_error_message(
            call_details, "3:15 PM", "not_30_min_interval"
        )
        assert "30 minute intervals" in msg
        assert "3:00 PM" in msg or "3:30 PM" in msg

    def test_error_message_outside_hours(self, main_module):
        call_details = {
            "booking_date": "2026-05-19",
            "booking_day": "Monday",
        }
        msg = main_module.build_time_error_message(
            call_details, "9:00 AM", "outside_hours"
        )
        assert "outside our booking hours" in msg
        assert "10:00 AM" in msg
        assert "4:30 PM" in msg

    def test_error_message_already_booked_with_suggestions(self, main_module):
        call_details = {
            "booking_date": "2026-05-19",
            "booking_day": "Monday",
        }
        msg = main_module.build_time_error_message(
            call_details, "10:00 AM", "already_booked"
        )
        assert "already booked" in msg
        assert "Monday" in msg


class TestGetNextAvailableTimes:
    def test_get_next_available_times_returns_list(self, main_module):
        available = main_module.get_next_available_times("2026-05-19")
        assert isinstance(available, list)
        assert len(available) > 0

    def test_get_next_available_times_respects_business_hours(self, main_module):
        available = main_module.get_next_available_times("2026-05-19")
        for time_str in available:
            # All times should be valid and 30-minute intervals
            assert main_module.is_valid_booking_time(time_str)
            assert main_module.is_30_min_interval(time_str)

    def test_get_next_available_times_after_time(self, main_module):
        all_times = main_module.get_next_available_times("2026-05-19")
        after_times = main_module.get_next_available_times(
            "2026-05-19", after_time="2:00 PM"
        )

        assert len(after_times) <= len(all_times)
        if after_times:
            assert after_times[0] != "10:00 AM"

    def test_get_next_available_times_max_3_suggestions(self, main_module):
        available = main_module.get_next_available_times("2026-05-19")
        assert len(available) <= 3


class TestIsSlotAvailable:
    def test_is_slot_available_returns_boolean(self, main_module):
        result = main_module.is_slot_available("2026-05-19", "10:00 AM")
        assert isinstance(result, bool)

    def test_is_slot_available_new_date_available(self, main_module):
        result = main_module.is_slot_available("2026-06-19", "10:00 AM")
        assert result is True

    def test_is_slot_available_different_times_independent(self, main_module):
        date_str = "2026-05-20"
        time1 = main_module.is_slot_available(date_str, "10:00 AM")
        time2 = main_module.is_slot_available(date_str, "10:30 AM")
        time3 = main_module.is_slot_available(date_str, "11:00 AM")
        assert time1 is True
        assert time2 is True
        assert time3 is True


class TestBookingTimeFormatting:
    def test_format_then_validate_workflow(self, main_module):
        formatted = main_module.format_booking_time("3:30 pm")
        assert formatted == "3:30 PM"
        is_valid = main_module.is_valid_booking_time(formatted)
        assert is_valid is True

    def test_parse_format_validate_workflow(self, main_module):
        raw_time = "2:00 pm"
        parsed = main_module.parse_time_to_object(raw_time)
        assert parsed is not None

        formatted = main_module.format_booking_time(raw_time)
        assert formatted == "2 PM"

        is_valid = main_module.is_valid_booking_time(formatted)
        assert is_valid is True

        is_interval = main_module.is_30_min_interval(formatted)
        assert is_interval is True

    def test_complete_time_validation_flow(self, main_module):
        test_times = [
            ("10:00 AM", True),
            ("10:15 AM", False),
            ("9:00 AM", False),
            ("5:00 PM", False),
            ("2:30 PM", True),
        ]

        for time_str, should_be_valid in test_times:
            formatted = main_module.format_booking_time(time_str)
            is_valid = main_module.is_valid_booking_time(formatted)
            is_interval = main_module.is_30_min_interval(formatted)
            result = is_valid and is_interval
            assert result == should_be_valid, f"Failed for {time_str}"
