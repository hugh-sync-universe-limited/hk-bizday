import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_holidays  # noqa: E402

MINIMAL_JSON = b"""{
  "vcalendar": [{
    "prodid": "-//test//EN",
    "vevent": [{
      "dtstart": ["20260101", {"value": "DATE"}],
      "dtend": ["20260102", {"value": "DATE"}],
      "summary": "The first day of January"
    }]
  }]
}
"""


class TestUpdateHolidays(unittest.TestCase):
    def test_refuses_non_official_url(self):
        with self.assertRaises(update_holidays.UpdateError):
            update_holidays.fetch_official_file("https://www.gov.hk/en/about/abouthk/holiday/2026.htm")
        with self.assertRaises(update_holidays.UpdateError):
            update_holidays.fetch_official_file("https://www.labour.gov.hk/eng/news/holiday.htm")
        with self.assertRaises(update_holidays.UpdateError):
            update_holidays.fetch_official_file("https://www.1823.gov.hk/en/")

    def test_accepts_official_url_constant(self):
        self.assertTrue(
            update_holidays.is_allowed_url(update_holidays.OFFICIAL_FILE_URL)
        )

    def test_updates_source_date_from_localhost_fixture(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                body = MINIMAL_JSON
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Last-Modified", "Tue, 17 Nov 2026 00:00:00 GMT")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/en.json"
            import tempfile
            from datetime import datetime
            from zoneinfo import ZoneInfo

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                data_path = tmp_path / "hk_public_holidays_en.json"
                source_path = tmp_path / "SOURCE.json"
                source_txt = tmp_path / "SOURCE.txt"
                meta = {
                    "dataset": "Hong Kong Public Holidays Data",
                    "dataset_url": "https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal",
                    "resource_url": "https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal/resource/7ce98bb9-6330-414d-83fa-48aa4f253789",
                    "file_url": url,
                    "file_name": "hk_public_holidays_en.json",
                    "retrieved_on": "2026-01-01",
                    "retrieved_timezone": "Asia/Hong_Kong",
                    "http_last_modified": "old",
                    "terms_url": "https://data.gov.hk/en/terms-and-conditions",
                    "attribution": "Data from DATA.GOV.HK, the Government of the Hong Kong Special Administrative Region, the Digital Policy Office and 1823.",
                }
                source_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                updated = update_holidays.update_local_files(
                    source_path=source_path,
                    data_path=data_path,
                    source_txt_path=source_txt,
                    now=datetime(2026, 11, 17, tzinfo=ZoneInfo("Asia/Hong_Kong")),
                    allow_localhost=True,
                )
                self.assertEqual(updated["retrieved_on"], "2026-11-17")
                self.assertEqual(
                    updated["http_last_modified"], "Tue, 17 Nov 2026 00:00:00 GMT"
                )
                self.assertTrue(data_path.exists())
                payload = json.loads(data_path.read_bytes().decode("utf-8-sig"))
                self.assertEqual(len(payload["vcalendar"][0]["vevent"]), 1)
                text = source_txt.read_text(encoding="utf-8")
                self.assertIn("Retrieved on: 2026-11-17 (Asia/Hong_Kong)", text)
                self.assertIn("https://data.gov.hk/en/terms-and-conditions", text)
        finally:
            server.shutdown()
            server.server_close()

    def test_uses_template_when_source_json_missing(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                body = MINIMAL_JSON
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Last-Modified", "Tue, 17 Nov 2026 00:00:00 GMT")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/en.json"
            import tempfile
            from datetime import datetime
            from zoneinfo import ZoneInfo

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                data_path = tmp_path / "hk_public_holidays_en.json"
                source_path = tmp_path / "SOURCE.json"
                source_txt = tmp_path / "SOURCE.txt"
                template_path = tmp_path / "SOURCE.template.json"
                template_meta = {
                    "dataset": "Hong Kong Public Holidays Data",
                    "dataset_url": "https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal",
                    "resource_url": "https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal/resource/7ce98bb9-6330-414d-83fa-48aa4f253789",
                    "file_url": url,
                    "file_name": "hk_public_holidays_en.json",
                    "retrieved_on": None,
                    "retrieved_timezone": "Asia/Hong_Kong",
                    "http_last_modified": None,
                    "terms_url": "https://data.gov.hk/en/terms-and-conditions",
                    "attribution": "Data from DATA.GOV.HK, the Government of the Hong Kong Special Administrative Region, the Digital Policy Office and 1823.",
                }
                template_bytes = json.dumps(template_meta, indent=2).encode("utf-8")
                template_path.write_bytes(template_bytes)
                self.assertFalse(source_path.exists())
                updated = update_holidays.update_local_files(
                    source_path=source_path,
                    data_path=data_path,
                    source_txt_path=source_txt,
                    now=datetime(2026, 11, 17, tzinfo=ZoneInfo("Asia/Hong_Kong")),
                    allow_localhost=True,
                )
                self.assertEqual(updated["retrieved_on"], "2026-11-17")
                self.assertTrue(source_path.exists())
                self.assertTrue(data_path.exists())
                self.assertEqual(template_path.read_bytes(), template_bytes)
                written = json.loads(source_path.read_text(encoding="utf-8"))
                self.assertEqual(written["retrieved_on"], "2026-11-17")
                self.assertEqual(
                    written["http_last_modified"], "Tue, 17 Nov 2026 00:00:00 GMT"
                )
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
