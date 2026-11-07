"""normalize_event over every recorded event fixture, both Google Chat shapes, and hostile input."""

import copy
from typing import Any

import pytest
from tests.unit.chat_bot.conftest import load_event

from buddy_bot.events import ChatEvent, normalize_event

USER = "users/111111111111111111111"
EMAIL = "utente@example.invalid"
DM = "spaces/AAAAsyntheticDM"
ROOM = "spaces/AAAAsyntheticRoom"


def _event(**changes: Any) -> ChatEvent:
    base: dict[str, Any] = {
        "kind": "message",
        "message_name": None,
        "text": "",
        "space_name": ROOM,
        "is_dm": False,
        "thread_name": None,
        "user_name": USER,
        "user_email": EMAIL,
        "is_bot_sender": False,
        "command_id": None,
    }
    return ChatEvent(**{**base, **changes})


MESSAGE_CASES = {
    "legacy_dm_message": _event(
        message_name=f"{DM}/messages/msg-1.msg-1",
        text="Come richiedo le ferie?",
        space_name=DM,
        is_dm=True,
        thread_name=f"{DM}/threads/thr-1",
    ),
    "legacy_room_mention": _event(
        message_name=f"{ROOM}/messages/m-2.m-2",
        text="Come richiedo le ferie?",
        thread_name=f"{ROOM}/threads/t-2",
    ),
    "addon_room_mention": _event(
        message_name=f"{ROOM}/messages/m-1.m-1",
        text="Come richiedo le ferie?",
        thread_name=f"{ROOM}/threads/t-1",
    ),
    "addon_dm_message": _event(
        message_name=f"{DM}/messages/msg-5.msg-5",
        text="Come richiedo le ferie?",
        space_name=DM,
        is_dm=True,
        thread_name=f"{DM}/threads/thr-5",
    ),
    "legacy_bot_sender": _event(
        message_name=f"{ROOM}/messages/m-4.m-4",
        text="Messaggio automatico",
        thread_name=f"{ROOM}/threads/t-4",
        user_name="users/222222222222222222222",
        user_email=None,
        is_bot_sender=True,
    ),
}


@pytest.mark.parametrize("fixture", MESSAGE_CASES)
def test_message_fixtures_normalize_to_message_events(fixture: str) -> None:
    assert normalize_event(load_event(fixture)) == MESSAGE_CASES[fixture]


@pytest.mark.parametrize("fixture", ["legacy_added_to_space", "addon_added_to_space"])
def test_added_to_space_is_kind_added_without_a_message(fixture: str) -> None:
    assert normalize_event(load_event(fixture)) == _event(kind="added")


@pytest.mark.parametrize("fixture", ["legacy_removed_from_space", "addon_removed_from_space"])
def test_removed_from_space_is_kind_removed_without_a_message(fixture: str) -> None:
    assert normalize_event(load_event(fixture)) == _event(kind="removed")


@pytest.mark.parametrize(
    ("fixture", "thread_name", "message_name"),
    [
        ("legacy_slash_command", f"{DM}/threads/thr-3", f"{DM}/messages/msg-3.msg-3"),
        ("addon_app_command", f"{DM}/threads/thr-6", f"{DM}/messages/msg-6.msg-6"),
    ],
)
def test_slash_and_app_commands_carry_the_command_id_as_a_string(
    fixture: str, thread_name: str, message_name: str
) -> None:
    event = normalize_event(load_event(fixture))
    assert event is not None
    assert event.kind == "command"
    assert event.command_id == "1"
    assert event.space_name == DM
    assert event.is_dm is True
    assert event.thread_name == thread_name
    assert event.message_name == message_name
    assert event.user_name == USER


def test_user_without_email_has_no_email() -> None:
    payload = load_event("addon_room_mention")
    del payload["chat"]["user"]["email"]
    event = normalize_event(payload)
    assert event is not None and event.user_email is None


def test_email_is_lowercased() -> None:
    payload = load_event("legacy_dm_message")
    payload["user"]["email"] = "Utente@Example.Invalid"
    event = normalize_event(payload)
    assert event is not None and event.user_email == EMAIL


def test_mention_is_removed_from_text_when_argument_text_is_absent() -> None:
    payload = load_event("addon_room_mention")
    message = payload["chat"]["messagePayload"]["message"]
    del message["argumentText"]
    message["text"] = "@Buddy Come richiedo le ferie?"
    event = normalize_event(payload)
    assert event is not None and event.text == "Come richiedo le ferie?"


def _bot_mention(length: int, start_index: int | None = None) -> dict[str, Any]:
    mention: dict[str, Any] = {
        "type": "USER_MENTION",
        "length": length,
        "userMention": {"type": "MENTION", "user": {"name": "users/999", "type": "BOT"}},
    }
    if start_index is not None:  # proto3 JSON omits a zero startIndex
        mention["startIndex"] = start_index
    return mention


def test_two_word_bot_mention_is_removed_whole_using_the_annotation() -> None:
    payload = load_event("addon_room_mention")
    message = payload["chat"]["messagePayload"]["message"]
    del message["argumentText"]
    message["text"] = "@AI Buddy Come richiedo le ferie?"
    message["annotations"] = [_bot_mention(length=9)]
    event = normalize_event(payload)
    assert event is not None and event.text == "Come richiedo le ferie?"


def test_bot_mention_in_the_middle_of_the_text_is_removed_too() -> None:
    payload = load_event("legacy_room_mention")
    message = payload["message"]
    del message["argumentText"]
    message["text"] = "Ciao @AI Buddy come richiedo le ferie?"
    message["annotations"] = [_bot_mention(length=9, start_index=5)]
    event = normalize_event(payload)
    assert event is not None and event.text == "Ciao come richiedo le ferie?"


def test_annotation_that_does_not_point_at_an_at_sign_is_ignored() -> None:
    payload = load_event("legacy_room_mention")
    message = payload["message"]
    del message["argumentText"]
    message["text"] = "@AI Buddy Come richiedo le ferie?"
    message["annotations"] = [_bot_mention(length=4, start_index=3), {"type": "SLASH_COMMAND"}]
    event = normalize_event(payload)
    assert event is not None and event.text == "Buddy Come richiedo le ferie?"


def test_dm_text_without_argument_text_is_kept_whole() -> None:
    payload = load_event("legacy_dm_message")
    del payload["message"]["argumentText"]
    event = normalize_event(payload)
    assert event is not None and event.text == "Come richiedo le ferie?"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"type": "CARD_CLICKED"},
        {"type": "MESSAGE"},
        {"chat": "not-a-mapping"},
        {"chat": ["not", "a", "mapping"]},
        {"chat": None},
        {"chat": {}},
        {"chat": {"user": {"name": USER}, "buttonClickedPayload": {"space": {"name": ROOM}}}},
        {"chat": {"messagePayload": "not-a-mapping"}},
        {"chat": {"messagePayload": {"space": "not-a-mapping", "message": 3}}},
        {"chat": {"messagePayload": {"space": {"name": 7}, "message": {}}}},
        {"chat": {"addedToSpacePayload": {"space": {}}}},
        {"chat": {"appCommandPayload": {"space": {"name": ROOM}}}},
        {"chat": {"appCommandPayload": {"appCommandMetadata": "x", "space": {"name": ROOM}}}},
        {
            "chat": {
                "appCommandPayload": {
                    "appCommandMetadata": {"appCommandId": True},
                    "space": {"name": ROOM},
                }
            }
        },
        {"type": "ADDED_TO_SPACE", "space": {}},
        {"type": "ADDED_TO_SPACE", "space": "x"},
        {"type": "REMOVED_FROM_SPACE"},
        {"type": "MESSAGE", "space": {"name": ROOM}, "message": {"slashCommand": "x"}},
        {"type": ["MESSAGE"], "space": {"name": ROOM}},
        {"type": "MESSAGE", "space": {"name": ROOM}},
        {"chat": {"messagePayload": {"space": {"name": ROOM}}}},
        {"type": "MESSAGE", "message": {"text": "ciao"}},
    ],
    ids=lambda p: repr(p)[:60],
)
def test_malformed_payloads_return_none_and_never_raise(payload: dict[str, Any]) -> None:
    assert normalize_event(payload) is None


@pytest.mark.parametrize("value", [None, [], "MESSAGE", 7, 1.5, True])
def test_non_mapping_json_values_return_none(value: object) -> None:
    assert normalize_event(value) is None


def test_message_without_space_name_returns_none() -> None:
    legacy = load_event("legacy_dm_message")
    del legacy["space"]["name"]
    addon = load_event("addon_dm_message")
    del addon["chat"]["messagePayload"]["space"]["name"]
    assert normalize_event(legacy) is None
    assert normalize_event(addon) is None


def test_normalize_does_not_mutate_the_payload() -> None:
    payload = load_event("addon_app_command")
    before = copy.deepcopy(payload)
    normalize_event(payload)
    assert payload == before
