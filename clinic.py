CLINIC_INFO = {
    "name": "Sunrise Medical Clinic",
    "address": "Pune, Maharashtra",
    "phone": "020-12345678",
    "opening_hours": "Monday to Saturday, 9 AM to 6 PM",
    "services": ["General consultation", "Routine checkups"],
}

def get_clinic_info(topic:str) -> str:
    #Return the requested information about the clinic

    if topic not in CLINIC_INFO:
        return "Sorry, I don't have that information."

    return str(CLINIC_INFO[topic])