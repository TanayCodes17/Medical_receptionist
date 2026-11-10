
from langgraph.store.base import BaseStore


def get_patient_memory(
    store: BaseStore,
    user_id: str
) -> dict | None:
    """Retrieve long-term memory for a patient."""

    namespace = ("patients", user_id)

    memory = store.get(
        namespace,
        "patient_profile"
    )

    if memory is None:
        return None

    return memory.value


def save_patient_memory(
    store: BaseStore,
    user_id: str,
    memory: dict
) -> None:
    """Save or update a patient's long-term memory."""

    namespace = ("patients", user_id)

    store.put(
        namespace,
        "patient_profile",
        memory
    )

def get_patient_context(
    store: BaseStore,
    user_id: str,
    category: str = "all"
) -> str:

    memory = get_patient_memory(store, user_id)

    if not memory:
        return ""

    if category == "medical":
        return str(memory.get("medical_history", {}))

    if category == "all":
        return str(memory)

    return ""


def update_patient_memory(
    store: BaseStore,
    user_id: str,
    updates: dict
) -> None:
    """Update selected fields in a patient's existing memory."""

    existing_memory = get_patient_memory(store, user_id)

    if existing_memory is None:
        existing_memory = {
            "medical_history": {
                "allergies": [],
                "conditions": [],
                "medications": [],
                "reported_symptoms": []
            },
            "conversation_summary": ""
        }

    # Update medical history
    new_history = updates.get("medical_history", {})

    for key, values in new_history.items():
        if key not in existing_memory["medical_history"]:
            existing_memory["medical_history"][key] = []
        existing_values = existing_memory["medical_history"][key]

        if isinstance(values, list):
            for value in values:
                if value not in existing_values:
                    existing_values.append(value)
        elif values not in existing_values:
            existing_values.append(values)

    # Update conversation summary if provided
    if "conversation_summary" in updates:
        existing_memory["conversation_summary"] = (
            updates["conversation_summary"]
        )

    save_patient_memory(store, user_id, existing_memory)
