from clinic import get_clinic_info


def test_opening_hours():
    result = get_clinic_info("opening_hours")

    assert result["success"] is True
    assert result["data"] == "Monday to Saturday, 9 AM to 6 PM"
    assert result["error"] is None


def test_unknown_topic():
    result = get_clinic_info("unknown_topic")

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == "unknown_topic"


def test_phone_number():
    result = get_clinic_info("phone")

    assert result["success"] is True
    assert result["data"] == "020-12345678"
    assert result["error"] is None
