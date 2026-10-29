from agent_tools import execute_tool


def test_valid_tool_call():
    result = execute_tool(
        "get_clinic_info",
        {"topic": "opening_hours"},
    )

    assert result["success"] is True
    assert result["data"] == "Monday to Saturday, 9 AM to 6 PM"


def test_unknown_tool_is_rejected():
    result = execute_tool(
        "delete_patient_records",
        {},
    )

    assert result["success"] is False
    assert result["error"] == "unknown_tool"


def test_invalid_topic_is_rejected():
    result = execute_tool(
        "get_clinic_info",
        {"topic": "make_up_an_answer"},
    )

    assert result["success"] is False
    assert result["error"] == "invalid_arguments"