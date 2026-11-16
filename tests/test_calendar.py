import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hk_bizday.calendar import (  # noqa: E402
    DEFAULT_PROFILE,
    DISCLAIMER,
    CalendarError,
    load_default_calendar,
)
from hk_bizday.httpapi import handle_request  # noqa: E402

DATA_FILE = ROOT / "data" / "hk_public_holidays_en.json"


def official_holidays():
    with DATA_FILE.open(encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    holidays = {}
    for event in payload["vcalendar"][0]["vevent"]:
        raw = event["dtstart"][0]
        day = date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
        holidays[day] = event.get("summary")
    return holidays


class TestHkBizday(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = load_default_calendar()
        cls.official = official_holidays()

    def test_required_fields_on_day_payload(self):
        payload = self.calendar.day_payload("2026-11-17")
        self.assertEqual(payload["profile"], DEFAULT_PROFILE)
        self.assertEqual(payload["coverage"], {"from": "2025-01-01", "to": "2027-12-31"})
        self.assertEqual(
            payload["source"]["url"],
            "https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal",
        )
        with (ROOT / "data" / "SOURCE.json").open(encoding="utf-8") as handle:
            source_meta = json.load(handle)
        retrieved = payload["source"]["retrieved_on"]
        self.assertIsInstance(retrieved, str)
        self.assertRegex(retrieved, r"^\d{4}-\d{2}-\d{2}$")
        date.fromisoformat(retrieved)
        self.assertEqual(retrieved, source_meta["retrieved_on"])
        self.assertIn("DATA.GOV.HK", payload["source"]["attribution"])
        self.assertEqual(payload["disclaimer"], DISCLAIMER)
        self.assertIn("Not a government service", payload["disclaimer"])
        self.assertIn("Not legal advice", payload["disclaimer"])
        self.assertIn("statutory holidays", payload["disclaimer"])
        self.assertIn("weather-related work arrangements", payload["disclaimer"])

    def test_gazetted_holidays_2025_to_2027_parse_correctly(self):
        self.assertEqual(len(self.official), 51)
        counts = {2025: 0, 2026: 0, 2027: 0}
        for day, name in self.official.items():
            counts[day.year] += 1
            payload = self.calendar.day_payload(day.isoformat())
            self.assertTrue(payload["is_gazetted_general_holiday"], day)
            self.assertEqual(payload["holiday_name"], name)
            self.assertFalse(payload["is_business_day"], day)
        self.assertEqual(counts, {2025: 17, 2026: 17, 2027: 17})
        listed = self.calendar.holidays_payload("2025-01-01", "2027-12-31")
        self.assertEqual(listed["count"], 51)
        self.assertEqual(
            {(item["date"], item["holiday_name"]) for item in listed["holidays"]},
            {(day.isoformat(), name) for day, name in self.official.items()},
        )
        self.assertEqual(listed["profile"], DEFAULT_PROFILE)
        self.assertEqual(listed["source"]["url"], payload["source"]["url"])
        self.assertEqual(listed["disclaimer"], DISCLAIMER)

    def test_sundays_are_not_business_days_under_default_profile(self):
        # Sundays in coverage that are not themselves gazetted holidays.
        sundays = [
            date(2025, 1, 5),
            date(2026, 4, 5),  # Easter Sunday / Ching Ming, not in gazetted file
            date(2026, 11, 15),
            date(2026, 12, 27),
            date(2027, 2, 7),
            date(2027, 12, 26),
        ]
        for day in sundays:
            self.assertEqual(day.weekday(), 6, day)
            self.assertNotIn(day, self.official)
            payload = self.calendar.day_payload(day.isoformat())
            self.assertTrue(payload["is_sunday"])
            self.assertFalse(payload["is_gazetted_general_holiday"])
            self.assertIsNone(payload["holiday_name"])
            self.assertFalse(payload["is_business_day"])

        # Every Sunday in 2026 is a non-business day under the default profile.
        cursor = date(2026, 1, 1)
        while cursor.year == 2026:
            if cursor.weekday() == 6:
                payload = self.calendar.day_payload(cursor.isoformat())
                self.assertTrue(payload["is_sunday"], cursor)
                self.assertFalse(payload["is_business_day"], cursor)
            cursor += timedelta(days=1)

    def test_known_2026_dates(self):
        known = {
            "2026-01-01": ("The first day of January", False),
            "2026-02-17": ("Lunar New Year’s Day", False),
            "2026-02-18": ("The second day of Lunar New Year", False),
            "2026-02-19": ("The third day of Lunar New Year", False),
            "2026-04-03": ("Good Friday", False),
            "2026-04-04": ("The day following Good Friday", False),
            "2026-04-06": ("The day following Ching Ming Festival", False),
            "2026-04-07": ("The day following Easter Monday", False),
            "2026-05-01": ("Labour Day", False),
            "2026-05-25": ("The day following the Birthday of the Buddha", False),
            "2026-06-19": ("Tuen Ng Festival", False),
            "2026-07-01": (
                "Hong Kong Special Administrative Region Establishment Day",
                False,
            ),
            "2026-09-26": ("The day following the Chinese Mid-Autumn Festival", False),
            "2026-10-01": ("National Day", False),
            "2026-10-19": ("The day following Chung Yeung Festival", False),
            "2026-12-25": ("Christmas Day", False),
            "2026-12-26": ("The first weekday after Christmas Day", False),
            "2026-11-17": (None, True),  # Tuesday
            "2026-11-16": (None, True),  # Monday
            "2026-11-14": (None, False),  # Saturday, not gazetted
        }
        for date_text, (name, is_business) in known.items():
            payload = self.calendar.day_payload(date_text)
            self.assertEqual(payload["holiday_name"], name, date_text)
            self.assertEqual(payload["is_gazetted_general_holiday"], name is not None, date_text)
            self.assertEqual(payload["is_business_day"], is_business, date_text)

    def test_add_business_days(self):
        cases = {
            ("2026-11-17", 0): "2026-11-17",
            ("2026-11-17", 3): "2026-11-20",
            ("2026-11-20", 1): "2026-11-23",  # Friday + 1 skips weekend
            ("2026-04-02", 1): "2026-04-08",  # Thu before Easter/Ching Ming block
            ("2026-12-24", 1): "2026-12-28",  # Thu before Christmas block
            ("2026-02-16", 1): "2026-02-20",  # Mon before Lunar New Year
        }
        for (start, days), expected in cases.items():
            payload = self.calendar.add_business_days_payload(start, days)
            self.assertEqual(payload["result_date"], expected, (start, days))
            self.assertEqual(payload["days"], days)
            self.assertEqual(payload["profile"], DEFAULT_PROFILE)
            self.assertEqual(payload["disclaimer"], DISCLAIMER)
            self.assertIn("DATA.GOV.HK", payload["source"]["attribution"])
            self.assertTrue(payload["is_business_day"] or days == 0 and start == expected)

        # String days from HTTP/CLI should work the same way.
        self.assertEqual(
            self.calendar.add_business_days_payload("2026-11-17", "3")["result_date"],
            "2026-11-20",
        )

    def test_http_and_cli_shapes(self):
        status, payload = handle_request(
            self.calendar, "GET", "/v0/day?date=2026-11-17&profile=weekday_ex_general_holidays"
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["is_business_day"])
        self.assertEqual(payload["disclaimer"], DISCLAIMER)
        self.assertEqual(payload["coverage"]["from"], "2025-01-01")

        status, payload = handle_request(
            self.calendar, "GET", "/v0/add-business-days?date=2026-04-02&days=1"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["result_date"], "2026-04-08")

        status, payload = handle_request(
            self.calendar, "GET", "/v0/holidays?from=2026-01-01&to=2026-12-31"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["count"], 17)
        self.assertEqual(payload["disclaimer"], DISCLAIMER)

        from hk_bizday.cli import main
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["day", "--date", "2026-12-25"])
        self.assertEqual(code, 0)
        cli_payload = json.loads(buf.getvalue())
        self.assertEqual(cli_payload["holiday_name"], "Christmas Day")
        self.assertFalse(cli_payload["is_business_day"])
        self.assertEqual(cli_payload["disclaimer"], DISCLAIMER)


if __name__ == "__main__":
    unittest.main()
