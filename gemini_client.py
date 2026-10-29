import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from agent_tools import execute_tool


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY was not found. Check your .env file."
    )

client = genai.Client(api_key=api_key)

MODEL_NAME = "gemini-3.6-flash"


def get_clinic_info_tool(topic: str) -> dict:
    """Retrieve verified clinic information for a supported topic."""

    print(f"\n[DEBUG] Tool called with topic: {topic!r}")

    result = execute_tool(
        "get_clinic_info",
        {"topic": topic},
    )

    print(f"[DEBUG] Tool returned: {result}\n")
    return result


chat = client.chats.create(
    model=MODEL_NAME,
    config=types.GenerateContentConfig(
        system_instruction=(
            "You are a polite medical clinic receptionist. "
            "Answer clinic-information questions using the "
            "available tool. Do not invent clinic details. "
            "If information is unavailable, say so clearly. "
            "Do not diagnose patients or provide medical treatment advice."
        ),
        tools=[get_clinic_info_tool],
    ),
)


def ask_receptionist(question: str) -> str:
    response = chat.send_message(question)
    return response.text or "Sorry, I couldn't generate a response."


def main() -> None:
    print("Medical Receptionist — Gemini")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()

        if question.lower() == "exit":
            print("Receptionist: Goodbye!")
            break

        if not question:
            continue

        try:
            answer = ask_receptionist(question)
            print(f"Receptionist: {answer}\n")
        except Exception as error:
            print(f"Request failed: {error}\n")


if __name__ == "__main__":
    main()