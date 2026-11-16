"""Load official DATA.GOV.HK holiday data and answer business-day queries."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

DEFAULT_PROFILE = "weekday_ex_general_holidays"
TIMEZONE = "Asia/Hong_Kong"
DISCLAIMER = (
    "Not a government service. Not legal advice. "
    "The profile is a conventional weekday calendar, not an official legal definition. "
    "Does not cover statutory holidays or weather-related work arrangements."
)
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = PACKAGE_ROOT / "data" / "hk_public_holidays_en.json"
DEFAULT_SOURCE_FILE = PACKAGE_ROOT / "data" / "SOURCE.json"


class CalendarError(ValueError):
    """Invalid input or a date outside the official file's coverage."""


def _parse_ical_date(value) -> date:
    raw = value[0] if isinstance(value, list) else value
    return date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))


def _parse_iso_date(text: str, field: str = "date") -> date:
    if not isinstance(text, str):
        raise CalendarError(f"{field} must be a YYYY-MM-DD string")
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise CalendarError(f"{field} must be a valid YYYY-MM-DD date") from exc
    return parsed



def _parse_non_negative_int(value, field: str = "days") -> int:
    if isinstance(value, bool) or value is None:
        raise CalendarError(f"{field} must be an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
    else:
        raise CalendarError(f"{field} must be an integer")
    if number < 0:
        raise CalendarError(f"{field} must be zero or a positive integer")
    return number


class HolidayCalendar:
    def __init__(self, data_path: Path, source_meta: dict):
        self.data_path = Path(data_path)
        self.source_meta = source_meta
        self.holidays: dict[date, str] = {}
        with self.data_path.open(encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        try:
            events = payload["vcalendar"][0]["vevent"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CalendarError("Official holiday file is missing vcalendar/vevent data") from exc
        for event in events:
            start = _parse_ical_date(event["dtstart"])
            end = _parse_ical_date(event["dtend"])
            name = event.get("summary")
            cursor = start
            while cursor < end:
                self.holidays[cursor] = name
                cursor += timedelta(days=1)
        if not self.holidays:
            raise CalendarError("Official holiday file contained no events")
        years = {day.year for day in self.holidays}
        self.coverage_from = date(min(years), 1, 1)
        self.coverage_to = date(max(years), 12, 31)

    @property
    def source_block(self) -> dict:
        meta = self.source_meta
        return {
            "dataset": meta.get("dataset", "Hong Kong Public Holidays Data"),
            "url": meta.get("dataset_url", "https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal"),
            "resource_url": meta.get("resource_url"),
            "file_url": meta.get("file_url"),
            "retrieved_on": meta.get("retrieved_on"),
            "attribution": meta.get(
                "attribution",
                "Data from DATA.GOV.HK, the Government of the Hong Kong Special Administrative Region, the Digital Policy Office and 1823.",
            ),
        }

    def _coverage(self) -> dict:
        return {
            "from": self.coverage_from.isoformat(),
            "to": self.coverage_to.isoformat(),
        }

    def _common(self, profile: str) -> dict:
        return {
            "timezone": TIMEZONE,
            "profile": profile,
            "coverage": self._coverage(),
            "source": self.source_block,
            "disclaimer": DISCLAIMER,
        }

    def _require_profile(self, profile: str | None) -> str:
        name = profile or DEFAULT_PROFILE
        if name != DEFAULT_PROFILE:
            raise CalendarError(f"unknown profile: {name}")
        return name

    def _require_in_coverage(self, day: date) -> None:
        if day < self.coverage_from or day > self.coverage_to:
            raise CalendarError(
                f"date {day.isoformat()} is outside coverage "
                f"{self.coverage_from.isoformat()} to {self.coverage_to.isoformat()}"
            )

    def is_sunday(self, day: date) -> bool:
        return day.weekday() == 6

    def gazetted_name(self, day: date) -> str | None:
        return self.holidays.get(day)

    def is_gazetted_general_holiday(self, day: date) -> bool:
        return day in self.holidays

    def is_business_day(self, day: date, profile: str = DEFAULT_PROFILE) -> bool:
        self._require_profile(profile)
        if self.is_sunday(day) or self.is_gazetted_general_holiday(day):
            return False
        return day.weekday() < 5

    def day_payload(self, date_text: str, profile: str | None = None) -> dict:
        profile = self._require_profile(profile)
        day = _parse_iso_date(date_text, "date")
        self._require_in_coverage(day)
        return {
            "date": day.isoformat(),
            **self._common(profile),
            "is_sunday": self.is_sunday(day),
            "is_gazetted_general_holiday": self.is_gazetted_general_holiday(day),
            "holiday_name": self.gazetted_name(day),
            "is_business_day": self.is_business_day(day, profile),
        }

    def holidays_payload(
        self,
        from_text: str,
        to_text: str,
        profile: str | None = None,
    ) -> dict:
        profile = self._require_profile(profile)
        start = _parse_iso_date(from_text, "from")
        end = _parse_iso_date(to_text, "to")
        if end < start:
            raise CalendarError("to must be on or after from")
        self._require_in_coverage(start)
        self._require_in_coverage(end)
        holidays = [
            {"date": day.isoformat(), "holiday_name": name}
            for day, name in sorted(self.holidays.items())
            if start <= day <= end
        ]
        return {
            "from": start.isoformat(),
            "to": end.isoformat(),
            **self._common(profile),
            "count": len(holidays),
            "holidays": holidays,
        }

    def add_business_days_payload(
        self,
        date_text: str,
        days,
        profile: str | None = None,
    ) -> dict:
        profile = self._require_profile(profile)
        start = _parse_iso_date(date_text, "date")
        offset = _parse_non_negative_int(days, "days")
        self._require_in_coverage(start)
        cursor = start
        remaining = offset
        # Guard against running past coverage if too many days are requested.
        safety = 0
        while remaining > 0:
            cursor += timedelta(days=1)
            safety += 1
            if cursor > self.coverage_to:
                raise CalendarError(
                    f"result would fall outside coverage "
                    f"{self.coverage_from.isoformat()} to {self.coverage_to.isoformat()}"
                )
            if safety > 4000:
                raise CalendarError("add-business-days exceeded internal step limit")
            if self.is_business_day(cursor, profile):
                remaining -= 1
        return {
            "date": start.isoformat(),
            "days": offset,
            "result_date": cursor.isoformat(),
            **self._common(profile),
            "is_sunday": self.is_sunday(cursor),
            "is_gazetted_general_holiday": self.is_gazetted_general_holiday(cursor),
            "holiday_name": self.gazetted_name(cursor),
            "is_business_day": self.is_business_day(cursor, profile),
        }


def load_default_calendar(
    data_path: Path | None = None,
    source_path: Path | None = None,
) -> HolidayCalendar:
    source_file = Path(source_path) if source_path else DEFAULT_SOURCE_FILE
    with source_file.open(encoding="utf-8") as handle:
        source_meta = json.load(handle)
    return HolidayCalendar(Path(data_path) if data_path else DEFAULT_DATA_FILE, source_meta)
