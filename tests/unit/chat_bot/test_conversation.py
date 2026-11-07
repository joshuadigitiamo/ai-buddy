"""Follow-ups: history reaches the reformulation step only, never the answer step (D-11, D-12)."""

import pytest
from tests.unit.chat_bot.conftest import (
    GOOD_DRAFT,
    REFORMULATION,
    DictThreadMemory,
    FakeChatApi,
    FakeLlm,
    ServiceFactory,
    load_event,
    with_message,
)

from buddy_bot.ports import Turn
from buddy_bot.schemas import AnswerDraft, Reformulation

pytestmark = pytest.mark.anyio

FIRST_QUESTION = "Come richiedo le ferie?"
FIRST_ANSWER = GOOD_DRAFT.answer
SECOND_QUESTION = "E per i permessi?"
SECOND_REFORMULATION = REFORMULATION.model_copy(
    update={"standalone_question": "Come richiedo i permessi retribuiti?"}
)
SECOND_ANSWER = "I permessi si chiedono al responsabile con un giorno di preavviso."


def _answer_prompts(llm: FakeLlm) -> list[str]:
    return [call.user for call in llm.calls if call.schema is AnswerDraft]


def _reformulate_prompts(llm: FakeLlm) -> list[str]:
    return [call.user for call in llm.calls if call.schema is Reformulation]


async def test_dm_follow_up_reformulation_sees_history_and_answer_step_does_not(
    make_service: ServiceFactory,
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION, SECOND_REFORMULATION],
            AnswerDraft: [GOOD_DRAFT, GOOD_DRAFT.model_copy(update={"answer": SECOND_ANSWER})],
        }
    )
    memory = DictThreadMemory()
    service = make_service(llm, chat=FakeChatApi(), memory=memory)
    first = load_event("legacy_dm_message")

    await service.handle(first)
    await service.handle(
        with_message(first, name="spaces/AAAAsyntheticDM/messages/msg-2", text=SECOND_QUESTION)
    )

    first_prompt, second_prompt = _reformulate_prompts(llm)
    assert first_prompt == FIRST_QUESTION
    assert FIRST_QUESTION in second_prompt and FIRST_ANSWER in second_prompt
    assert SECOND_QUESTION in second_prompt
    for prompt in _answer_prompts(llm):
        assert FIRST_ANSWER not in prompt
        assert SECOND_QUESTION not in prompt
    assert memory.turns == {
        "spaces/AAAAsyntheticDM": [
            Turn(FIRST_QUESTION, FIRST_ANSWER),
            Turn(SECOND_QUESTION, SECOND_ANSWER),
        ]
    }


async def test_room_follow_up_uses_the_thread_name_as_memory_key(
    make_service: ServiceFactory,
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [REFORMULATION, SECOND_REFORMULATION],
            AnswerDraft: [GOOD_DRAFT, GOOD_DRAFT],
        }
    )
    memory = DictThreadMemory()
    service = make_service(llm, memory=memory)
    first = load_event("addon_room_mention")

    await service.handle(first)
    await service.handle(
        with_message(first, name="spaces/AAAAsyntheticRoom/messages/m-2", text=SECOND_QUESTION)
    )

    thread = "spaces/AAAAsyntheticRoom/threads/t-1"
    assert list(memory.turns) == [thread]
    assert len(memory.turns[thread]) == 2
    assert memory.recent_calls == [(thread, 3), (thread, 3)]
    second_prompt = _reformulate_prompts(llm)[1]
    assert FIRST_QUESTION in second_prompt and FIRST_ANSWER in second_prompt
    assert all(FIRST_ANSWER not in prompt for prompt in _answer_prompts(llm))


async def test_memory_turns_limits_how_many_turns_are_read(
    make_service: ServiceFactory,
) -> None:
    answers = [GOOD_DRAFT.model_copy(update={"answer": f"Risposta numero {n}."}) for n in (1, 2, 3)]
    llm = FakeLlm({Reformulation: [REFORMULATION] * 3, AnswerDraft: answers})
    memory = DictThreadMemory()
    service = make_service(llm, memory=memory, memory_turns=1)
    first = load_event("legacy_dm_message")

    for n, text in enumerate(("Prima domanda?", "Seconda domanda?", "Terza domanda?"), start=1):
        await service.handle(
            with_message(first, name=f"spaces/AAAAsyntheticDM/messages/msg-{n}", text=text)
        )

    assert [n for _, n in memory.recent_calls] == [1, 1, 1]
    third_prompt = _reformulate_prompts(llm)[2]
    assert "Seconda domanda?" in third_prompt and "Risposta numero 2." in third_prompt
    assert "Prima domanda?" not in third_prompt and "Risposta numero 1." not in third_prompt
