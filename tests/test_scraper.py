"""tests/test_scraper.py"""
import json
import pytest
from unittest.mock import MagicMock, patch

# Minimal HTML fixture with one real-shape job
SAMPLE_HTML_ONE_JOB = """
<html><body><script>
var jobsData = [{"jobID":3236627,"city":"Christiansburg","stateAbbrev":"VA",
"state":"Virginia","expertiseText":"Obstetrics/Gynecology",
"professionText":"Physician","employmentTypeText":"LocumTenens1099",
"regularPayLow":4500,"regularPayHigh":5000,
"startDate":"2026-07-01T04:00:00","posted":"2026-03-30T17:39:16.92",
"longShift":"3x12-Hour 07:00 - 07:00","duration":13,"positions":3,
"facilityName":null,"hideFacilityName":true,
"hospitalAddress":"2875 Barn Rd","hospitalZip":"24073",
"hospitalLocationLat":37.09329,"hospitalLocationLong":-80.50438,
"facilityTypeId":10,"hospitalSystemId":509}]
var otherVar = 1;
</script></body></html>
"""

SAMPLE_HTML_EMPTY = """
<html><body><script>
var jobsData = []
var otherVar = 1;
</script></body></html>
"""

SAMPLE_HTML_NO_REGEX = "<html><body>No jobs here</body></html>"


class TestExtractJobsFromHtml:
    def test_extracts_one_job(self):
        import scraper
        jobs = scraper.extract_jobs_from_html(SAMPLE_HTML_ONE_JOB)
        assert jobs is not None
        assert len(jobs) == 1
        assert jobs[0]["jobID"] == 3236627

    def test_returns_empty_list_for_empty_array(self):
        import scraper
        jobs = scraper.extract_jobs_from_html(SAMPLE_HTML_EMPTY)
        assert jobs == []

    def test_returns_none_when_regex_misses(self):
        import scraper
        result = scraper.extract_jobs_from_html(SAMPLE_HTML_NO_REGEX)
        assert result is None


class TestNormalizeJob:
    def test_id_is_string(self):
        import scraper
        raw = {"jobID": 3236627, "city": "Christiansburg", "stateAbbrev": "VA",
               "state": "Virginia", "expertiseText": "OB/GYN"}
        job = scraper.normalize_job(raw)
        assert job["id"] == "3236627"
        assert isinstance(job["id"], str)

    def test_pay_display_formatted_correctly(self):
        import scraper
        raw = {"jobID": 1, "regularPayLow": 4500, "regularPayHigh": 5000}
        job = scraper.normalize_job(raw)
        assert job["pay_display"] == "$4,500\u2013$5,000/day"

    def test_pay_display_empty_when_both_null(self):
        import scraper
        raw = {"jobID": 1, "regularPayLow": None, "regularPayHigh": None}
        job = scraper.normalize_job(raw)
        assert job["pay_display"] == ""

    def test_url_constructed_from_job_id(self):
        import scraper
        raw = {"jobID": 3236627}
        job = scraper.normalize_job(raw)
        assert job["url"] == "https://www.ayalocums.com/job/locum-physician/3236627/"

    def test_missing_optional_fields_default_to_none(self):
        import scraper
        raw = {"jobID": 99}
        job = scraper.normalize_job(raw)
        assert job["street_address"] is None
        assert job["lat"] is None
        assert job["zip_code"] is None

    def test_all_expected_keys_present(self):
        import scraper
        raw = {"jobID": 1}
        job = scraper.normalize_job(raw)
        for key in ("id", "specialty", "city", "state", "state_full",
                    "pay_display", "shift", "url", "street_address", "zip_code",
                    "lat", "lng", "posted_date"):
            assert key in job, f"Missing key: {key}"


class TestPayDisplay:
    def test_both_values(self):
        import scraper
        assert scraper.pay_display(4500, 5000) == "$4,500\u2013$5,000/day"

    def test_low_only(self):
        import scraper
        assert scraper.pay_display(4500, None) == "$4,500+/day"

    def test_high_only(self):
        import scraper
        assert scraper.pay_display(None, 5000) == "up to $5,000/day"

    def test_neither(self):
        import scraper
        assert scraper.pay_display(None, None) == ""


class TestScrapeAllJobs:
    def test_filters_out_seen_ids(self):
        import scraper
        seen = {"3236627"}

        mock_page1 = MagicMock()
        mock_page1.status_code = 200
        mock_page1.text = SAMPLE_HTML_ONE_JOB

        mock_empty = MagicMock()
        mock_empty.status_code = 200
        mock_empty.text = SAMPLE_HTML_EMPTY

        with patch("scraper.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.side_effect = [mock_page1, mock_empty]
            with patch("scraper.time.sleep"):
                new_jobs, is_complete = scraper.scrape_all_jobs(seen)

        assert new_jobs == []
        assert is_complete is True

    def test_collects_new_jobs(self):
        import scraper

        mock_page1 = MagicMock()
        mock_page1.status_code = 200
        mock_page1.text = SAMPLE_HTML_ONE_JOB

        mock_empty = MagicMock()
        mock_empty.status_code = 200
        mock_empty.text = SAMPLE_HTML_EMPTY

        with patch("scraper.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.side_effect = [mock_page1, mock_empty]
            with patch("scraper.time.sleep"):
                new_jobs, is_complete = scraper.scrape_all_jobs(set())

        assert len(new_jobs) == 1
        assert new_jobs[0]["id"] == "3236627"
        assert is_complete is True

    def test_http_error_on_page_2_sets_is_complete_false(self):
        import scraper

        mock_page1 = MagicMock()
        mock_page1.status_code = 200
        mock_page1.text = SAMPLE_HTML_ONE_JOB

        mock_page2 = MagicMock()
        mock_page2.status_code = 404

        with patch("scraper.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.side_effect = [mock_page1, mock_page2]
            with patch("scraper.time.sleep"):
                new_jobs, is_complete = scraper.scrape_all_jobs(set())

        assert is_complete is False

    def test_raises_runtime_error_when_page1_regex_fails(self):
        import scraper

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = SAMPLE_HTML_NO_REGEX

        with patch("scraper.requests.Session") as MockSession:
            session = MockSession.return_value
            session.get.return_value = mock_response
            with pytest.raises(RuntimeError, match="jobsData regex"):
                scraper.scrape_all_jobs(set())
