# Tests and CI: fetch official data first

The official holiday JSON is not in the repository. Local tests and CI
must fetch it from the official DATA.GOV.HK file URL immediately before
running tests. Do not commit `data/hk_public_holidays_en.json`, and do
not vendor a copy of the official data for CI.

The update script accepts only that official file URL. It refuses
GovHK, 1823 website, and Labour Department page URLs. The CLI has no
localhost bypass; localhost is allowed only in unit tests.

If `data/SOURCE.json` is missing, `scripts/update_holidays.py` reads
`data/SOURCE.template.json` and writes a new `data/SOURCE.json` after a
successful fetch. It does not change the template.

Tests check that each response's `retrieved_on` value is a `YYYY-MM-DD`
date and that it matches `data/SOURCE.json`. They do not hard-code a
retrieval date.

## Local

```bash
python3 scripts/update_holidays.py --dry-run
python3 scripts/update_holidays.py
python3 -m unittest discover -s tests -v
```

## CI

A sample GitHub Actions workflow is in
`docs/public/ci-github-actions.yml.example`. It is a draft only: it is
not installed under `.github/workflows/`, and it must not be enabled
until publication is approved.

The sample uses the free GitHub Actions minutes available for public
repositories, pins Python 3.12, and sets `permissions: contents: read`.
It does not use GitHub Team or Enterprise, Copilot, Codespaces, or Git
LFS.

CI should:

1. Check out the repository (no official JSON is present).
2. Run `python3 scripts/update_holidays.py` so the official file is
   fetched from `https://www.1823.gov.hk/common/ical/en.json`. If
   `data/SOURCE.json` is missing, the script uses
   `data/SOURCE.template.json` and does not change the template.
3. Run `python3 -m unittest discover -s tests -v`.
4. Leave generated files uncommitted.

If the official download fails (for example a transient TLS error), the
job should fail and retry on a later run. Do not fall back to a
committed data file.

Some tests still assume the official English resource covers
2025-01-01 to 2027-12-31 and contains 17 gazetted days in each of those
years. Those assertions will need review if that official file’s
coverage changes.
