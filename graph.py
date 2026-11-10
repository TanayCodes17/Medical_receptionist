import os
from datetime import datetime
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig


# Import specialized tools
from tools import (
    get_clinic_info,
    list_doctors,
    check_doctor_availability,
    book_appointment,
    book_urgent_appointment,
    get_patient_appointments,
    cancel_appointment,
)
from patient_memory import (
    get_patient_context,
    update_patient_memory
)

# Load environment variables (.env)
load_dotenv(override=True)

# ==========================================
# PART 1: State Definition & Tool Grouping
# ==========================================

class AgentState(MessagesState, total=False):
    """Conversation messages + supervisor routing decision."""
    next_worker: str
    memory_updates: dict


# Group tools by specialist responsibility
triage_tools = [
    list_doctors,
    book_urgent_appointment,
]

clinic_info_tools = [
    get_clinic_info,
]

scheduling_tools = [
    list_doctors,
    check_doctor_availability,
    book_appointment,
    book_urgent_appointment,
    get_patient_appointments,
    cancel_appointment,
]

# Initialize Groq LLM
model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

llm = ChatGroq(
    model=model_name,
    temperature=0.2,
)

# ==========================================
# PART 2: Supervisor / Router Definition
# ==========================================

class RouterDecision(BaseModel):
    """Structured decision returned by the supervisor."""

    next_worker: Literal[
        "triage",
        "scheduling",
        "clinic_info",
        "general",
    ] = Field(
        description="The specialist best suited to handle this user message."
    )

    reason: str = Field(
        description="Brief explanation of why this specialist was chosen."
    )


SUPERVISOR_SYSTEM_PROMPT = """You are the Front Desk Manager at Sunrise Medical Clinic.

Your sole responsibility is to analyze the conversation and route
the patient to the single best specialist.

ROUTING CRITERIA:

1. 'triage': The patient mentions physical symptoms, illness, pain,
   feeling sick, or asks which doctor can treat their condition.

2. 'scheduling': The patient wants to check appointment availability,
   book a visit (routine or urgent/emergency), cancel an appointment, or look up existing appointments.

3. 'clinic_info': The patient asks about clinic address, location,
   opening hours, phone number, or general services.

4. 'general': Greetings, pleasantries, thanks, or goodbyes.

Always select the most specific specialist for the user's latest message.
"""


router_llm = llm.with_structured_output(RouterDecision)


def supervisor_node(state: AgentState) -> dict:
    """Inspect conversation and choose the next specialist."""

    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)
    ] + state["messages"]

    try:
        decision: RouterDecision = router_llm.invoke(messages)
        worker = decision.next_worker

    except Exception:
        # Fallback to scheduling if routing fails, as scheduling handles appointments
        worker = "scheduling"

    return {"next_worker": worker}


# ==========================================
# PART 3: Specialist Prompts & Worker Nodes
# ==========================================

TRIAGE_PROMPT = """You are the Clinical Intake & Triage Specialist
at Sunrise Medical Clinic.

Today's date is {today}.

OUR CLINIC DOCTORS & SPECIALTIES:
- Dr. Rajesh Sharma (General Physician): Headaches, dizziness,
  fever, cough, cold, fatigue, body aches, stomach pain,
  routine checkups.
- Dr. Priya Patel (Pediatrician): Children, infants,
  childhood illnesses, pediatric wellness.
- Dr. Ananya Iyer (Dermatologist): Skin rashes, acne, itching,
  skin lesions, allergies, hair/scalp issues.

YOUR OPERATIONAL PROTOCOL:

1. Empathy:
   Acknowledge the patient's discomfort warmly and politely.

2. Emergency Triage (CRITICAL SAFETY PROTOCOL):
   If the patient mentions life-threatening signs such as severe
   chest pain, difficulty breathing, sudden paralysis/slurred speech,
   heavy bleeding, or loss of consciousness:
   a. Safety Alert: Immediately advise them to call emergency services (112 or local ER) right away.
   b. Urgent Slot Offer: If they are in a safe condition and want an immediate clinic consultation today, offer:
      "If you are safe and need an immediate consultation today, I can reserve our earliest urgent slot with our General Physician, Dr. Rajesh Sharma. Would you like me to book that for you?"
   c. If the patient has already provided their name and phone number and explicitly asked to book now, call 'book_urgent_appointment'. Otherwise, wait for their confirmation.


3. No Direct Diagnosis:
   Never diagnose conditions or prescribe medications.

4. Doctor Directory:
   Use the 'list_doctors' tool to verify the current clinic doctors
   and specialties before recommending a doctor when relevant.

5. Active Clinic Steering:
   Clearly state which doctor can evaluate the patient's symptoms.
   Proactively ask if they would like to check appointment slots
   or schedule a visit.

Example:
"I'm sorry to hear that you are feeling dizzy and having a headache.
While I cannot diagnose you, our General Physician can evaluate you.
Would you like me to check available appointment slots?"
"""


SCHEDULING_PROMPT = """You are the Appointment Scheduling Specialist
at Sunrise Medical Clinic.

Today's date is {today}.

YOUR OPERATIONAL PROTOCOL:

1. Urgent / Emergency Bookings:
   If the patient is in an urgent situation or confirms they want the urgent appointment offered by triage:
   - Use 'book_urgent_appointment' with the patient's name and contact number.
   - You only need their name and phone number (do NOT ask for doctor, date, or time slot, as this tool automatically reserves the earliest slot today with Dr. Rajesh Sharma).
   - Once confirmed, provide the Appointment ID, date, and time slot, and remind them that if symptoms worsen, they must seek emergency services at 112 immediately.

2. Checking Availability:
   When a patient asks for a doctor or date, use
   'check_doctor_availability' with date format YYYY-MM-DD.

3. Booking:
   Collect patient name, phone number, doctor name, date,
   and time slot.

   Once the patient confirms, call 'book_appointment'.

   Confirm the appointment using the returned Appointment ID.

4. Cancelling:
   Ask for the patient's phone number if not provided.

   Use 'get_patient_appointments' to look up active bookings.

   Confirm the appointment details before cancelling.

   Then call 'cancel_appointment'.

5. Doctor Directory:
   Use 'list_doctors' if the patient asks about clinic doctors.

6. Keep answers concise, clear, and professional.

7. Never assume the patient wants an appointment booked
   merely because a doctor was recommended.
"""


CLINIC_INFO_PROMPT = """You are the Clinic Information Specialist
at Sunrise Medical Clinic.

Use 'get_clinic_info' to provide accurate information about
the clinic's address, phone number, opening hours, or services.

Never fabricate details.

If a detail is missing, clearly explain that it is unavailable.
"""


GENERAL_PROMPT = """You are the Front Desk Greeter
at Sunrise Medical Clinic.

Politely greet the patient, welcome them to the clinic,
and ask how you can help today.

Examples include consulting with a doctor, booking an appointment,
or asking about clinic information.
"""


# ==========================================
# Model bindings per specialist
# ==========================================

triage_llm = llm.bind_tools(triage_tools)

scheduling_llm = llm.bind_tools(scheduling_tools)

clinic_info_llm = llm.bind_tools(clinic_info_tools)

general_llm = llm.bind_tools([])


# ==========================================
# Worker Nodes
# ==========================================

def triage_node(state: AgentState, config:RunnableConfig,* , store: BaseStore) -> dict:
    """Evaluate symptoms and recommend an appropriate doctor."""

    today_str = datetime.now().strftime("%Y-%m-%d (%A)")

    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    patient_context = get_patient_context(
        store,
        user_id,
        category="medical"
    )
    prompt = f"""{TRIAGE_PROMPT.format(today=today_str)}

PATIENT MEDICAL CONTEXT:
{patient_context}
"""

    messages = [
        SystemMessage(content=prompt)
    ] + state["messages"]

    response = triage_llm.invoke(messages)

    # Track reported symptoms into memory_updates so they persist across sessions
    last_user_msg = next((m.content for m in reversed(state["messages"]) if getattr(m, "type", "") == "human"), None)
    updates = {}
    if last_user_msg and len(str(last_user_msg).strip()) > 3:
        updates = {
            "medical_history": {
                "reported_symptoms": [str(last_user_msg).strip()[:100]]
            }
        }

    return {"messages": [response], "memory_updates": updates}


def scheduling_node(state: AgentState, config:RunnableConfig,* , store: BaseStore) -> dict:
    """Manage appointments and database operations."""

    today_str = datetime.now().strftime("%Y-%m-%d (%A)")

    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    patient_context = get_patient_context(
    store,
    user_id,
    category="all"
)
    
    prompt = f"""
    {SCHEDULING_PROMPT.format(today=today_str)}
    Patient Context:
    {patient_context}
    """

    messages = [
        SystemMessage(content=prompt)
    ] + state["messages"]

    response = scheduling_llm.invoke(messages)

    return {"messages": [response]}


def clinic_info_node(state: AgentState) -> dict:
    """Answer clinic FAQs using clinic tools."""

    messages = [
        SystemMessage(content=CLINIC_INFO_PROMPT)
    ] + state["messages"]

    response = clinic_info_llm.invoke(messages)

    return {"messages": [response]}


def general_node(
    state: AgentState,
    config: RunnableConfig,
    *,
    store: BaseStore
) -> dict:
    """Handle greetings and general conversation using long-term memory."""

    # 1. Extract patient ID from config
    user_id = config.get("configurable", {}).get("user_id")
    if not user_id:
        raise ValueError("user_id is required")

    patient_context = get_patient_context(
        store,
        user_id,
        category="all"
    )
    prompt = f"""{GENERAL_PROMPT}

PATIENT CONTEXT:
{patient_context}
"""


    messages = [
        SystemMessage(content=prompt)
    ] + state["messages"]

    # 5. Generate response
    response = general_llm.invoke(messages)

    return {"messages": [response]}


def memory_update_node(
    state: AgentState,
    config: RunnableConfig,
    *,
    store: BaseStore
) -> dict:
    """Save explicitly validated patient memory updates."""

    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        return {"memory_updates": {}}

    updates = dict(state.get("memory_updates") or {})

    # Auto-detect booked appointments to remember in conversation_summary
    for msg in reversed(state.get("messages", [])):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and ("appointment confirmed" in content.lower() or "urgent appointment confirmed" in content.lower()):
            today_str = datetime.now().strftime("%Y-%m-%d")
            updates["conversation_summary"] = f"Last booking confirmed on {today_str}"
            break

    if updates:
        update_patient_memory(
            store,
            user_id,
            updates
        )

    # Clear pending updates after processing
    return {"memory_updates": {}}



# ==========================================
# PART 4: State Graph Construction & Wiring
# ==========================================

builder = StateGraph(AgentState)

# 1. Register specialist nodes
builder.add_node("supervisor", supervisor_node)
builder.add_node("triage", triage_node)
builder.add_node("scheduling", scheduling_node)
builder.add_node("clinic_info", clinic_info_node)
builder.add_node("general", general_node)
builder.add_node("memory_update", memory_update_node)

# 2. Register tool execution nodes
builder.add_node("triage_tools", ToolNode(triage_tools))
builder.add_node("scheduling_tools", ToolNode(scheduling_tools))
builder.add_node("clinic_info_tools", ToolNode(clinic_info_tools))

# 3. Start at supervisor
builder.add_edge(START, "supervisor")

# 4. Supervisor routing
builder.add_conditional_edges(
    "supervisor",
    lambda state: state.get("next_worker", "general"),
    {
        "triage": "triage",
        "scheduling": "scheduling",
        "clinic_info": "clinic_info",
        "general": "general",
    },
)

# 5. Triage tool loop
builder.add_conditional_edges(
    "triage",
    tools_condition,
    {
        "tools": "triage_tools",
        END: "memory_update",
    },
)

builder.add_edge("triage_tools", "triage")

# 6. Scheduling tool loop
builder.add_conditional_edges(
    "scheduling",
    tools_condition,
    {
        "tools": "scheduling_tools",
        END: "memory_update",
    },
)

builder.add_edge("scheduling_tools", "scheduling")

# 7. Clinic information tool loop
builder.add_conditional_edges(
    "clinic_info",
    tools_condition,
    {
        "tools": "clinic_info_tools",
        END: "memory_update",
    },
)

builder.add_edge("clinic_info_tools", "clinic_info")

# 8. General response
builder.add_edge("general", "memory_update")

# 9. Memory Updates after execution
builder.add_edge("memory_update", END)

# ==========================================
# PART 5: Compile Graph & Enable Memory
# ==========================================

memory = MemorySaver()
store = InMemoryStore()

graph = builder.compile(
    checkpointer=memory,
    store=store
)
