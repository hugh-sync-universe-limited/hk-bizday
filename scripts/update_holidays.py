#!/usr/bin/env python3
"""Refresh the local holiday JSON from the official DATA.GOV.HK file URL only.

Does not scrape GovHK, 1823, or Labour Department website pages.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "SOURCE.json"
DEFAULT_SOURCE_TEMPLATE = ROOT / "data" / "SOURCE.template.json"
DEFAULT_DATA = ROOT / "data" / "hk_public_holidays_en.json"
DEFAULT_SOURCE_TXT = ROOT / "data" / "SOURCE.txt"
OFFICIAL_FILE_URL = "https://www.1823.gov.hk/common/ical/en.json"
HONG_KONG = ZoneInfo("Asia/Hong_Kong")
USER_AGENT = "hk-bizday-update/0.1"


class UpdateError(ValueError):
    """The official file could not be fetched or was not valid holiday JSON."""


def today_hong_kong(now: datetime | None = None) -> str:
    current = now or datetime.now(HONG_KONG)
    if current.tzinfo is None:
        current = current.replace(tzinfo=HONG_KONG)
    return current.astimezone(HONG_KONG).date().isoformat()


def is_allowed_url(url: str, *, allow_localhost: bool = False) -> bool:
    if url == OFFICIAL_FILE_URL:
        return True
    if not allow_localhost:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def source_template_path(source_path: Path) -> Path:
    if source_path == DEFAULT_SOURCE:
        return DEFAULT_SOURCE_TEMPLATE
    return source_path.parent / "SOURCE.template.json"


def resolve_source_read_path(source_path: Path) -> Path:
    """Read SOURCE.json if present; otherwise use SOURCE.template.json.

    The template is never written. Generated metadata goes to source_path.
    """
    if source_path.exists():
        return source_path
    template = source_template_path(source_path)
    if template.exists():
        return template
    raise UpdateError(
        f"{source_path} not found, and no SOURCE.template.json to use instead"
    )


def load_source(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_holiday_json(raw: bytes) -> dict:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("downloaded file is not valid UTF-8 JSON") from exc
    try:
        events = payload["vcalendar"][0]["vevent"]
    except (KeyError, IndexError, TypeError) as exc:
        raise UpdateError("downloaded file is missing vcalendar/vevent data") from exc
    if not isinstance(events, list) or not events:
        raise UpdateError("downloaded file contains no holiday events")
    for event in events:
        if "dtstart" not in event:
            raise UpdateError("a vevent is missing dtstart")
    return payload


def fetch_official_file(url: str, *, allow_localhost: bool = False) -> tuple[bytes, str | None]:
    if not is_allowed_url(url, allow_localhost=allow_localhost):
        raise UpdateError(
            "refusing to fetch a URL that is not the official DATA.GOV.HK holiday "
            f"file URL ({OFFICIAL_FILE_URL})"
        )
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                last_modified = response.headers.get("Last-Modified")
                data = response.read()
            break
        except URLError as exc:
            last_error = exc
    else:
        raise UpdateError(f"failed to download official file: {last_error}") from last_error
    validate_holiday_json(data)
    return data, last_modified


def render_source_txt(meta: dict) -> str:
    return (
        f"{meta['dataset']}\n"
        f"Retrieved on: {meta['retrieved_on']} ({meta['retrieved_timezone']})\n"
        "\n"
        "This file was obtained as the official English JSON resource listed on "
        "the DATA.GOV.HK dataset page. It was not scraped from GovHK, 1823, or "
        "Labour Department website pages for redistribution.\n"
        "\n"
        "DATA.GOV.HK dataset:\n"
        f"{meta['dataset_url']}\n"
        "\n"
        "English resource page:\n"
        f"{meta['resource_url']}\n"
        "\n"
        "Official file URL listed on DATA.GOV.HK:\n"
        f"{meta['file_url']}\n"
        "\n"
        f"Local file: data/{meta['file_name']}\n"
        f"HTTP Last-Modified of the downloaded file: {meta.get('http_last_modified') or '(not provided)'}\n"
        "\n"
        "Terms of use:\n"
        f"{meta['terms_url']}\n"
        "\n"
        "Attribution:\n"
        f"{meta['attribution']}\n"
    )


def write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def update_local_files(
    *,
    source_path: Path = DEFAULT_SOURCE,
    data_path: Path = DEFAULT_DATA,
    source_txt_path: Path = DEFAULT_SOURCE_TXT,
    now: datetime | None = None,
    allow_localhost: bool = False,
) -> dict:
    read_path = resolve_source_read_path(source_path)
    meta = load_source(read_path)
    url = meta.get("file_url")
    if not url:
        raise UpdateError("source metadata is missing file_url")
    raw, last_modified = fetch_official_file(url, allow_localhost=allow_localhost)
    write_atomic(data_path, raw)
    meta["retrieved_on"] = today_hong_kong(now)
    meta["retrieved_timezone"] = "Asia/Hong_Kong"
    if last_modified:
        meta["http_last_modified"] = last_modified
    # Always write SOURCE.json (source_path), never the template.
    source_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_txt_path.write_text(render_source_txt(meta), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Download the official DATA.GOV.HK English holiday JSON into data/ "
            "and update the SOURCE retrieval date. Does not scrape other government pages."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate the official file, but do not write local files.",
    )
    args = parser.parse_args(argv)
    try:
        if args.dry_run:
            meta = load_source(resolve_source_read_path(DEFAULT_SOURCE))
            raw, last_modified = fetch_official_file(meta["file_url"])
            events = validate_holiday_json(raw)
            count = len(events["vcalendar"][0]["vevent"])
            print(
                f"dry-run ok: {count} events from {meta['file_url']}"
                + (f"; Last-Modified: {last_modified}" if last_modified else "")
            )
            return 0
        meta = update_local_files()
        print(
            "updated "
            f"{DEFAULT_DATA} and SOURCE files; retrieved_on={meta['retrieved_on']}; "
            f"http_last_modified={meta.get('http_last_modified')}"
        )
        return 0
    except UpdateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
