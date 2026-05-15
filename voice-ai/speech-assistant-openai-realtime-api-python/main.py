import os
import json
import re
import asyncio
import websockets
import sqlite3

from datetime import datetime, date, timedelta, time
from pathlib import Path
from typing import Optional, Tuple

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# ---------------------------
# Config
# ---------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", 5050))
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.8))

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

VOICE = os.getenv("OPENAI_VOICE", "alloy")
HANGUP_DELAY_SECONDS = int(os.getenv("HANGUP_DELAY_SECONDS", 4))

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env")

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    print("WARNING: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN missing. Auto-hangup will not work.")


BOOKING_WINDOW_DAYS = 14
BUSINESS_START = time(10, 0)
BUSINESS_END = time(16, 30)
APPOINTMENT_INTERVAL_MINUTES = 30

GOODBYE_PHRASES = [
    "your appointment information has been recorded",
    "thank you for calling. goodbye",
    "thank you for calling",
    "goodbye",
]

YES_WORDS = {
    "yes",
    "yeah",
    "yep",
    "ya",
    "correct",
    "that's correct",
    "that is correct",
    "yes correct",
    "yes that's correct",
    "yes that is correct",
    "sounds good",
    "right",
    "perfect",
    "that's perfect",
    "that is perfect",
    "nope that's perfect",
    "nope that is perfect",
}

NO_WORDS = {
    "no",
    "nope",
    "nah",
    "not correct",
    "that's wrong",
    "that is wrong",
    "incorrect",
}

DAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "today",
    "tomorrow",
]

WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def get_current_date_text() -> str:
    return date.today().strftime("%A, %B %d, %Y")


def build_system_message() -> str:
    return f"""
You are Team 12's AI Barber shop assistant.

IMPORTANT:
Speak English only.
Never switch languages.
If the caller is unclear, ask them to repeat in English.
Only accept confirmation if the caller clearly says yes, yeah, yep, ya, correct, perfect, or sounds good in English.
If the caller responds in another language or says something unclear, do not confirm.
Instead say:
"Sorry, I can only confirm in English. Please say yes if the details are correct, or no if something needs to be changed."

Current date:
- Today's date is {get_current_date_text()}.
- Use this current date when understanding phrases like this Friday, next Friday, next week, today, and tomorrow.

Your job is to collect simple appointment information from the caller.

Only collect these details:
1. The caller's first name
2. Their phone number
3. The day they are coming in
4. The time they are coming in

Conversation rules:
- Ask only one question at a time.
- Keep responses short because this is a phone call.
- Stay professional, simple, and focused.
- Do not go off-topic.
- Do not pretend to be human.
- Do not make promises, prices, or guarantees.
- If the caller gives multiple details at once, acknowledge them and ask for the next missing detail.
- If the caller is unclear, ask them to repeat it in English.

Phone number rules:
- A valid phone number must have 10 digits.
- Never guess, invent, or correct a phone number.
- Only repeat the exact phone number that was successfully collected.
- If the phone number is missing or invalid, ask for it again.
- If the phone number is invalid, say:
"Sorry, I need a valid 10 digit phone number. What is your phone number?"

Important day rule:
- Ask what day the caller is coming in before asking for the time.
- Only accept weekday names: Monday, Tuesday, Wednesday, Thursday, or Friday.
- The caller can also give a date like May 15, May 15th, May fifteenth, fifteenth of May, or 15th of May.
- The caller can only book within the next 14 days.
- If the caller gives a weekday like Monday or Friday, use the next upcoming matching weekday.
- If the caller says "next Friday" or another "next [weekday]", use the weekday one week later.
- If the caller says "next week" but does not give a weekday, ask them which weekday next week.
- If the caller gives a specific date, it must be within the next 14 days.
- If the caller asks for a date more than 14 days away, do not accept it.
- If the caller asks for a date more than 14 days away, say:
"We can only book appointments within the next two weeks. Please choose an earlier date."
- Do not suggest today or tomorrow.
- If the caller says today or tomorrow, only accept it if it is a weekday and within the next two weeks.
- If the caller asks for Saturday or Sunday, say appointments are only available Monday to Friday.
- CANNOT book appointments on Saturday or Sunday.
- If the caller gives an unclear day, ask them to repeat the day.

Important time rule:
- Mention that we're open from 10:00 AM to 5:00 PM.
- Latest booking time is 4:30 PM.
- Can only book from 10:00 AM to 4:30 PM.
- CANNOT book appointments before 10:00 AM.
- CANNOT book appointments after 4:30 PM.
- If the caller asks for 5:00 PM or later, do not accept it.
- Appointments must be in 30 minute intervals.
- Valid examples are 10:00 AM, 10:30 AM, 1:00 PM, 1:30 PM, 4:00 PM, and 4:30 PM.
- If the caller asks for a time like 1:45 PM or 3:10 PM, do not accept it.
- If a requested appointment time is already booked, ask the caller to choose another time.
- Do not double-book the same date and time.
- Ask what time the caller is coming in after the day is collected.
- If the caller gives a time without AM or PM, ask:
"Is that AM or PM?"
- If the caller gives multiple times in one sentence, use the final valid time they said.
- Example: if they say "5 PM, actually 4:30, no wait 2 PM", use 2 PM.
- If the caller asks for a time outside 10:00 AM to 4:30 PM, ask them to choose another time.
- Do not confirm the appointment until the booking time includes AM or PM.

Important confirmation rule:
- Only confirm after first name, phone number, booking day, and booking time are all collected.
- Every confirmation must end with exactly:
"Is that correct?"
- Do not skip the phrase "Is that correct?"
- Say:
"Thank you. Let's confirm: your first name is [name], your phone number is [phone number], and you're coming in on [day] at [time]. Is that correct?"
- If the caller says yes, yeah, yep, ya, correct, perfect, or sounds good, end with exactly:
"Your appointment information has been recorded. Thank you for calling. Goodbye."
- If the caller says something unclear, ask them to repeat and do not confirm. Say:
"Sorry, I did not understand. Please say yes if the details are correct, or no if something needs to be changed."
- If any detail is missing, do not say goodbye. Ask for the missing detail.
- Do not say "Oops, I actually can't end the call."
- Do not ask "Is there anything else you'd like to ask or change?"
- If the phone number is missing, ask exactly:
"What is your phone number?"
- If the booking day is missing, ask exactly:
"What day are you coming in? Please choose Monday to Friday within the next two weeks."
- If the booking time is missing, ask exactly:
"What time are you coming in? Please choose a time between 10:00 AM and 4:30 PM."
- If the caller says no, ask:
"What needs to be corrected: your first name, phone number, booking day, or booking time?"
- If the caller asks how something is spelled, answer with the current spelling and ask if it needs to be corrected.
- After any correction, confirm all details again and end with exactly:
"Is that correct?"

Start by saying exactly:
"Hi, this is Team 12's AI Barber shop assistant. I can help collect your appointment information. What is your first name?"
"""


# ---------------------------
# Database / Call Logs
# ---------------------------
CALL_LOG_DIR = Path("call_logs")
CALL_LOG_DIR.mkdir(exist_ok=True)

DATABASE_FILE = CALL_LOG_DIR / "appointments.db"


def initialize_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            booking_day TEXT NOT NULL,
            booking_date TEXT,
            booking_time TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "booking_date" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN booking_date TEXT")

    conn.commit()
    conn.close()


def normalize_text(text: str) -> str:
    return text.lower().replace("’", "'").strip(" .!?,")


def parse_time_to_object(booking_time: str):
    match = re.search(
        r"^(\d{1,2})(?::(\d{2}))?\s*(AM|PM)$",
        booking_time.strip(),
        flags=re.I,
    )

    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = match.group(3).upper()

    if hour < 1 or hour > 12 or minute < 0 or minute > 59:
        return None

    if ampm == "AM":
        if hour == 12:
            hour = 0
    else:
        if hour != 12:
            hour += 12

    return time(hour, minute)


def format_booking_time(booking_time: str) -> str:
    parsed = parse_time_to_object(booking_time)

    if not parsed:
        return booking_time.strip().upper()

    hour_24 = parsed.hour
    minute = parsed.minute
    ampm = "AM" if hour_24 < 12 else "PM"

    hour_12 = hour_24 % 12
    if hour_12 == 0:
        hour_12 = 12

    if minute == 0:
        return f"{hour_12} PM" if ampm == "PM" else f"{hour_12} AM"

    return f"{hour_12}:{minute:02d} {ampm}"


def is_valid_booking_time(booking_time: str) -> bool:
    parsed_time = parse_time_to_object(booking_time)

    if not parsed_time:
        return False

    return BUSINESS_START <= parsed_time <= BUSINESS_END


def is_30_min_interval(booking_time: str) -> bool:
    parsed_time = parse_time_to_object(booking_time)

    if not parsed_time:
        return False

    return parsed_time.minute in [0, 30]


def is_slot_available(booking_date: str, booking_time: str) -> bool:
    initialize_database()

    normalized_time = format_booking_time(booking_time)

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM appointments
        WHERE booking_date = ?
        AND UPPER(REPLACE(booking_time, ':00 ', ' ')) = UPPER(REPLACE(?, ':00 ', ' '))
    """, (booking_date, normalized_time))

    count = cursor.fetchone()[0]

    conn.close()

    return count == 0


def get_next_available_times(booking_date: str, after_time: str = "") -> list[str]:
    available_times = []

    start_minutes = BUSINESS_START.hour * 60 + BUSINESS_START.minute
    end_minutes = BUSINESS_END.hour * 60 + BUSINESS_END.minute

    after_minutes = start_minutes

    parsed_after = parse_time_to_object(after_time)
    if parsed_after:
        after_minutes = parsed_after.hour * 60 + parsed_after.minute + APPOINTMENT_INTERVAL_MINUTES

    current_minutes = max(start_minutes, after_minutes)

    while current_minutes <= end_minutes and len(available_times) < 3:
        hour = current_minutes // 60
        minute = current_minutes % 60

        candidate_time = time(hour, minute)
        ampm = "AM" if candidate_time.hour < 12 else "PM"

        hour_12 = candidate_time.hour % 12
        if hour_12 == 0:
            hour_12 = 12

        if minute == 0:
            candidate_label = f"{hour_12} {ampm}"
        else:
            candidate_label = f"{hour_12}:{minute:02d} {ampm}"

        if is_slot_available(booking_date, candidate_label):
            available_times.append(candidate_label)

        current_minutes += APPOINTMENT_INTERVAL_MINUTES

    return available_times


def build_time_error_message(call_details: dict, requested_time: str, reason: str) -> str:
    booking_date = call_details.get("booking_date", "")
    booking_day = call_details.get("booking_day", "")

    if reason == "not_30_min_interval":
        return "Appointments must be booked in 30 minute intervals. Please choose a time like 3:00 PM or 3:30 PM."

    if reason == "outside_hours":
        return "That time is outside our booking hours. Please choose a time between 10:00 AM and 4:30 PM."

    if reason == "already_booked":
        suggestions = get_next_available_times(booking_date, requested_time)

        if suggestions:
            joined = ", ".join(suggestions)
            return (
                f"{requested_time} on {booking_day} is already booked. "
                f"Please choose another time. Available options after that include {joined}."
            )

        return (
            f"{requested_time} on {booking_day} is already booked, and there are no later available times that day. "
            f"Please choose another time or another weekday."
        )

    return "Please choose another time between 10:00 AM and 4:30 PM."


def validate_and_store_booking_time(call_details: dict, booking_time: str) -> bool:
    if not booking_time:
        return False

    if "AM" not in booking_time.upper() and "PM" not in booking_time.upper():
        call_details["booking_time"] = booking_time
        call_details["_time_error"] = ""
        return True

    normalized_time = format_booking_time(booking_time)

    if not is_valid_booking_time(normalized_time):
        call_details["booking_time"] = ""
        call_details["_time_error"] = build_time_error_message(call_details, normalized_time, "outside_hours")
        return False

    if not is_30_min_interval(normalized_time):
        call_details["booking_time"] = ""
        call_details["_time_error"] = build_time_error_message(call_details, normalized_time, "not_30_min_interval")
        return False

    booking_date = call_details.get("booking_date", "")

    if booking_date and not is_slot_available(booking_date, normalized_time):
        call_details["booking_time"] = ""
        call_details["_time_error"] = build_time_error_message(call_details, normalized_time, "already_booked")
        return False

    call_details["booking_time"] = normalized_time
    call_details["_time_error"] = ""
    return True


def save_call_outputs(call_details: dict, transcript_lines: list[str]):
    initialize_database()

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO appointments (
            name,
            phone_number,
            booking_day,
            booking_date,
            booking_time,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        call_details["name"],
        call_details["phone_number"],
        call_details["booking_day"],
        call_details["booking_date"],
        call_details["booking_time"],
        created_at,
    ))

    appointment_id = cursor.lastrowid

    conn.commit()
    conn.close()

    transcript_path = CALL_LOG_DIR / f"call{appointment_id}_transcript.txt"

    with open(transcript_path, "w", encoding="utf-8") as file:
        file.write("Call Transcript\n")
        file.write("====================\n\n")
        for line in transcript_lines:
            file.write(line + "\n")
        file.write("\n====================\n")
        file.write("Extracted Details\n")
        file.write(f"Appointment ID: {appointment_id}\n")
        file.write(f"Name: {call_details['name']}\n")
        file.write(f"Phone Number: {call_details['phone_number']}\n")
        file.write(f"Booking Day: {call_details['booking_day']}\n")
        file.write(f"Booking Date: {call_details['booking_date']}\n")
        file.write(f"Booking Time: {call_details['booking_time']}\n")
        file.write(f"Created At: {created_at}\n")

    print(f"💾 Saved appointment to SQLite database: {DATABASE_FILE}")
    print(f"📝 Saved transcript to: {transcript_path}")


# ---------------------------
# Date Parsing
# ---------------------------
def is_weekend(check_date: date) -> bool:
    return check_date.weekday() >= 5


def is_within_14_day_window(check_date: date) -> bool:
    today = date.today()
    latest_allowed = today + timedelta(days=BOOKING_WINDOW_DAYS)
    return today <= check_date <= latest_allowed


def get_next_weekday_date(day_name: str, force_next_week: bool = False) -> date:
    today = date.today()
    target_weekday = WEEKDAY_NAMES[day_name.lower()]
    days_ahead = (target_weekday - today.weekday()) % 7

    if force_next_week:
        days_ahead += 7
    elif days_ahead == 0:
        days_ahead = 7

    return today + timedelta(days=days_ahead)


def ordinal_word_to_number(word: str) -> Optional[int]:
    word = normalize_text(word).replace("-", " ")

    ordinal_words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
        "eleventh": 11,
        "twelfth": 12,
        "thirteenth": 13,
        "fourteenth": 14,
        "fifteenth": 15,
        "sixteenth": 16,
        "seventeenth": 17,
        "eighteenth": 18,
        "nineteenth": 19,
        "twentieth": 20,
        "twenty first": 21,
        "twenty second": 22,
        "twenty third": 23,
        "twenty fourth": 24,
        "twenty fifth": 25,
        "twenty sixth": 26,
        "twenty seventh": 27,
        "twenty eighth": 28,
        "twenty ninth": 29,
        "thirtieth": 30,
        "thirty first": 31,
    }

    return ordinal_words.get(word)


def parse_specific_month_date(text: str) -> Optional[date]:
    cleaned = normalize_text(text)

    month_pattern = (
        r"january|jan|february|feb|march|mar|april|apr|may|june|jun|"
        r"july|jul|august|aug|september|sep|sept|october|oct|"
        r"november|nov|december|dec"
    )

    ordinal_word_pattern = (
        r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
        r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|"
        r"seventeenth|eighteenth|nineteenth|twentieth|twenty[\s-]first|"
        r"twenty[\s-]second|twenty[\s-]third|twenty[\s-]fourth|"
        r"twenty[\s-]fifth|twenty[\s-]sixth|twenty[\s-]seventh|"
        r"twenty[\s-]eighth|twenty[\s-]ninth|thirtieth|thirty[\s-]first"
    )

    # Examples: May 15, May 15th, May fifteenth
    match = re.search(
        rf"\b({month_pattern})\s+(\d{{1,2}}(?:st|nd|rd|th)?|{ordinal_word_pattern})(?:\s*,?\s*(\d{{4}}))?\b",
        cleaned,
        flags=re.I,
    )

    if match:
        month_text = match.group(1).lower()
        day_text = match.group(2).lower()
        year_text = match.group(3)
    else:
        # Examples: 15th of May, fifteenth of May
        reverse_match = re.search(
            rf"\b(\d{{1,2}}(?:st|nd|rd|th)?|{ordinal_word_pattern})\s+(?:of\s+)?({month_pattern})(?:\s*,?\s*(\d{{4}}))?\b",
            cleaned,
            flags=re.I,
        )

        if not reverse_match:
            return None

        day_text = reverse_match.group(1).lower()
        month_text = reverse_match.group(2).lower()
        year_text = reverse_match.group(3)

    if re.match(r"\d", day_text):
        day_number = int(re.sub(r"(st|nd|rd|th)$", "", day_text))
    else:
        day_number = ordinal_word_to_number(day_text)

    if not day_number:
        return None

    today = date.today()
    year_number = int(year_text) if year_text else today.year
    month_number = MONTH_NAMES[month_text]

    try:
        picked_date = date(year_number, month_number, day_number)
    except ValueError:
        return None

    if not year_text and picked_date < today:
        picked_date = date(today.year + 1, month_number, day_number)

    return picked_date


def clean_booking_day(text: str) -> str:
    lower = normalize_text(text)

    day_aliases = {
        "mon": "Monday",
        "monday": "Monday",
        "tues": "Tuesday",
        "tuesday": "Tuesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",
        "thurs": "Thursday",
        "thursday": "Thursday",
        "fri": "Friday",
        "friday": "Friday",
        "sat": "Saturday",
        "saturday": "Saturday",
        "sun": "Sunday",
        "sunday": "Sunday",
        "today": "today",
        "tomorrow": "tomorrow",
    }

    for key, value in day_aliases.items():
        if re.search(rf"\b{key}\b", lower):
            return value

    return ""


def parse_booking_day_and_date(text: str, current_booking_day: str = "") -> Tuple[str, str, str]:
    cleaned = normalize_text(text)
    today = date.today()

    if re.search(r"\btoday\b", cleaned):
        picked_date = today
        booking_day = picked_date.strftime("%A")

        if is_weekend(picked_date):
            return "", "", "weekend"

        if not is_within_14_day_window(picked_date):
            return "", "", "outside_window"

        return booking_day, picked_date.isoformat(), ""

    if re.search(r"\btomorrow\b", cleaned):
        picked_date = today + timedelta(days=1)
        booking_day = picked_date.strftime("%A")

        if is_weekend(picked_date):
            return "", "", "weekend"

        if not is_within_14_day_window(picked_date):
            return "", "", "outside_window"

        return booking_day, picked_date.isoformat(), ""

    specific_date = parse_specific_month_date(text)

    if specific_date:
        booking_day = specific_date.strftime("%A")

        if is_weekend(specific_date):
            return "", "", "weekend"

        if not is_within_14_day_window(specific_date):
            return "", "", "outside_window"

        return booking_day, specific_date.isoformat(), ""

    booking_day = clean_booking_day(text)

    if booking_day:
        lower_day = booking_day.lower()

        if lower_day in ["saturday", "sunday"]:
            return "", "", "weekend"

        if lower_day in WEEKDAY_NAMES:
            force_next_week = bool(re.search(r"\bnext\b", cleaned))
            picked_date = get_next_weekday_date(lower_day, force_next_week=force_next_week)

            if is_weekend(picked_date):
                return "", "", "weekend"

            if not is_within_14_day_window(picked_date):
                return "", "", "outside_window"

            return booking_day, picked_date.isoformat(), ""

    if re.search(r"\bnext week\b", cleaned) and current_booking_day:
        lower_day = current_booking_day.lower()

        if lower_day in WEEKDAY_NAMES:
            picked_date = get_next_weekday_date(lower_day, force_next_week=True)

            if is_weekend(picked_date):
                return "", "", "weekend"

            if not is_within_14_day_window(picked_date):
                return "", "", "outside_window"

            return current_booking_day, picked_date.isoformat(), ""

    return "", "", ""


# ---------------------------
# Field Parsing
# ---------------------------
def word_to_number(text: str) -> str:
    words = {
        "one": "1",
        "two": "2",
        "too": "2",
        "to": "2",
        "three": "3",
        "four": "4",
        "for": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
    }

    cleaned = normalize_text(text)

    for word, number in words.items():
        if re.search(rf"\b{word}\b", cleaned):
            return number

    return ""


def clean_booking_time(text: str) -> str:
    normalized = text.strip()

    normalized = normalized.replace("p.m.", "PM").replace("a.m.", "AM")
    normalized = normalized.replace("p.m", "PM").replace("a.m", "AM")
    normalized = normalized.replace("p m", "PM").replace("a m", "AM")

    normalized = re.sub(r"\bpm\b", "PM", normalized, flags=re.I)
    normalized = re.sub(r"\bam\b", "AM", normalized, flags=re.I)

    normalized = re.sub(
        r"\b(uh|um|like|probably|i think|maybe|around|about|kind of|kinda|gonna be|going to be|thinking)\b",
        "",
        normalized,
        flags=re.I,
    )

    normalized = re.sub(r"\s+", " ", normalized).strip(" .?!,")

    time_candidates = []

    for match in re.finditer(r"\b(\d{1,2}(?::\d{2})?)\s*(AM|PM)\b", normalized, flags=re.I):
        candidate = f"{match.group(1)} {match.group(2).upper()}"
        time_candidates.append(candidate)

    for match in re.finditer(
        r"\b(one|two|too|to|three|four|for|five|six|seven|eight|nine|ten|eleven|twelve)\s*(AM|PM)\b",
        normalized,
        flags=re.I,
    ):
        num = word_to_number(match.group(1))
        ampm = match.group(2).upper()

        if num:
            time_candidates.append(f"{num} {ampm}")

    for candidate in reversed(time_candidates):
        candidate = format_booking_time(candidate)

        if is_valid_booking_time(candidate) and is_30_min_interval(candidate):
            return candidate

    if time_candidates:
        return format_booking_time(time_candidates[-1])

    number_word = word_to_number(normalized)

    if number_word:
        return number_word

    number_only = re.search(r"\b(\d{1,2})(?::(\d{2}))?\b", normalized)

    if number_only:
        hour = number_only.group(1)
        minute = number_only.group(2)

        if minute:
            return f"{hour}:{minute}"

        return hour

    return ""


def booking_time_needs_ampm(booking_time: str) -> bool:
    if not booking_time:
        return False

    upper = booking_time.upper()

    if "AM" in upper or "PM" in upper:
        return False

    return bool(re.fullmatch(r"\d{1,2}(?::\d{2})?", booking_time.strip()))


def apply_ampm_to_booking_time(call_details: dict, caller_text: str) -> bool:
    full_time = clean_booking_time(caller_text)

    if full_time and ("AM" in full_time.upper() or "PM" in full_time.upper()):
        return validate_and_store_booking_time(call_details, full_time)

    cleaned = caller_text.lower()
    cleaned = cleaned.replace("p.m.", "pm").replace("p.m", "pm").replace("p m", "pm")
    cleaned = cleaned.replace("a.m.", "am").replace("a.m", "am").replace("a m", "am")

    current_time = call_details.get("booking_time", "").strip()

    if not current_time:
        return False

    if "am" in cleaned or "morning" in cleaned:
        candidate = f"{current_time} AM"
        return validate_and_store_booking_time(call_details, candidate)

    if "pm" in cleaned or "afternoon" in cleaned or "evening" in cleaned or "night" in cleaned:
        candidate = f"{current_time} PM"
        return validate_and_store_booking_time(call_details, candidate)

    return False


def clean_phone_number(text: str) -> str:
    match = re.search(
        r"(\+?1?[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})",
        text,
    )

    if match:
        digits = re.sub(r"\D", "", match.group(1))

        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        if len(digits) == 10:
            return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"

    word_digits = {
        "zero": "0",
        "oh": "0",
        "o": "0",
        "one": "1",
        "two": "2",
        "too": "2",
        "to": "2",
        "three": "3",
        "four": "4",
        "for": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
    }

    tokens = re.findall(r"[A-Za-z]+|\d", text.lower())
    digits = ""

    for token in tokens:
        if token.isdigit():
            digits += token
        elif token in word_digits:
            digits += word_digits[token]

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"

    return ""


def clean_spelled_name(text: str) -> str:
    original = text.strip()

    if not original:
        return ""

    normalized = re.sub(r"\b(dash|hyphen|minus)\b", "-", original, flags=re.I)
    normalized = re.sub(r"\b(space)\b", " ", normalized, flags=re.I)

    has_spelling_trigger = re.search(
        r"\b(spelled|spell|spelt|spelling is|spelled as)\b",
        normalized,
        flags=re.I,
    )

    has_clear_letter_sequence = re.search(r"\b[A-Za-z](?:[\s\-]+[A-Za-z]){1,}\b", normalized)

    if not has_spelling_trigger and not has_clear_letter_sequence:
        return ""

    if has_spelling_trigger:
        spelled_match = re.search(
            r"(?:spelled|spell|spelt|spelling is|spelled as)\s+(.+)",
            normalized,
            flags=re.I,
        )
        segment = spelled_match.group(1) if spelled_match else normalized
    else:
        segment = normalized

    segment = re.sub(
        r"\b(it'?s|it is|actually|my|first|name|is|called|but|the|correct|way|should|be|as|with|extra|an|a)\b",
        " ",
        segment,
        flags=re.I,
    )

    letter_tokens = re.findall(r"\b[A-Za-z]\b", segment)

    if 2 <= len(letter_tokens) <= 20:
        return "".join(letter_tokens).title()

    return ""


def is_valid_first_name(name: str) -> bool:
    name = name.strip()

    if not name or len(name) < 2 or len(name) > 30:
        return False

    if not re.match(r"^[A-Za-z][A-Za-z'\-]*$", name):
        return False

    blocked_words = {
        "Needs", "Need", "Corrected", "Correction", "Wrong", "Right",
        "Verify", "Spelled", "Spell", "Actually", "Phone", "Number",
        "Time", "Booking", "Appointment", "How", "What", "Csv", "Inserted",
        "File", "Other", "Perfect", "Sure", "Make", "Day", "Date",
    }

    return name.title() not in blocked_words


def clean_first_name(text: str) -> str:
    text = text.strip()

    if not text:
        return ""

    lower = text.lower()

    correction_patterns = [
        r"\bchange it to\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bchange my name to\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bchange the name to\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bmake it\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bput\s+([A-Za-z][A-Za-z'\-]*)",
        r"\buse\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bmake sure\s+([A-Za-z][A-Za-z'\-]*)\s+is in",
        r"\bmake sure\s+([A-Za-z][A-Za-z'\-]*)\s+goes in",
        r"\bit should be\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bshould be\s+([A-Za-z][A-Za-z'\-]*)",
    ]

    for pattern in correction_patterns:
        match = re.search(pattern, text, flags=re.I)

        if match:
            candidate = match.group(1).strip(" .!?,'\"")

            if is_valid_first_name(candidate):
                return candidate.title()

    spelled = clean_spelled_name(text)

    if spelled:
        return spelled

    bad_phrases = [
        "needs to be corrected", "need to be corrected", "has to be corrected",
        "is wrong", "was wrong", "not right", "incorrect", "corrected",
        "verify how my name is spelled", "how my name is spelled",
        "how did you spell", "what did you put", "what do you have",
        "can you verify", "could you verify", "with an extra",
    ]

    if any(phrase in lower for phrase in bad_phrases):
        return ""

    patterns = [
        r"\bmy first name is\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bfirst name is\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bmy name is\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bname is\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bi am\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bi'm\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bim\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bit is\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bit's\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bits\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bcall me\s+([A-Za-z][A-Za-z'\-]*)",
        r"\bcalled\s+([A-Za-z][A-Za-z'\-]*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)

        if match:
            candidate = match.group(1).strip(" .!?,'\"").title()

            if is_valid_first_name(candidate):
                return candidate

    before_but = re.split(r"\bbut\b", text, flags=re.I)[0].strip()
    words_before_but = re.findall(r"[A-Za-z][A-Za-z'\-]*", before_but)

    if len(words_before_but) == 1 and is_valid_first_name(words_before_but[0]):
        return words_before_but[0].title()

    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", text)

    ignore_words = {
        "hi", "hello", "hey", "there", "my", "name", "first", "is", "i",
        "am", "im", "it", "its", "yes", "yeah", "yep", "ya", "ok", "okay",
        "uh", "um", "the", "actually", "no", "but", "spelled", "spell",
        "spelling", "before", "how", "did", "you", "verify", "correct",
        "corrected", "needs", "need", "to", "be", "should", "what", "have",
        "put", "with", "extra", "csv", "file", "other", "than", "perfect",
        "nope", "make", "sure", "in", "change", "use", "goes",
    }

    useful_words = [word for word in words if word.lower() not in ignore_words]

    if len(useful_words) == 1 and is_valid_first_name(useful_words[0]):
        return useful_words[0].title()

    return ""


# ---------------------------
# Conversation State Helpers
# ---------------------------
def all_required_details_present(call_details: dict) -> bool:
    return all([
        call_details.get("name"),
        call_details.get("phone_number"),
        call_details.get("booking_day"),
        call_details.get("booking_date"),
        call_details.get("booking_time"),
        not booking_time_needs_ampm(call_details.get("booking_time", "")),
        is_valid_booking_time(call_details.get("booking_time", "")),
        is_30_min_interval(call_details.get("booking_time", "")),
    ])


def next_missing_field(call_details: dict) -> str:
    if not call_details.get("name"):
        return "name"
    if not call_details.get("phone_number"):
        return "phone_number"
    if not call_details.get("booking_day") or not call_details.get("booking_date"):
        return "booking_day"
    if not call_details.get("booking_time"):
        return "booking_time"
    if booking_time_needs_ampm(call_details.get("booking_time", "")):
        return "booking_ampm"
    if not is_valid_booking_time(call_details.get("booking_time", "")):
        return "booking_time"
    if not is_30_min_interval(call_details.get("booking_time", "")):
        return "booking_time"
    return "confirmation"


def missing_field_instruction(call_details: dict) -> str:
    field = next_missing_field(call_details)

    if field == "name":
        return "Do not end the call. Ask exactly: What is your first name?"
    if field == "phone_number":
        return "Do not end the call. Ask exactly: What is your phone number?"
    if field == "booking_day":
        return "Do not end the call. Ask exactly: What day are you coming in? Please choose Monday to Friday within the next two weeks."
    if field == "booking_time":
        return "Do not end the call. Ask exactly: What time are you coming in? Please choose a time between 10:00 AM and 4:30 PM."
    if field == "booking_ampm":
        return f"Do not end the call. Ask exactly: Is that {call_details.get('booking_time', '').strip()} AM or {call_details.get('booking_time', '').strip()} PM?"

    return "Confirm the details again and end with exactly: Is that correct?"


def looks_like_yes(text: str) -> bool:
    cleaned = normalize_text(text)

    question_or_correction_words = [
        "but", "what", "how", "which", "can you", "could you", "do you",
        "is the", "what do you have", "csv", "inserted", "spell",
        "spelled", "change", "wrong",
    ]

    if any(word in cleaned for word in question_or_correction_words):
        return False

    return cleaned in YES_WORDS


def looks_like_no(text: str) -> bool:
    cleaned = normalize_text(text)

    if "perfect" in cleaned or "correct" in cleaned:
        return False

    return cleaned in NO_WORDS or cleaned.startswith("no")


def detect_correction_target(text: str) -> str:
    lower = normalize_text(text)

    if any(word in lower for word in [
        "name", "first name", "spelled", "spell", "change it to",
        "change my name", "make it", "make sure", "csv",
    ]):
        return "name"

    if any(word in lower for word in ["phone", "number", "cell"]):
        return "phone_number"

    if any(word in lower for word in ["day", "date", "today", "tomorrow", "next week", *DAYS]):
        return "booking_day"

    if any(word in lower for word in ["time", "appointment", "coming"]):
        return "booking_time"

    return ""


def text_has_goodbye(text: str) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in GOODBYE_PHRASES)


def extract_transcript_from_response_done(response: dict) -> str:
    text_parts = []

    try:
        output_items = response.get("response", {}).get("output", [])

        for item in output_items:
            for content in item.get("content", []):
                transcript = content.get("transcript")
                text = content.get("text")

                if transcript:
                    text_parts.append(transcript)

                if text:
                    text_parts.append(text)

    except Exception as e:
        print("Could not extract transcript from response.done:", repr(e))

    return " ".join(text_parts).strip()


def detect_next_expected_field(assistant_text: str, current_expected_field: str) -> str:
    lower = normalize_text(assistant_text)

    if "is that am or pm" in lower or "am or pm" in lower:
        return "booking_ampm"

    if "what needs to be corrected" in lower:
        return "correction_target"

    if "correct first name" in lower or "spell your first name" in lower:
        return "correction_name"

    if "correct phone number" in lower:
        return "correction_phone_number"

    if "correct booking day" in lower or "correct day" in lower:
        return "correction_booking_day"

    if "correct booking time" in lower or "correct time" in lower:
        return "correction_booking_time"

    if "is that correct" in lower or "confirm" in lower:
        return "confirmation"

    if "first name" in lower or "your name" in lower:
        return "name"

    if "phone number" in lower or "number" in lower:
        return "phone_number"

    if "what day" in lower or "which day" in lower or "day are you coming" in lower:
        return "booking_day"

    if "what time" in lower or "time" in lower:
        return "booking_time"

    return current_expected_field


def apply_field_update(call_details: dict, field: str, caller_text: str) -> bool:
    if field == "name":
        name = clean_first_name(caller_text)

        if name:
            call_details["name"] = name
            return True

        return False

    if field == "phone_number":
        phone = clean_phone_number(caller_text)

        if phone:
            call_details["phone_number"] = phone
            return True

        return False

    if field == "booking_day":
        day, booking_date, date_error = parse_booking_day_and_date(
            caller_text,
            call_details.get("booking_day", ""),
        )

        if day and booking_date and not date_error:
            call_details["booking_day"] = day
            call_details["booking_date"] = booking_date
            return True

        return False

    if field == "booking_time":
        booking_time = clean_booking_time(caller_text)

        if booking_time:
            return validate_and_store_booking_time(call_details, booking_time)

        return False

    return False


def update_call_details_by_expected_field(call_details: dict, caller_text: str, expected_field: str) -> str:
    text = caller_text.strip()

    if not text:
        return expected_field

    explicit_name = clean_first_name(text)

    if explicit_name and ("name" in normalize_text(text) or expected_field == "name"):
        call_details["name"] = explicit_name

    phone = clean_phone_number(text)

    day, booking_date, date_error = parse_booking_day_and_date(
        text,
        call_details.get("booking_day", ""),
    )

    time_value = ""

    if re.search(r"\b(am|pm|a\.m\.|p\.m\.|morning|afternoon|evening|night)\b", text, flags=re.I):
        time_value = clean_booking_time(text)
    elif expected_field in ["booking_time", "booking_ampm", "correction_booking_time", "correction_booking_day"]:
        time_value = clean_booking_time(text)

    if phone:
        call_details["phone_number"] = phone

    if date_error:
        call_details["booking_day"] = ""
        call_details["booking_date"] = ""
        return "booking_day"

    if day and booking_date:
        call_details["booking_day"] = day
        call_details["booking_date"] = booking_date

    # Very important:
    # If the caller says only "PM" while we are waiting for AM/PM,
    # apply it to the existing time like "3:30" -> "3:30 PM".
    if expected_field == "booking_ampm":
        if apply_ampm_to_booking_time(call_details, text):
            return "confirmation"
        return "booking_ampm"

    if time_value:
        if not validate_and_store_booking_time(call_details, time_value):
            return "booking_time"

    if call_details.get("booking_time") and booking_time_needs_ampm(call_details["booking_time"]):
        return "booking_ampm"

    if expected_field == "confirmation":
        normalized = normalize_text(text)

        if "spell" in normalized or "spelled" in normalized:
            return "correction_name"

        if "csv" in normalized or "sql" in normalized or "database" in normalized:
            target = detect_correction_target(text)
            return f"correction_{target}" if target else "correction_target"

        if "booking day" in normalized or "day" in normalized or "date" in normalized or "next week" in normalized:
            return "correction_booking_day"

        if "booking time" in normalized or "time" in normalized:
            return "correction_booking_time"

        if time_value:
            return "confirmation"

        if looks_like_yes(text):
            return "confirmed" if all_required_details_present(call_details) else next_missing_field(call_details)

        if looks_like_no(text):
            return "correction_target"

        return "confirmation"

    if expected_field == "correction_target":
        target = detect_correction_target(text)
        return f"correction_{target}" if target else "correction_target"

    if expected_field == "correction_name":
        lower = normalize_text(text)

        if "how" in lower and ("spell" in lower or "spelled" in lower):
            return "correction_name"

        if normalize_text(text).startswith("nope") and ("perfect" in lower or "correct" in lower):
            return "confirmation"

        return "confirmation" if apply_field_update(call_details, "name", text) else "correction_name"

    if expected_field == "correction_phone_number":
        return "confirmation" if apply_field_update(call_details, "phone_number", text) else "correction_phone_number"

    if expected_field == "correction_booking_day":
        updated = apply_field_update(call_details, "booking_day", text)

        if time_value:
            if not validate_and_store_booking_time(call_details, time_value):
                return "booking_time"

        if call_details["booking_day"] and call_details["booking_date"] and call_details["booking_time"]:
            return "confirmation"

        return "booking_time" if updated else "correction_booking_day"

    if expected_field == "correction_booking_time":
        updated = apply_field_update(call_details, "booking_time", text)

        if not updated:
            return "correction_booking_time"

        return "booking_ampm" if booking_time_needs_ampm(call_details["booking_time"]) else "confirmation"

    if expected_field == "name":
        return "phone_number" if call_details["name"] else "name"

    if expected_field == "phone_number":
        return "booking_day" if call_details["phone_number"] else "phone_number"

    if expected_field == "booking_day":
        if call_details["booking_day"] and call_details["booking_date"] and call_details["booking_time"]:
            return "confirmation"

        if call_details["booking_day"] and call_details["booking_date"]:
            return "booking_time"

        return "booking_day"

    if expected_field == "booking_time":
        if call_details["booking_time"]:
            return "booking_ampm" if booking_time_needs_ampm(call_details["booking_time"]) else "confirmation"

        return "booking_time"

    return expected_field


# ---------------------------
# FastAPI App
# ---------------------------
app = FastAPI()
initialize_database()


@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio + OpenAI Realtime server is running!"}


@app.get("/appointments", response_class=JSONResponse)
async def get_appointments():
    initialize_database()

    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, phone_number, booking_day, booking_date, booking_time, created_at
        FROM appointments
        ORDER BY booking_date ASC, booking_time ASC
    """)

    appointments = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {"appointments": appointments}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    response = VoiceResponse()

    form = await request.form()
    call_sid = form.get("CallSid", "")
    host = request.url.hostname

    connect = Connect()
    stream = connect.stream(url=f"wss://{host}/media-stream")

    if call_sid:
        stream.parameter(name="call_sid", value=call_sid)

    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


async def end_call_later(call_sid: str):
    await asyncio.sleep(HANGUP_DELAY_SECONDS)

    if not call_sid:
        print("❌ No CallSid found. Cannot end call.")
        return

    if not twilio_client:
        print("❌ Twilio client missing. Cannot end call.")
        return

    try:
        twilio_client.calls(call_sid).update(status="completed")
        print(f"✅ Call ended successfully. CallSid: {call_sid}")

    except Exception as e:
        print("❌ Error ending call:", repr(e))


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    print("\n📞 Client connected")
    await websocket.accept()

    async with websockets.connect(
        f"wss://api.openai.com/v1/realtime?model=gpt-realtime&temperature={TEMPERATURE}",
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
    ) as openai_ws:
        await initialize_session(openai_ws)

        stream_sid = None
        call_sid = None
        latest_media_timestamp = 0
        response_start_timestamp_twilio = None
        last_assistant_item = None
        mark_queue = []
        assistant_transcript = ""
        transcript_lines = []
        expected_field = "name"
        goodbye_detected_for_current_response = False
        audio_done_for_current_response = False
        playback_done_for_current_response = False
        hangup_started = False
        saved_outputs = False

        response_in_progress = False
        pending_exact_message = ""

        call_details = {
            "name": "",
            "phone_number": "",
            "booking_day": "",
            "booking_date": "",
            "booking_time": "",
        }

        def build_confirmation_text(details: dict) -> str:
            return (
                f"Thank you. Let's confirm: your first name is {details['name']}, "
                f"your phone number is {details['phone_number']}, and you're coming in on "
                f"{details['booking_day']} at {details['booking_time']}. Is that correct?"
            )

        async def send_response_create(text: str):
            await openai_ws.send(json.dumps({
                "type": "response.create",
                "response": {
                    "instructions": f"Say exactly this and nothing else: \"{text}\""
                },
            }))

        async def say_exactly(text: str):
            nonlocal pending_exact_message, response_in_progress

            if response_in_progress:
                pending_exact_message = text
                return

            await send_response_create(text)

        async def flush_pending_exact_message():
            nonlocal pending_exact_message, response_in_progress

            if pending_exact_message and not response_in_progress:
                message_to_send = pending_exact_message
                pending_exact_message = ""
                await send_response_create(message_to_send)

        async def force_missing_detail_question():
            field = next_missing_field(call_details)

            if field == "name":
                exact_question = "What is your first name?"
            elif field == "phone_number":
                exact_question = "What is your phone number?"
            elif field == "booking_day":
                exact_question = "What day are you coming in? Please choose Monday to Friday within the next two weeks."
            elif field == "booking_time":
                exact_question = "What time are you coming in? Please choose a time between 10:00 AM and 4:30 PM."
            elif field == "booking_ampm":
                exact_question = f"Is that {call_details.get('booking_time', '').strip()} AM or {call_details.get('booking_time', '').strip()} PM?"
            else:
                exact_question = build_confirmation_text(call_details)

            await say_exactly(exact_question)

        async def force_confirmation():
            await say_exactly(build_confirmation_text(call_details))

        def build_next_assistant_text() -> str:
            field = expected_field

            if field == "confirmed":
                return "Your appointment information has been recorded. Thank you for calling. Goodbye."

            if field == "correction_target":
                return "What needs to be corrected: your first name, phone number, booking day, or booking time?"

            if field == "correction_name":
                current_name = call_details.get("name", "")

                if current_name:
                    return f"Your first name is currently spelled {current_name}. What should the correct first name be?"

                return "What should the correct first name be?"

            if field == "correction_phone_number":
                return "What should the correct phone number be?"

            if field == "correction_booking_day":
                return "What should the correct booking day be? Please choose Monday to Friday within the next two weeks."

            if field == "correction_booking_time":
                return "What should the correct booking time be? Please choose a time between 10:00 AM and 4:30 PM."

            if field == "confirmation" and all_required_details_present(call_details):
                return build_confirmation_text(call_details)

            missing = next_missing_field(call_details)

            if missing == "name":
                return "What is your first name?"

            if missing == "phone_number":
                return "What is your phone number?"

            if missing == "booking_day":
                return "What day are you coming in? Please choose Monday to Friday within the next two weeks."

            if missing == "booking_time":
                return "What time are you coming in? Please choose a time between 10:00 AM and 4:30 PM."

            if missing == "booking_ampm":
                current_time = call_details.get("booking_time", "").strip()
                return f"Is that {current_time} AM or {current_time} PM?"

            return build_confirmation_text(call_details)

        async def maybe_end_call_after_goodbye():
            nonlocal hangup_started, saved_outputs

            if not all_required_details_present(call_details):
                return

            if not is_slot_available(call_details["booking_date"], call_details["booking_time"]):
                print("⚠️ Slot became unavailable before save.")
                call_details["booking_time"] = ""
                call_details["_time_error"] = "That time was just booked. Please choose another available time."
                return

            if (
                goodbye_detected_for_current_response
                and audio_done_for_current_response
                and playback_done_for_current_response
                and not hangup_started
            ):
                hangup_started = True

                print("✅ Goodbye response fully finished and played.")

                if not saved_outputs:
                    save_call_outputs(call_details, transcript_lines)
                    saved_outputs = True

                print(f"📴 Ending call in {HANGUP_DELAY_SECONDS} seconds...")
                asyncio.create_task(end_call_later(call_sid))

        async def receive_from_twilio():
            nonlocal stream_sid, call_sid, latest_media_timestamp
            nonlocal response_start_timestamp_twilio, last_assistant_item
            nonlocal playback_done_for_current_response, saved_outputs

            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    event_type = data.get("event")

                    if event_type == "start":
                        stream_sid = data["start"]["streamSid"]
                        latest_media_timestamp = 0
                        response_start_timestamp_twilio = None
                        last_assistant_item = None

                        custom_params = data["start"].get("customParameters", {})
                        call_sid = custom_params.get("call_sid")

                        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                        print("📞 Call started")
                        print(f"StreamSid: {stream_sid}")
                        print(f"CallSid:   {call_sid}")
                        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

                    elif event_type == "media":
                        latest_media_timestamp = int(data["media"]["timestamp"])

                        if openai_ws.state.name == "OPEN":
                            await openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": data["media"]["payload"],
                            }))

                    elif event_type == "mark":
                        mark_name = data.get("mark", {}).get("name")

                        if mark_queue:
                            mark_queue.pop(0)

                        if mark_name == "assistantAudioDone":
                            playback_done_for_current_response = True
                            await maybe_end_call_after_goodbye()

                    elif event_type == "stop":
                        print("📴 Twilio signaled stop.")

                        if not saved_outputs and hangup_started and all_required_details_present(call_details):
                            save_call_outputs(call_details, transcript_lines)
                            saved_outputs = True

                        break

            except WebSocketDisconnect:
                print("📴 Twilio websocket disconnected.")

                if openai_ws.state.name == "OPEN":
                    await openai_ws.close()

            except Exception as e:
                print("❌ Error receiving from Twilio:", repr(e))

        async def send_to_twilio():
            nonlocal response_start_timestamp_twilio, last_assistant_item
            nonlocal assistant_transcript, expected_field
            nonlocal goodbye_detected_for_current_response
            nonlocal audio_done_for_current_response
            nonlocal playback_done_for_current_response
            nonlocal response_in_progress

            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    event_type = response.get("type")

                    if event_type == "error":
                        print("❌ OpenAI error:", json.dumps(response, indent=2))
                        continue

                    if event_type == "conversation.item.input_audio_transcription.completed":
                        caller_text = response.get("transcript", "").strip()

                        if caller_text:
                            print(f"👤 Caller: {caller_text}")
                            transcript_lines.append(f"Caller: {caller_text}")

                            old_details = call_details.copy()
                            old_expected = expected_field

                            expected_field = update_call_details_by_expected_field(
                                call_details,
                                caller_text,
                                expected_field,
                            )

                            for key in ["name", "phone_number", "booking_day", "booking_date", "booking_time"]:
                                if old_details[key] and not call_details[key] and key != "booking_time":
                                    print(f"⚠️ Prevented accidental clearing of {key}.")
                                    call_details[key] = old_details[key]
                                    expected_field = old_expected

                            correction_states = [
                                "correction_target",
                                "correction_name",
                                "correction_phone_number",
                                "correction_booking_day",
                                "correction_booking_time",
                                "confirmation",
                                "confirmed",
                            ]

                            if expected_field not in correction_states:
                                expected_field = next_missing_field(call_details)

                            time_error = call_details.pop("_time_error", "")
                            printable_details = {key: value for key, value in call_details.items() if not key.startswith("_")}
                            print("📋 Current details:", {**printable_details, "expected_field": expected_field})

                            if time_error:
                                expected_field = "booking_time"
                                await say_exactly(time_error)
                            else:
                                await say_exactly(build_next_assistant_text())

                    elif event_type == "conversation.item.input_audio_transcription.failed":
                        print("⚠️ Caller transcription failed.")

                    elif event_type == "response.created":
                        response_in_progress = True
                        assistant_transcript = ""
                        goodbye_detected_for_current_response = False
                        audio_done_for_current_response = False
                        playback_done_for_current_response = False

                    elif event_type == "response.output_audio.delta":
                        audio_payload = response.get("delta")

                        if audio_payload and stream_sid:
                            await websocket.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": audio_payload},
                            })

                        item_id = response.get("item_id")

                        if item_id and item_id != last_assistant_item:
                            response_start_timestamp_twilio = latest_media_timestamp
                            last_assistant_item = item_id

                    elif event_type == "response.output_audio_transcript.delta":
                        assistant_transcript += response.get("delta", "")

                    elif event_type == "response.output_audio_transcript.done":
                        pass

                    elif event_type == "response.output_audio.done":
                        audio_done_for_current_response = True

                        if stream_sid:
                            await send_mark(websocket, stream_sid, "assistantAudioDone")

                        await maybe_end_call_after_goodbye()

                    elif event_type == "response.done":
                        response_in_progress = False

                        done_transcript = extract_transcript_from_response_done(response)

                        if not assistant_transcript.strip() and done_transcript:
                            assistant_transcript = done_transcript

                        clean_transcript = assistant_transcript.strip()

                        if clean_transcript:
                            print(f"🤖 Assistant: {clean_transcript}")
                            transcript_lines.append(f"Assistant: {clean_transcript}")

                        detected_expected_field = detect_next_expected_field(clean_transcript, expected_field)

                        if expected_field == "confirmed":
                            expected_field = "confirmed"
                        elif detected_expected_field in [
                            "correction_target",
                            "correction_name",
                            "correction_phone_number",
                            "correction_booking_day",
                            "correction_booking_time",
                            "confirmation",
                        ]:
                            expected_field = detected_expected_field
                        else:
                            expected_field = next_missing_field(call_details)

                        if text_has_goodbye(clean_transcript):
                            if all_required_details_present(call_details):
                                goodbye_detected_for_current_response = True
                                print("✅ Goodbye detected. Waiting for final audio playback confirmation.")
                            else:
                                print("⚠️ Goodbye ignored because details are incomplete.")
                                expected_field = next_missing_field(call_details)
                                await force_missing_detail_question()

                        assistant_transcript = ""
                        await maybe_end_call_after_goodbye()
                        await flush_pending_exact_message()

                    elif event_type == "input_audio_buffer.speech_started":
                        print("🎙️ Caller started speaking")

                        if last_assistant_item:
                            await handle_speech_started_event()

                    elif event_type == "input_audio_buffer.speech_stopped":
                        print("🔇 Caller stopped speaking")

            except Exception as e:
                print("❌ Error sending to Twilio:", repr(e))

        async def handle_speech_started_event():
            nonlocal response_start_timestamp_twilio, last_assistant_item

            if mark_queue and response_start_timestamp_twilio is not None:
                elapsed_time = latest_media_timestamp - response_start_timestamp_twilio

                if last_assistant_item:
                    await openai_ws.send(json.dumps({
                        "type": "conversation.item.truncate",
                        "item_id": last_assistant_item,
                        "content_index": 0,
                        "audio_end_ms": elapsed_time,
                    }))

                if stream_sid:
                    await websocket.send_json({
                        "event": "clear",
                        "streamSid": stream_sid,
                    })

                mark_queue.clear()
                last_assistant_item = None
                response_start_timestamp_twilio = None

                print("⏭️ Assistant interrupted and audio cleared.")

        async def send_mark(connection: WebSocket, sid: str, name: str):
            if not sid:
                return

            await connection.send_json({
                "event": "mark",
                "streamSid": sid,
                "mark": {"name": name},
            })

            mark_queue.append(name)

        await asyncio.gather(receive_from_twilio(), send_to_twilio())


async def initialize_session(openai_ws):
    session_update = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": "gpt-realtime",
            "output_modalities": ["audio"],
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.75,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 700,
                        "create_response": False,
                        "interrupt_response": True,
                    },
                },
                "output": {
                    "format": {"type": "audio/pcmu"},
                    "voice": VOICE,
                },
            },
            "instructions": build_system_message(),
        },
    }

    print("⚙️ Sending OpenAI session update...")

    await openai_ws.send(json.dumps(session_update))

    await openai_ws.send(json.dumps({
        "type": "response.create",
        "response": {
            "instructions": "Speak English only. Say exactly this and nothing else: \"Hi, this is Team 12's AI Barber shop assistant. I can help collect your appointment information. What is your first name?\""
        },
    }))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)