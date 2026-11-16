# hk-bizday

**Not a government service. Not legal advice.** This project is not a service of the Government of the Hong Kong Special Administrative Region. The default profile is a conventional weekday calendar, not an official legal definition. It does not cover statutory holidays or weather-related work arrangements. Do not present this project as an official calendar, a government product, or legal advice.

hk-bizday is a small Python 3 standard-library tool for other programs, scheduled jobs, and AI agents that need to know whether a date is a conventional Hong Kong business day under a stated profile. It is not a human-facing advisory or customer-support service, and it does not provide a hosted, non-localhost API.

## Holiday data is not in this repository

This repository does not include the official holiday JSON file. That file is third-party data from the DATA.GOV.HK dataset [Hong Kong Public Holidays Data](https://data.gov.hk/en-data/dataset/hk-dpo-statistic-cal). It is not original to this project, is not licensed under Apache-2.0, and remains subject only to the [DATA.GOV.HK terms of use](https://data.gov.hk/en/terms-and-conditions). See `NOTICE`.

The terms require identifying the source, acknowledging the Government’s and the relevant organisations’ intellectual property rights, and attributing the Government, the relevant organisations, and DATA.GOV.HK. Do not resell the data. See also the [DATA.GOV.HK FAQ](https://data.gov.hk/en/faq).

Attribution:

> Data from DATA.GOV.HK, the Government of the Hong Kong Special Administrative Region, the Digital Policy Office and 1823.

Fetch the file only with the update script, which downloads solely the official English file URL listed on DATA.GOV.HK (`https://www.1823.gov.hk/common/ical/en.json`). Do not scrape GovHK, 1823, or Labour Department website pages for redistribution. The copyright notices on those websites are more restrictive than the DATA.GOV.HK dataset terms and are not the licence for this data file.

```bash
python3 scripts/update_holidays.py --dry-run
python3 scripts/update_holidays.py
```

If `data/SOURCE.json` is missing, the script reads `data/SOURCE.template.json` and, after a successful fetch, writes a new `data/SOURCE.json`. It does not change the template. The script writes `data/hk_public_holidays_en.json` and records the retrieval date (Asia/Hong_Kong) and the HTTP Last-Modified value in `data/SOURCE.json` and `data/SOURCE.txt`. Those generated files must not be committed; they are listed in `.gitignore`.

Requires Python 3 only (standard library). No other packages.

## Default profile and coverage

Default profile: `weekday_ex_general_holidays` (Monday–Friday, and not a Sunday or a gazetted general holiday). This is a convention chosen by this project, not an official “business day” definition.

Coverage is taken from the official file after you fetch it, and is stated in the `coverage` field of every CLI and API response. Do not assume a fixed year range. Sundays that are not gazetted general holidays are not listed in that file, and are still treated as non-business days under the default profile.

## Run tests

Tests need a locally fetched official file. Do not commit that file. See `TESTING.md` for local and CI steps.

```bash
python3 scripts/update_holidays.py
python3 -m unittest discover -s tests -v
```

## CLI

```bash
python3 -m hk_bizday day --date 2026-11-17
python3 -m hk_bizday holidays --from 2026-01-01 --to 2026-12-31
python3 -m hk_bizday add-business-days --date 2026-11-17 --days 3
```

Every CLI and API response includes the profile, coverage window, DATA.GOV.HK source, and the disclaimer above.

## Local HTTP API (localhost only)

This is a local tool. It is not a public hosted service.

```bash
python3 -m hk_bizday serve --host 127.0.0.1 --port 8000
```

- `GET /v0/day?date=2026-11-17&profile=weekday_ex_general_holidays`
- `GET /v0/holidays?from=2026-01-01&to=2026-12-31`
- `GET /v0/add-business-days?date=2026-11-17&days=3`

The server refuses to bind to a non-localhost address.

## Licence

Original source code, HTTP and CLI interfaces, calendar profiles, tests, scripts, and documentation text (other than the third-party data identified in `NOTICE`) are copyright HUGH SYNC UNIVERSE LIMITED and are licensed under the Apache License, Version 2.0. See `LICENSE` and `NOTICE`.

The official holiday JSON, when fetched into `data/hk_public_holidays_en.json`, is not covered by that licence.
