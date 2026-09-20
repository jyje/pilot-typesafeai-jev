from langchain_core.messages import AIMessage, HumanMessage

from pilot_jev.text import last_user_text, message_text


def test_message_text_joins_text_blocks_and_drops_other_blocks():
    message = HumanMessage(
        [
            {"type": "text", "text": "a"},
            {"type": "image_url", "image_url": "x"},
            {"type": "text", "text": "b"},
        ]
    )
    assert message_text(message) == "a\nb"


def test_last_user_text_picks_the_latest_human_message():
    messages = [HumanMessage("first"), AIMessage("reply"), HumanMessage("second")]
    assert last_user_text(messages) == "second"


def test_last_user_text_is_empty_without_a_human_message():
    assert last_user_text([AIMessage("only ai")]) == ""
