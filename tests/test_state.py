import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


def make_entry(job_id: str, days_ago: int = 0) -> dict:
    d = (datetime.today() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {"id": job_id, "seen_date": d}


class TestLoadState:
    def test_returns_empty_list_when_file_missing(self, tmp_path):
        import state
        with patch.object(state, "STATE_FILE", tmp_path / "state.json"):
            assert state.load_state() == []

    def test_returns_entries_from_existing_file(self, tmp_path):
        import state
        entries = [make_entry("job-1"), make_entry("job-2")]
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(entries))
        with patch.object(state, "STATE_FILE", state_file):
            assert state.load_state() == entries


class TestSaveState:
    def test_prunes_entries_older_than_60_days(self, tmp_path):
        import state
        state_file = tmp_path / "state.json"
        entries = [
            make_entry("job-old", days_ago=61),
            make_entry("job-new", days_ago=1),
        ]
        with patch.object(state, "STATE_FILE", state_file):
            state.save_state(entries)
            result = json.loads(state_file.read_text())
        assert len(result) == 1
        assert result[0]["id"] == "job-new"

    def test_deduplicates_by_id(self, tmp_path):
        import state
        state_file = tmp_path / "state.json"
        entries = [make_entry("job-1"), make_entry("job-1")]
        with patch.object(state, "STATE_FILE", state_file):
            state.save_state(entries)
            result = json.loads(state_file.read_text())
        assert len(result) == 1

    def test_keeps_entries_within_60_days(self, tmp_path):
        import state
        state_file = tmp_path / "state.json"
        entries = [make_entry("job-1", days_ago=59), make_entry("job-2", days_ago=60)]
        with patch.object(state, "STATE_FILE", state_file):
            state.save_state(entries)
            result = json.loads(state_file.read_text())
        assert {e["id"] for e in result} == {"job-1", "job-2"}


class TestGetSeenIds:
    def test_returns_set_of_ids(self, tmp_path):
        import state
        state_file = tmp_path / "state.json"
        entries = [make_entry("job-1"), make_entry("job-2")]
        state_file.write_text(json.dumps(entries))
        with patch.object(state, "STATE_FILE", state_file):
            assert state.get_seen_ids() == {"job-1", "job-2"}

    def test_returns_empty_set_when_no_state(self, tmp_path):
        import state
        with patch.object(state, "STATE_FILE", tmp_path / "state.json"):
            assert state.get_seen_ids() == set()


class TestAddJobs:
    def test_appends_new_job_ids_to_state(self, tmp_path):
        import state
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps([make_entry("job-existing")]))
        jobs = [{"id": "job-new"}]
        with patch.object(state, "STATE_FILE", state_file):
            state.add_jobs(jobs)
            result = json.loads(state_file.read_text())
        ids = {e["id"] for e in result}
        assert ids == {"job-existing", "job-new"}
