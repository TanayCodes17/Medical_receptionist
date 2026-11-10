from typing import Literal
from langchain_core.tools import tool
from clinic import CLINIC_INFO
import database


@tool
def get_clinic_info(
    topic: Literal["name", "address", "phone", "opening_hours", "services"],
) -> str:
    """Retrieve verified information about Sunrise Medical Clinic, such as name, address, phone number, opening hours, or available services."""
    if topic in CLINIC_INFO:
        data = CLINIC_INFO[topic]
        if isinstance(data, list):
            return f"{topic.replace('_', ' ').capitalize()}: {', '.join(data)}"
        return f"{topic.replace('_', ' ').capitalize()}: {data}"

    return f"Sorry, information for '{topic}' is not available."


@tool
def list_doctors() -> str:
    """List all available doctors at Sunrise Medical Clinic,
     their specialties, and working days."""
    doctors =  database.get_doctors()
    if not doctors:
        return "No doctors currently found in our clinic"
    lines = ["Available Doctors at Sunrise Medical Clinic:"]
    for doc in doctors:
        lines.append(
            f"-{doc['name']} ({doc['specialty']} | Days:{doc['available_days']})"
        )
    return "\n".join(lines)

@tool
def check_doctor_availability(doctor_name: str, date: str) -> str:
    """Check remaining open appointment slots for a doctor on 
    a specific date (format: YYYY-MM-DD)."""
    slots = database.get_available_slots(doctor_name, date)
    if not slots:
        return f"No open slots for {doctor_name} on {date}. The doctor may be fully booked or off duty"
    return f"Available slots for {doctor_name} on {date}: {', ' .join(slots)}"

@tool
def book_appointment(
    doctor_name: str,
    patient_name: str,
    patient_contact: str,
    date: str,
    time_slot: str,
) -> str:
    """Book an appointment using patient_contact as the phone number.
    This wrapper aligns the tool signature with the LLM's expected argument name.
    """
    # Forward to the underlying database function, mapping contact to phone.
    result = database.book_appointment(
        patient_name=patient_name,
        patient_phone=patient_contact,
        doctor_name=doctor_name,
        date=date,
        time_slot=time_slot,
    )
    if result["success"]:
        return (
            f"Appointment confirmed successfully! "
            f"Appointment ID: #{result['appointment_id']}, "
            f"Patient: {result['patient_name']}, "
            f"Doctor: {result['doctor_name']}, "
            f"Date: {result['date']}, "
            f"Time: {result['time_slot']}."
        )
    else:
        return f"Booking failed: {result['error']}"


@tool
def book_urgent_appointment(
    patient_name: str,
    patient_contact: str,
) -> str:
    """Book the earliest available appointment slot TODAY for an urgent or emergency patient with our General Physician (Dr. Rajesh Sharma).
    Use this when an emergency patient confirms they want an urgent slot immediately.
    """
    result = database.book_urgent_appointment(
        patient_name=patient_name,
        patient_phone=patient_contact,
        doctor_name="Dr. Rajesh Sharma",
    )
    if result["success"]:
        return (
            f"URGENT Appointment confirmed successfully! "
            f"Appointment ID: #{result['appointment_id']} (EMERGENCY PRIORITY), "
            f"Patient: {result['patient_name']}, "
            f"Doctor: {result['doctor_name']}, "
            f"Date: {result['date']}, "
            f"Time: {result['time_slot']}."
        )
    else:
        return f"Urgent booking could not be completed: {result['error']}"


@tool
def get_patient_appointments(patient_phone: str) -> str:
    """Retrieve all active confirmed appointments for a patient using their phone number."""
    appointments = database.get_patient_appointments(patient_phone)
    if not appointments:
        return f"No active appointments found for phone number {patient_phone}."

    lines = [f"Active appointments for {patient_phone}:"]
    for appt in appointments:
        lines.append(
            f"- Appointment #{appt['id']}: with {appt['doctor_name']} on {appt['date']} at {appt['time_slot']}"
        )
    return "\n".join(lines)


@tool
def cancel_appointment(appointment_id: int) -> str:
    """Cancel an existing clinic appointment using its unique appointment ID."""
    result = database.cancel_appointment(appointment_id)
    if result["success"]:
        return (
            f"Appointment #{result['appointment_id']} for {result['patient_name']} "
            f"with {result['doctor_name']} on {result['date']} at {result['time_slot']} "
            f"has been successfully cancelled. The time slot is now open."
        )
    else:
        return f"Cancellation failed: {result['error']}"


# Export list of all tools for the agent
tools = [
    get_clinic_info,
    list_doctors,
    check_doctor_availability,
    book_appointment,
    book_urgent_appointment,
    get_patient_appointments,
    cancel_appointment,
]

