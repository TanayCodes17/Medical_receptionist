conversations: dict[str, list[dict[str, str]]] = {}


def get_history(session_id: str) -> list[dict[str, str]]:
    """Return the message history for a session."""

    if session_id not in conversations:
        conversations[session_id] = []

    return conversations[session_id]


def add_message(
    session_id: str,
    role: str,
    content: str,
) -> None:
    """Add a message to the specified session."""

    history = get_history(session_id)

    history.append({
        "role": role,
        "content": content,
    })