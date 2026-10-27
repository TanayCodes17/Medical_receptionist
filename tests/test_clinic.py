from clinic import get_clinic_info


def test_opening_hours():
    result = get_clinic_info("opening_hours")

    assert result == "Monday to Saturday, 9 AM to 6 PM"


def test_unknown_topic():
    result = get_clinic_info("unknown_topic")

    assert result == "Sorry, I don't have that information."


def test_phone_number():
    result = get_clinic_info("phone")

    assert result == "020-12345678"