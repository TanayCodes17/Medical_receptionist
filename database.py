import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "clinic.db")

# Standard clinic appointment slots available per day
SLOT_DURATION_MINUTES = 30

STANDARD_SLOTS = [
    # Morning Session
    "09:00 AM", "09:30 AM",
    "10:00 AM", "10:30 AM",
    "11:00 AM", "11:30 AM",
    "12:00 PM", "12:30 PM",
    # (Lunch: 01:00 PM - 02:00 PM)
    # Afternoon Session
    "02:00 PM", "02:30 PM",
    "03:00 PM", "03:30 PM",
    "04:00 PM", "04:30 PM",
]

def get_connection():
    """Create a connection to the SQLite database with row factory for named column access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize tables and seed doctor data if empty."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Doctors table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                specialty TEXT NOT NULL,
                available_days TEXT NOT NULL
            )
            """
        )

        # 2. Appointments table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                patient_phone TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Confirmed',
                is_emergency INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Migration: ensure is_emergency exists on existing DB files
        cursor.execute("PRAGMA table_info(appointments)")
        existing_cols = [col["name"] for col in cursor.fetchall()]
        if "is_emergency" not in existing_cols:
            cursor.execute(
                "ALTER TABLE appointments ADD COLUMN is_emergency INTEGER NOT NULL DEFAULT 0"
            )

        # 3. Partial Unique Index: only enforce uniqueness for Confirmed appointments
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_active_appointment
            ON appointments(doctor_name, date, time_slot)
            WHERE status = 'Confirmed'
            """
        )

        # 4. Seed doctors if empty
        cursor.execute("SELECT COUNT(*) FROM doctors")
        if cursor.fetchone()[0] == 0:
            sample_doctors = [
                (
                    "Dr. Rajesh Sharma",
                    "General Physician",
                    "Monday to Saturday",
                ),
                (
                    "Dr. Priya Patel",
                    "Pediatrician (Child Specialist)",
                    "Monday, Wednesday, Friday",
                ),
                (
                    "Dr. Ananya Iyer",
                    "Dermatologist (Skin Specialist)",
                    "Tuesday, Thursday, Saturday",
                ),
            ]
            cursor.executemany(
                """
                INSERT INTO doctors (name, specialty, available_days)
                VALUES (?, ?, ?)
                """,
                sample_doctors,
            )
            conn.commit()


def get_doctors() -> list[dict]:
    """Return all doctors with their specialties and available days."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, specialty, available_days FROM doctors ORDER BY id"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def find_doctor(cursor, query: str) -> str | None:
    """Fuzzy match doctor name (e.g. 'Dr. Sharma', 'Sharma', 'Dr. Rajesh') to full DB name."""
    clean = query.lower().replace("dr.", "").replace("dr", "").strip()

    # 1. Try matching the cleaned query directly
    cursor.execute(
        "SELECT name FROM doctors WHERE LOWER(name) LIKE LOWER(?)",
        (f"%{clean}%",),
    )
    row = cursor.fetchone()
    if row:
        return row["name"]

    # 2. Try matching individual words (e.g., last name 'Sharma' or 'Patel')
    for word in clean.split():
        if len(word) > 2:
            cursor.execute(
                "SELECT name FROM doctors WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{word}%",),
            )
            row = cursor.fetchone()
            if row:
                return row["name"]

    return None


def get_available_slots(doctor_name: str, date: str) -> list[str]:
    """
    Return remaining free time slots for a specific doctor on a given date (YYYY-MM-DD).
    Subtracts already booked slots and filters out slots that have already passed for today.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check if the doctor exists
        matched_doctor_name = find_doctor(cursor, doctor_name)
        if not matched_doctor_name:
            return []

        clean_date = date.strip()

        # Fetch booked slots for that doctor on that date (only Confirmed ones)
        cursor.execute(
            """
            SELECT time_slot FROM appointments
            WHERE doctor_name = ? AND date = ? AND status = 'Confirmed'
            """,
            (matched_doctor_name, clean_date),
        )
        booked_slots = {row["time_slot"] for row in cursor.fetchall()}

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        free_slots = []
        for slot in STANDARD_SLOTS:
            if slot in booked_slots:
                continue

            # If date is today, exclude slots whose consultation window has ended
            if clean_date == today_str:
                try:
                    slot_start = datetime.strptime(f"{clean_date} {slot}", "%Y-%m-%d %I:%M %p")
                    slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                    # The slot remains available within its window (e.g. for urgent/walk-ins after a no-show)
                    if slot_end <= now:
                        continue
                except ValueError:
                    pass
            elif clean_date < today_str:
                # Past dates have no available slots
                continue

            free_slots.append(slot)

        return free_slots


def normalize_time_slot(time_str: str) -> str | None:
    """Normalize user or LLM time string (e.g. '09:00', '9:00 am', '14:00', '2pm') to 'HH:MM AM/PM'."""
    clean = time_str.strip().upper()
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M", "%H:%M:%S"):
        try:
            dt = datetime.strptime(clean, fmt)
            return dt.strftime("%I:%M %p")
        except ValueError:
            continue
    return None


def book_appointment(
    patient_name: str,
    patient_phone: str,
    doctor_name: str,
    date: str,
    time_slot: str,
    is_emergency: int = 0,
) -> dict:
    """
    Book an appointment.
    Returns success confirmation with appointment ID, or failure reason.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Find matching doctor
        resolved_doctor_name = find_doctor(cursor, doctor_name)
        if not resolved_doctor_name:
            return {
                "success": False,
                "error": f"Doctor '{doctor_name}' was not found in our clinic directory.",
            }

        # Normalize and validate time slot
        normalized_slot = normalize_time_slot(time_slot)
        if not normalized_slot:
            return {
                "success": False,
                "error": f"Invalid time format '{time_slot}'. Please use standard clinic slots (e.g., '09:00 AM', '02:00 PM').",
            }

        if normalized_slot not in STANDARD_SLOTS:
            return {
                "success": False,
                "error": f"'{time_slot}' is not a standard clinic appointment slot. Standard clinic slots are: {', '.join(STANDARD_SLOTS)}.",
            }

        # Validate that the date and slot are not in the past
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        clean_date = date.strip()

        if clean_date < today_str:
            return {
                "success": False,
                "error": f"Cannot book appointments for past dates ({clean_date}).",
            }
        elif clean_date == today_str:
            try:
                slot_start = datetime.strptime(f"{clean_date} {normalized_slot}", "%Y-%m-%d %I:%M %p")
                slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                if slot_end <= now:
                    return {
                        "success": False,
                        "error": f"The slot {normalized_slot} on {clean_date} has already ended. Please choose an upcoming time slot.",
                    }
            except ValueError:
                pass

        # Attempt insertion (guarded by the partial unique index)
        try:
            cursor.execute(
                """
                INSERT INTO appointments (
                    patient_name,
                    patient_phone,
                    doctor_name,
                    date,
                    time_slot,
                    status,
                    is_emergency
                )
                VALUES (?, ?, ?, ?, ?, 'Confirmed', ?)
                """,
                (
                    patient_name.strip(),
                    patient_phone.strip(),
                    resolved_doctor_name,
                    clean_date,
                    normalized_slot,
                    is_emergency,
                ),
            )
            conn.commit()
            appointment_id = cursor.lastrowid
            return {
                "success": True,
                "appointment_id": appointment_id,
                "patient_name": patient_name,
                "doctor_name": resolved_doctor_name,
                "date": clean_date,
                "time_slot": normalized_slot,
                "status": "Confirmed",
                "is_emergency": bool(is_emergency),
            }
        except sqlite3.IntegrityError:
            # Triggered when slot already has an active Confirmed appointment
            return {
                "success": False,
                "error": f"The slot {time_slot} on {date} with {resolved_doctor_name} is already booked. Please choose another time.",
            }


def get_patient_appointments(patient_phone: str) -> list[dict]:
    """Return all confirmed appointments for a patient by phone number."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, patient_name, doctor_name, date, time_slot, status, is_emergency
            FROM appointments
            WHERE patient_phone = ? AND status = 'Confirmed'
            ORDER BY date, time_slot
            """,
            (patient_phone.strip(),),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def cancel_appointment(appointment_id: int, reason: str = "Cancelled by staff/patient") -> dict:
    """
    Cancel an appointment by its ID.
    Marks status as 'Cancelled', which immediately frees the slot.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check if the appointment exists
        cursor.execute(
            """
            SELECT id, patient_name, doctor_name, date, time_slot, status, is_emergency
            FROM appointments
            WHERE id = ?
            """,
            (appointment_id,),
        )
        row = cursor.fetchone()

        if not row:
            return {
                "success": False,
                "error": f"Appointment #{appointment_id} was not found.",
            }

        if row["status"] in ("Cancelled", "No-Show"):
            return {
                "success": False,
                "error": f"Appointment #{appointment_id} has already been marked as {row['status']}.",
            }

        # Update status to Cancelled
        cursor.execute(
            "UPDATE appointments SET status = 'Cancelled' WHERE id = ?",
            (appointment_id,),
        )
        conn.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "patient_name": row["patient_name"],
            "doctor_name": row["doctor_name"],
            "date": row["date"],
            "time_slot": row["time_slot"],
            "status": "Cancelled",
            "reason": reason,
        }


def mark_no_show(appointment_id: int, reason: str = "Patient No-Show (10 min grace elapsed)") -> dict:
    """
    Mark an appointment as No-Show by clinic staff.
    Marks status as 'No-Show', which immediately frees the slot in SQLite
    because the unique index only enforces uniqueness for 'Confirmed' appointments.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, patient_name, doctor_name, date, time_slot, status, is_emergency
            FROM appointments
            WHERE id = ?
            """,
            (appointment_id,),
        )
        row = cursor.fetchone()

        if not row:
            return {
                "success": False,
                "error": f"Appointment #{appointment_id} was not found.",
            }

        if row["status"] in ("Cancelled", "No-Show"):
            return {
                "success": False,
                "error": f"Appointment #{appointment_id} is already marked as {row['status']}.",
            }

        cursor.execute(
            "UPDATE appointments SET status = 'No-Show' WHERE id = ?",
            (appointment_id,),
        )
        conn.commit()

        return {
            "success": True,
            "appointment_id": appointment_id,
            "patient_name": row["patient_name"],
            "doctor_name": row["doctor_name"],
            "date": row["date"],
            "time_slot": row["time_slot"],
            "status": "No-Show",
            "reason": reason,
            "message": f"Appointment #{appointment_id} marked as No-Show. Slot {row['time_slot']} on {row['date']} is now immediately open for other patients.",
        }


def book_urgent_appointment(
    patient_name: str,
    patient_phone: str,
    doctor_name: str = "Dr. Rajesh Sharma",
) -> dict:
    """
    Automatically book the earliest available slot today for an urgent/emergency patient.
    Defaults to General Physician (Dr. Rajesh Sharma).
    """
    today = datetime.now().strftime("%Y-%m-%d")
    available_slots = get_available_slots(doctor_name, today)

    if not available_slots:
        return {
            "success": False,
            "error": f"No remaining regular slots available with {doctor_name} for today ({today}). Please direct the patient to the emergency walk-in desk or nearest ER immediately.",
            "date": today,
            "doctor_name": doctor_name,
        }

    earliest_slot = available_slots[0]
    return book_appointment(
        patient_name=patient_name,
        patient_phone=patient_phone,
        doctor_name=doctor_name,
        date=today,
        time_slot=earliest_slot,
        is_emergency=1,
    )


# Auto-initialize database on first load
init_db()
