CLINIC_INFO = {
    "name": "Sunrise Medical Clinic",
    "address": "Pune, Maharashtra",
    "opening_hours": "Monday to Saturday, 9 AM to 6 PM",
    "services": ["General consultation", "Routine checkups"],
}

def get_clinic_info(topic:str) -> str:
    #Return the requested information about the clinic

    if topic not in CLINIC_INFO:
        return "Sorry, I dont have that information yet"

    return str(CLINIC_INFO[topic])