import json
from datetime import datetime, timedelta
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"


def load_state() -> list:
    if not STATE_FILE.exists():
        return []
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(entries: list) -> None:
    cutoff = (datetime.today() - timedelta(days=60)).strftime("%Y-%m-%d")
    pruned = [e for e in entries if e["seen_date"] >= cutoff]
    deduped = list({e["id"]: e for e in pruned}.values())
    with open(STATE_FILE, "w") as f:
        json.dump(deduped, f, indent=2)


def get_seen_ids() -> set:
    return {e["id"] for e in load_state()}


def add_jobs(jobs: list) -> None:
    today = datetime.today().strftime("%Y-%m-%d")
    existing = load_state()
    new_entries = [{"id": job["id"], "seen_date": today} for job in jobs]
    save_state(existing + new_entries)
