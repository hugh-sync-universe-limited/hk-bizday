"""HTTP routing for hk-bizday. Bind only to 127.0.0.1 when serving locally."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .calendar import DEFAULT_PROFILE, CalendarError, DISCLAIMER, HolidayCalendar


def handle_request(calendar: HolidayCalendar, method: str, path: str) -> tuple[int, dict]:
    if method != "GET":
        return HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method not allowed"}
    parsed = urlparse(path)
    query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
    profile = query.get("profile", DEFAULT_PROFILE)
    try:
        if parsed.path == "/v0/day":
            if "date" not in query:
                raise CalendarError("date is required")
            return HTTPStatus.OK, calendar.day_payload(query["date"], profile)
        if parsed.path == "/v0/holidays":
            if "from" not in query or "to" not in query:
                raise CalendarError("from and to are required")
            return HTTPStatus.OK, calendar.holidays_payload(query["from"], query["to"], profile)
        if parsed.path == "/v0/add-business-days":
            if "date" not in query or "days" not in query:
                raise CalendarError("date and days are required")
            return HTTPStatus.OK, calendar.add_business_days_payload(
                query["date"], query["days"], profile
            )
    except CalendarError as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": str(exc),
            "profile": profile,
            "coverage": {
                "from": calendar.coverage_from.isoformat(),
                "to": calendar.coverage_to.isoformat(),
            },
            "source": calendar.source_block,
            "disclaimer": DISCLAIMER,
        }
    return HTTPStatus.NOT_FOUND, {"error": "not found"}


class CalendarHandler(BaseHTTPRequestHandler):
    calendar: HolidayCalendar

    def log_message(self, format, *args):
        return

    def _write_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        status, payload = handle_request(self.calendar, "GET", self.path)
        self._write_json(status, payload)


def serve(calendar: HolidayCalendar, host: str = "127.0.0.1", port: int = 8000) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise CalendarError("server may only bind to localhost")

    class BoundHandler(CalendarHandler):
        pass

    BoundHandler.calendar = calendar
    httpd = ThreadingHTTPServer((host, port), BoundHandler)
    print(f"hk-bizday listening on http://{host}:{port} (localhost only)")
    httpd.serve_forever()
