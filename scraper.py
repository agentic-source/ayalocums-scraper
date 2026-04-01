"""
scraper.py — Scrape new AyaLocums physician job postings.

Fetches all pages of https://www.ayalocums.com/locum-tenens-physician-jobs/,
extracts inline jobsData JSON from each page, compares jobIDs against state.json,
writes jobs_new.json with new unseen jobs, and updates state.json.

Exit codes:
  0 — success (full or partial)
  1 — fatal failure (site unreachable, regex failed on page 1, or sanity check failed)
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

import state as state_module

JOBS_NEW_FILE = Path(__file__).parent / "jobs_new.json"
BASE_URL = "https://www.ayalocums.com"
JOBS_URL = f"{BASE_URL}/locum-tenens-physician-jobs/"
MAX_PAGES = 50
REQUEST_DELAY = 1.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
JOBSDATA_RE = re.compile(r"var jobsData = (\[.*?\])\s*\nvar ", re.DOTALL)


def page_url(page_num: int) -> str:
    if page_num == 1:
        return JOBS_URL
    return f"{JOBS_URL}page/{page_num}/"


def job_url(job_id) -> str:
    return f"{BASE_URL}/job/locum-physician/{job_id}/"


def pay_display(low, high) -> str:
    """Format daily pay range as a human-readable string."""
    if low and high:
        return f"${int(low):,}\u2013${int(high):,}/day"
    if low:
        return f"${int(low):,}+/day"
    if high:
        return f"up to ${int(high):,}/day"
    return ""


def extract_jobs_from_html(html: str):
    """
    Extract jobsData JSON array from page HTML.
    Returns list of raw job dicts, empty list if array is empty,
    or None if the regex didn't match (parse failure / page not found).
    """
    match = JOBSDATA_RE.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def normalize_job(raw: dict) -> dict:
    """Map a raw AyaLocums job dict to our normalized schema."""
    job_id = str(raw["jobID"])
    return {
        "id": job_id,
        "specialty": raw.get("expertiseText", ""),
        "city": raw.get("city", ""),
        "state": raw.get("stateAbbrev", ""),
        "state_full": raw.get("state", ""),
        "employment_type": raw.get("employmentTypeText", ""),
        "pay_low": raw.get("regularPayLow"),
        "pay_high": raw.get("regularPayHigh"),
        "pay_display": pay_display(raw.get("regularPayLow"), raw.get("regularPayHigh")),
        "start_date": raw.get("startDate"),
        "posted_date": raw.get("posted"),
        "shift": raw.get("longShift", ""),
        "duration_weeks": raw.get("duration"),
        "positions": raw.get("positions"),
        "street_address": raw.get("hospitalAddress"),
        "zip_code": raw.get("hospitalZip"),
        "lat": raw.get("hospitalLocationLat"),
        "lng": raw.get("hospitalLocationLong"),
        "facility_type_id": raw.get("facilityTypeId"),
        "url": job_url(raw["jobID"]),
    }


def fetch_page(session: requests.Session, page_num: int):
    url = page_url(page_num)
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            print(
                f"  Page {page_num}: HTTP {resp.status_code} — stopping",
                file=sys.stderr,
            )
            return None
        return resp.text
    except requests.RequestException as e:
        print(f"  Page {page_num}: request failed — {e}", file=sys.stderr)
        return None


def scrape_all_jobs(seen_ids: set) -> tuple:
    """
    Paginate all physician job pages, return (new_jobs, is_complete).
    is_complete is False if we hit MAX_PAGES or an HTTP error mid-run.
    Raises RuntimeError if page 1 regex fails (fatal — site changed).
    """
    new_jobs = []
    is_complete = True

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    for page_num in range(1, MAX_PAGES + 1):
        if page_num > 1:
            time.sleep(REQUEST_DELAY)

        html = fetch_page(session, page_num)
        if html is None:
            is_complete = False
            break

        raw_jobs = extract_jobs_from_html(html)

        # Fatal: regex didn't match on page 1 — site structure changed
        if raw_jobs is None and page_num == 1:
            raise RuntimeError(
                "Page 1: jobsData regex found no match — site structure may have changed."
            )

        # Empty array or regex miss on later pages = natural end of pagination
        if not raw_jobs:
            print(
                f"  Page {page_num}: no jobs found — end of pagination",
                file=sys.stderr,
            )
            break

        jobs_on_page = [normalize_job(r) for r in raw_jobs]
        new_on_page = [j for j in jobs_on_page if j["id"] not in seen_ids]
        print(
            f"  Page {page_num}: {len(jobs_on_page)} jobs, {len(new_on_page)} new",
            file=sys.stderr,
        )
        new_jobs.extend(new_on_page)

        if page_num == MAX_PAGES:
            print(
                f"  Reached MAX_PAGES ({MAX_PAGES}) — stopping", file=sys.stderr
            )
            is_complete = False

    return new_jobs, is_complete


def main() -> None:
    seen_ids = state_module.get_seen_ids()

    try:
        new_jobs, is_complete = scrape_all_jobs(seen_ids)
    except RuntimeError as e:
        print(f"SCRAPER_FATAL: {e}", file=sys.stderr)
        sys.exit(1)

    with open(JOBS_NEW_FILE, "w") as f:
        json.dump(new_jobs, f, indent=2)

    state_module.add_jobs(new_jobs)

    status = "COMPLETE" if is_complete else "PARTIAL (hit page limit or HTTP error)"
    print(f"Scrape {status}: {len(new_jobs)} new jobs")

    if not is_complete:
        print("SCRAPER_PARTIAL: results may be incomplete", file=sys.stderr)


if __name__ == "__main__":
    main()
