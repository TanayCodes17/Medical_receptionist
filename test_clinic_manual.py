from clinic import get_clinic_info

result=get_clinic_info("opening_hours")
if result["success"]:
    print(result["data"])
else:
    print(f"Unable to retrieve information: {result['error']}")