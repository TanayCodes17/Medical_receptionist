CLINIC_INFO = {
    "name": "Sunrise Medical Clinic",
    "address": "Pune, Maharashtra",
    "phone": "020-12345678",
    "opening_hours": "Monday to Saturday, 9 AM to 6 PM",
    "services": ["General consultation", "Routine checkups"],
}

def get_clinic_info(
    topic: str,
) -> dict[str, str | bool | None]:
    """Return clinic information with a consistent result structure."""

    if topic not in CLINIC_INFO:
        return {
            "success": False,
            "data": None,
            "error": "unknown_topic",
        }

    return {
        "success": True,
        "data": str(CLINIC_INFO[topic]),
        "error": None,
    }
