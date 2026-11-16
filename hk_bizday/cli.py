"""Command-line interface for hk-bizday."""

from __future__ import annotations

import argparse
import json
import sys

from .calendar import DEFAULT_PROFILE, CalendarError, DISCLAIMER, load_default_calendar
from .httpapi import serve


def _print_json(payload: dict, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hk-bizday",
        description="Hong Kong gazetted general holiday and conventional business-day calendar.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    day = sub.add_parser("day", help="Look up one date")
    day.add_argument("--date", required=True, help="YYYY-MM-DD")
    day.add_argument("--profile", default=DEFAULT_PROFILE)

    holidays = sub.add_parser("holidays", help="List gazetted general holidays in a range")
    holidays.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    holidays.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    holidays.add_argument("--profile", default=DEFAULT_PROFILE)

    add = sub.add_parser("add-business-days", help="Add business days under the named profile")
    add.add_argument("--date", required=True, help="YYYY-MM-DD")
    add.add_argument("--days", required=True, help="Zero or a positive integer")
    add.add_argument("--profile", default=DEFAULT_PROFILE)

    server = sub.add_parser("serve", help="Serve the HTTP API on localhost only")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    calendar = load_default_calendar()
    try:
        if args.command == "day":
            return _print_json(calendar.day_payload(args.date, args.profile))
        if args.command == "holidays":
            return _print_json(
                calendar.holidays_payload(args.date_from, args.date_to, args.profile)
            )
        if args.command == "add-business-days":
            return _print_json(
                calendar.add_business_days_payload(args.date, args.days, args.profile)
            )
        if args.command == "serve":
            serve(calendar, host=args.host, port=args.port)
            return 0
    except CalendarError as exc:
        return _print_json(
            {
                "error": str(exc),
                "profile": getattr(args, "profile", DEFAULT_PROFILE),
                "coverage": {
                    "from": calendar.coverage_from.isoformat(),
                    "to": calendar.coverage_to.isoformat(),
                },
                "source": calendar.source_block,
                "disclaimer": DISCLAIMER,
            },
            2,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
