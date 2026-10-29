from fastapi import FastAPI
from pydantic import BaseModel, Field
from groq_client import ask_receptionist
from conversation_manager import get_history, add_message

app=FastAPI(
    title="Medical Receptionist API",
    version="0.1.0"
)

class ChatRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        max_length=100,
        description="Identifier for this conversation.",
    )
    message: str = Field(
        min_length=1,
        max_length=2000,
        description="The user's message to the receptionist.",
    )

class ChatResponse(BaseModel):
    reply: str

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = get_history(request.session_id)

    reply = ask_receptionist(
        question=request.message,
        history=history,
    )

    add_message(request.session_id, "user", request.message)
    add_message(request.session_id, "assistant", reply)

    return ChatResponse(reply=reply)