"""tests/test_identifier.py"""
import json
import pytest
from unittest.mock import MagicMock, patch


def make_job(**kwargs) -> dict:
    defaults = {
        "id": "3236627",
        "specialty": "Obstetrics/Gynecology",
        "city": "Christiansburg",
        "state": "VA",
        "state_full": "Virginia",
        "zip_code": "24073",
        "street_address": "2875 Barn Rd",
        "lat": 37.09329,
        "lng": -80.50438,
        "pay_display": "$4,500\u2013$5,000/day",
        "shift": "3x12-Hour 07:00 - 07:00",
        "duration_weeks": 13,
        "start_date": "2026-07-01T04:00:00",
        "positions": 3,
        "url": "https://www.ayalocums.com/job/locum-physician/3236627/",
    }
    return {**defaults, **kwargs}


GOOD_RESPONSE = json.dumps({
    "facility_name": "Carilion New River Valley Medical Center",
    "facility_type": "Community Hospital",
    "confidence": "high",
    "reasoning": "Only hospital in Christiansburg at that address",
    "alternative_facility": None,
})


def make_mock_client(text: str) -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    client.messages.create.return_value = msg
    return client


class TestIdentifyFacility:
    def test_returns_parsed_response_on_success(self):
        import identifier
        client = make_mock_client(GOOD_RESPONSE)
        result = identifier.identify_facility(client, make_job())
        assert result["facility_name"] == "Carilion New River Valley Medical Center"
        assert result["confidence"] == "high"
        assert result["reasoning"] != ""

    def test_strips_markdown_code_fences(self):
        import identifier
        wrapped = f"```json\n{GOOD_RESPONSE}\n```"
        client = make_mock_client(wrapped)
        result = identifier.identify_facility(client, make_job())
        assert result["facility_name"] == "Carilion New River Valley Medical Center"

    def test_returns_fallback_after_two_failures(self):
        import identifier
        client = make_mock_client("not valid json at all")
        with patch("identifier.time.sleep"):
            result = identifier.identify_facility(client, make_job())
        assert result == identifier.FALLBACK

    def test_retries_once_on_parse_failure(self):
        import identifier
        bad_msg = MagicMock()
        bad_msg.content = [MagicMock(text="bad json")]
        good_msg = MagicMock()
        good_msg.content = [MagicMock(text=GOOD_RESPONSE)]
        client = MagicMock()
        client.messages.create.side_effect = [bad_msg, good_msg]
        with patch("identifier.time.sleep"):
            result = identifier.identify_facility(client, make_job())
        assert result["facility_name"] == "Carilion New River Valley Medical Center"
        assert client.messages.create.call_count == 2

    def test_returns_fallback_when_required_keys_missing(self):
        import identifier
        incomplete = json.dumps({"facility_name": "Something", "confidence": "low"})
        client = make_mock_client(incomplete)
        with patch("identifier.time.sleep"):
            result = identifier.identify_facility(client, make_job())
        assert result == identifier.FALLBACK
