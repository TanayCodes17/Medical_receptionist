from clinic import get_clinic_info


TOOL_DEFINITION = {
    "name": "get_clinic_info",
    "description": (
        "Retrieve verified information about the clinic, "
        "such as its name, address, phone number, "
        "opening hours, or services."
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
                "description": "The clinic information to retrieve.",
            }
        },
        "required": ["topic"],
        "additionalProperties": False,
    },
}


def execute_tool(name: str, arguments: dict) -> dict:
    """Execute an explicitly supported agent tool."""

    if name != "get_clinic_info":
        return {
            "success": False,
            "data": None,
            "error": "unknown_tool",
        }

    topic = arguments.get("topic")

    if not isinstance(topic, str):
        return {
            "success": False,
            "data": None,
            "error": "invalid_arguments",
        }

    if topic not in TOOL_DEFINITION["parameters"]["properties"]["topic"]["enum"]:
        return {
            "success": False,
            "data": None,
            "error": "invalid_arguments",
        }

    return get_clinic_info(topic)
