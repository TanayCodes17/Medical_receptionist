
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

import database
from graph import graph

app = FastAPI(
    title="Medical Receptionist API",
    version="0.2.0",
    description="LangGraph-powered AI Medical Clinic Receptionist"
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:

    config = {
        "configurable": {
            "thread_id": request.session_id,
            "user_id": request.user_id,
        }
    }

    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
        )

        reply = result["messages"][-1].content
        return ChatResponse(reply=reply)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        ) from e


# ==========================================
# Staff / Administrative Endpoints
# ==========================================

class NoShowRequest(BaseModel):
    reason: str = Field(default="Patient No-Show (10 min grace elapsed)")


@app.post("/appointments/{appointment_id}/no-show")
def mark_appointment_no_show(appointment_id: int, payload: NoShowRequest = NoShowRequest()) -> dict:
    """Staff endpoint: Marks an appointment as No-Show after the 10-minute grace period, immediately freeing the slot."""
    result = database.mark_no_show(appointment_id, reason=payload.reason)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class CancelRequest(BaseModel):
    reason: str = Field(default="Cancelled by staff/admin")


@app.post("/appointments/{appointment_id}/cancel")
def staff_cancel_appointment(appointment_id: int, payload: CancelRequest = CancelRequest()) -> dict:
    """Staff endpoint: Cancels an appointment and immediately releases the slot for other patients."""
    result = database.cancel_appointment(appointment_id, reason=payload.reason)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
