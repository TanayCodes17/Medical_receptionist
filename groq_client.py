
import json
import os

from dotenv import load_dotenv
from groq import Groq

from agent_tools import execute_tool


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY was not found. Check your .env file."
    )

client = Groq(api_key=api_key)

MODEL_NAME = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """
You are a polite medical clinic receptionist.

Use the clinic information tool for questions about clinic
details. Do not invent clinic information.

Only report information supported by the tool result.
If a specific department, extension, or detail is not listed,
clearly say that it is unavailable.

Do not diagnose patients or provide medical treatment advice.
"""

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_clinic_info",
        "description": (
            "Retrieve verified information about the clinic, "
            "including its name, address, phone, opening hours, "
            "and services."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "name",
                        "address",
                        "phone",
                        "opening_hours",
                        "services",
                    ],
                    "description": (
                        "The exact category of clinic information "
                        "to retrieve."
                    ),
                }
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
}


def ask_receptionist(
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    *(history or []),
    {"role": "user", "content": question},
]

    for _ in range(3):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=[TOOL_SCHEMA],
            tool_choice="auto",
            temperature=0.2,
        )

        assistant_message = response.choices[0].message
        messages.append(assistant_message)

        if not assistant_message.tool_calls:
            return (
                assistant_message.content
                or "Sorry, I couldn't generate a response."
            )

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name

            try:
                arguments = json.loads(
                    tool_call.function.arguments
                )

                result = execute_tool(tool_name, arguments)

            except (json.JSONDecodeError, TypeError):
                result = {
                    "success": False,
                    "data": None,
                    "error": "invalid_arguments",
                }

            print(
                f"[DEBUG] Tool: {tool_name}, "
                f"arguments: {arguments if 'arguments' in locals() else {}}"
            )
            print(f"[DEBUG] Result: {result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(result),
                }
            )

    return "Sorry, I couldn't complete that request."


def main() -> None:
    print("Medical Receptionist — Groq")
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
