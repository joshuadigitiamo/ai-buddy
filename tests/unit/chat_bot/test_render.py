"""Chat rendering: the Guides video card (BOT-09, D15) and bot-built sources only (D-02)."""

import json

import pytest
from tests.unit.chat_bot.conftest import FakeLlm, RecordingConnector
from tests.unit.mcp_server.conftest import FILE, SHA, WEB_BASE

from buddy_bot.render import (
    MAX_ANSWER_CHARS,
    MAX_FONTE_LINES,
    MAX_MESSAGE_CHARS,
    MAX_VIDEO_SECTIONS,
    render_reply,
    sanitize_prose,
)
from buddy_bot.schemas import AnswerDraft, BotReply, Evidence, Referente, Reformulation
from buddy_bot.workflow import WorkflowConfig, WorkflowDeps, run_workflow

pytestmark = pytest.mark.anyio

THUMBNAIL = "https://example.invalid/thumb.png"
MAPPED_PERMALINK = f"{WEB_BASE}/blob/{SHA}/{FILE}#L10-L14"
MAPPED_VIDEO = "https://videos.example.invalid/demo.mp4#t=12"


async def test_guides_answer_with_mapped_video_renders_card_with_fonte_and_guarda(
    connector: RecordingConnector, workflow_config: WorkflowConfig
) -> None:
    llm = FakeLlm(
        {
            Reformulation: [
                Reformulation(
                    standalone_question="Cos'e il chunking?",
                    keywords_it=["suddivisione"],
                    keywords_en=["chunking"],
                    intent="question",
                )
            ],
            AnswerDraft: [
                AnswerDraft(
                    answer="Il chunking divide i documenti in sezioni.",
                    citations=[MAPPED_PERMALINK],
                    grounded=True,
                    confidence=0.9,
                )
            ],
        }
    )

    reply = await run_workflow("chunking?", [], WorkflowDeps(llm, connector, workflow_config))
    rendered = render_reply(reply, video_thumbnail_url=THUMBNAIL)

    assert reply.kind == "answer"
    assert "Il chunking divide i documenti in sezioni." in rendered.text
    assert "Fonte: Guida" in rendered.text
    assert len(rendered.cards_v2) == 1
    sections = rendered.cards_v2[0]["card"]["sections"]
    assert len(sections) == 1
    widgets = sections[0]["widgets"]
    assert [next(iter(widget)) for widget in widgets] == ["image", "textParagraph", "buttonList"]
    assert widgets[0]["image"]["imageUrl"] == THUMBNAIL
    buttons = widgets[2]["buttonList"]["buttons"]
    assert [button["text"] for button in buttons] == ["Fonte", "Guarda"]
    assert [button["onClick"]["openLink"]["url"] for button in buttons] == [
        MAPPED_PERMALINK,
        MAPPED_VIDEO,
    ]


def _handbook(page: str, title: str, day: str = "2026-10-03") -> Evidence:
    return Evidence(
        source_url=f"handbook://{page}",
        kind="handbook",
        title=title,
        text="testo",
        revision_date=f"{day}T00:00:00+00:00",
        revision_kind="last_updated",
    )


def _guide(
    name: str, video_url: str | None = None, title: str | None = None, line: int = 1
) -> Evidence:
    return Evidence(
        source_url=f"{WEB_BASE}/blob/{SHA}/{FILE}#L{line}-L{line + 4}",
        kind="guides",
        title=title or f"Sezione {name}",
        text="testo",
        revision_date="2026-11-03T00:00:00+00:00",
        revision_kind="indexed_on",
        video_url=video_url,
    )


def _answer(
    sources: list[Evidence], answer: str = "Risposta breve.", referente: Referente | None = None
) -> BotReply:
    return BotReply(kind="answer", answer=answer, sources=sources, referente=referente)


HR_CONTACTS = _handbook("05-contatti", "Contatti", "2026-10-10")
HR = Referente(role="HR", contact="hr@example.invalid", contact_source=HR_CONTACTS)


def test_handbook_only_answer_cites_as_text_and_has_no_card() -> None:
    reply = _answer([_handbook("02-ferie", "Ferie e permessi")])

    rendered = render_reply(reply, video_thumbnail_url=THUMBNAIL)

    assert rendered.text.endswith(
        "Fonte: Manuale – Ferie e permessi (handbook://02-ferie), revisione 2026-10-03"
    )
    assert rendered.cards_v2 == []


def test_guides_source_without_video_has_a_fonte_line_and_no_card() -> None:
    reply = _answer([_guide("A")])

    rendered = render_reply(reply, video_thumbnail_url=THUMBNAIL)

    # The section title is a Markdown link (Chat app markup is MARKDOWN), not a raw URL in
    # parentheses: tone follow-up 2026-11-07, shorter and clickable.
    permalink = f"{WEB_BASE}/blob/{SHA}/{FILE}#L1-L5"
    assert rendered.text.endswith(
        f"Fonte: Guida – [Sezione A]({permalink}), indicizzata il 2026-11-03"
    )
    assert rendered.cards_v2 == []


def test_guides_fonte_title_cannot_break_out_of_the_markdown_link() -> None:
    source = _guide("A", title="Uso di [chunk] e (overlap)\nsu due righe")

    text = render_reply(_answer([source]), video_thumbnail_url=None).text
    fonte = text.split("\n\n")[1]

    assert fonte.startswith("Fonte: Guida – [Uso di (chunk) e (overlap) su due righe](")
    assert fonte.count("](") == 1
    assert "\n" not in fonte


def test_guides_permalink_with_parentheses_or_spaces_is_encoded_inside_the_link() -> None:
    source = _guide("A").model_copy(update={"source_url": f"{WEB_BASE}/blob/{SHA}/a (b).md#L1"})

    fonte = render_reply(_answer([source]), video_thumbnail_url=None).text.split("\n\n")[1]

    assert "](" + f"{WEB_BASE}/blob/{SHA}/a%20%28b%29.md#L1" + ")," in fonte


def test_guides_source_with_a_non_web_url_is_cited_by_title_without_any_link() -> None:
    source = _guide("A").model_copy(update={"source_url": "file:///etc/passwd"})

    text = render_reply(_answer([source]), video_thumbnail_url=None).text

    assert "file://" not in text
    assert "Fonte: Guida – Sezione A, indicizzata il 2026-11-03" in text


def test_at_most_three_fonte_lines_are_shown_in_citation_order() -> None:
    sources = [_handbook(f"{n:02d}-pagina", f"Pagina {n}") for n in range(5)]

    text = render_reply(_answer(sources), video_thumbnail_url=None).text

    assert text.count("Fonte:") == MAX_FONTE_LINES == 3
    for n in range(3):
        assert f"handbook://{n:02d}-pagina" in text
    assert "handbook://03-pagina" not in text
    assert "handbook://04-pagina" not in text


def test_the_fonte_cap_counts_distinct_sources_not_repeated_citations() -> None:
    first = _handbook("00-a", "A")
    others = [_handbook(f"0{n}-x", f"X{n}") for n in range(1, 4)]

    text = render_reply(_answer([first, first, first, *others]), video_thumbnail_url=None).text

    assert text.count("Fonte:") == 3
    assert "handbook://02-x" in text
    assert "handbook://03-x" not in text


def test_refusal_with_handbook_contact_names_the_page_the_contact_came_from() -> None:
    reply = BotReply(kind="refusal", referente=HR)

    rendered = render_reply(reply, video_thumbnail_url=THUMBNAIL)

    assert rendered.text.startswith("Non lo so, chiedi a HR (hr@example.invalid).")
    assert "Contatto dal manuale: Contatti (handbook://05-contatti)" in rendered.text


def test_no_reply_kind_other_than_answer_carries_a_card() -> None:
    video_source = _guide("V", MAPPED_VIDEO)
    replies = [
        BotReply(kind="refusal", referente=HR, sources=[video_source]),
        BotReply(kind="referral", referente=HR, sources=[video_source]),
        BotReply(kind="smalltalk", sources=[video_source]),
        BotReply(kind="error", sources=[video_source]),
    ]

    rendered = [render_reply(reply, video_thumbnail_url=THUMBNAIL) for reply in replies]

    assert [message.cards_v2 for message in rendered] == [[], [], [], []]
    referral_text = rendered[1].text
    assert referral_text.startswith("Per il tuo caso specifico chiedi a HR (hr@example.invalid).")
    assert "Contatto dal manuale: Contatti (handbook://05-contatti)" in referral_text


def test_sensitive_answer_ends_with_the_referral_sentence_after_the_fonte_lines() -> None:
    reply = _answer([_handbook("02-ferie", "Ferie e permessi")], referente=HR)

    text = render_reply(reply, video_thumbnail_url=None).text

    assert text.endswith("Per il tuo caso specifico chiedi a HR (hr@example.invalid).")
    assert text.index("Fonte: Manuale") < text.index("Per il tuo caso specifico")
    assert "Contatto dal manuale: Contatti (handbook://05-contatti)" in text


def _assert_no_soft_breaks(text: str) -> None:
    # Chat renders standard Markdown: a lone "\n" is a soft break and the lines run together.
    # Live check 2026-11-07: two "Fonte:" lines rendered on one line.
    assert "\n" not in text.replace("\n\n", "")
    assert "\n\n\n" not in text


def test_every_line_is_its_own_markdown_paragraph() -> None:
    sources = [_handbook("02-ferie", "Ferie e permessi"), _handbook("03-malattia", "Malattia")]
    answer = render_reply(_answer(sources, referente=HR), video_thumbnail_url=None).text
    refusal = render_reply(BotReply(kind="refusal", referente=HR), video_thumbnail_url=None).text
    referral = render_reply(BotReply(kind="referral", referente=HR), video_thumbnail_url=None).text

    for text in (answer, refusal, referral):
        _assert_no_soft_breaks(text)
    blocks = answer.split("\n\n")
    assert [block.split(" (")[0] for block in blocks[1:3]] == [
        "Fonte: Manuale – Ferie e permessi",
        "Fonte: Manuale – Malattia",
    ]
    assert blocks[3].startswith("Contatto dal manuale: Contatti")
    assert blocks[4].startswith("Per il tuo caso specifico chiedi a HR")
    assert refusal.split("\n\n")[1].startswith("Contatto dal manuale: Contatti")


def test_model_links_and_chat_markup_are_removed_from_the_prose() -> None:
    reply = _answer(
        [_handbook("02-ferie", "Ferie e permessi")],
        answer="Vedi https://evil.example.invalid/x e handbook://99-x <https://a|clic>",
    )

    text = render_reply(reply, video_thumbnail_url=None).text
    prose = text.split("\n\n")[0]

    assert "https://evil" not in text
    assert "handbook://99-x" not in text
    assert "<" not in prose
    assert ">" not in prose
    assert sanitize_prose("a <b> c") == "a ‹b› c"
    assert sanitize_prose("uno   due\t\ttre ") == "uno due tre"


def test_sources_keep_first_citation_order_and_each_appears_once() -> None:
    first = _handbook("02-ferie", "Ferie e permessi")
    second = _handbook("03-malattia", "Malattia")

    text = render_reply(_answer([first, second, first]), video_thumbnail_url=None).text

    assert text.count("handbook://02-ferie") == 1
    assert text.index("handbook://02-ferie") < text.index("handbook://03-malattia")


def test_long_prose_is_capped_and_the_whole_message_stays_within_the_limit() -> None:
    sources = [_handbook(f"{n:02d}-pagina", "T" * 300) for n in range(20)]

    text = render_reply(_answer(sources, answer="a" * 5000), video_thumbnail_url=None).text
    prose = text.split("\n\n")[0]

    assert len(prose) == MAX_ANSWER_CHARS == 3500
    assert prose.endswith("…")
    assert len(text) <= MAX_MESSAGE_CHARS == 4000
    assert text.endswith("revisione 2026-10-03")


def test_oversized_contact_still_leaves_a_message_within_the_limit() -> None:
    referente = Referente(role="HR", contact="x" * 5000)

    reply = BotReply(kind="refusal", referente=referente)

    text = render_reply(reply, video_thumbnail_url=None).text

    assert len(text) == MAX_MESSAGE_CHARS
    assert text.endswith("…")


def test_a_card_holds_at_most_three_video_sections_in_citation_order() -> None:
    sources = [_guide(str(n), f"https://videos.example.invalid/{n}.mp4", line=n) for n in range(5)]

    rendered = render_reply(_answer(sources), video_thumbnail_url=THUMBNAIL)

    assert MAX_VIDEO_SECTIONS == 3
    sections = rendered.cards_v2[0]["card"]["sections"]
    assert [section["header"] for section in sections] == [f"Sezione {n}" for n in range(3)]


def test_without_a_thumbnail_the_card_has_no_image_widget() -> None:
    reply = _answer([_guide("A", MAPPED_VIDEO)])

    rendered = render_reply(reply, video_thumbnail_url=None)

    widgets = rendered.cards_v2[0]["card"]["sections"][0]["widgets"]
    assert [next(iter(widget)) for widget in widgets] == ["textParagraph", "buttonList"]
    assert "imageUrl" not in json.dumps(rendered.cards_v2)


def test_a_video_url_that_is_not_http_gets_no_guarda_button() -> None:
    only_ftp = _answer([_guide("A", "ftp://x/demo.mp4")])
    mixed = _answer([_guide("A", "ftp://x/demo.mp4", line=1), _guide("B", MAPPED_VIDEO, line=9)])

    assert render_reply(only_ftp, video_thumbnail_url=THUMBNAIL).cards_v2 == []
    sections = render_reply(mixed, video_thumbnail_url=THUMBNAIL).cards_v2[0]["card"]["sections"]
    assert [section["header"] for section in sections] == ["Sezione B"]
    assert "ftp://" not in json.dumps(sections)


def test_a_source_url_that_is_not_http_gets_no_video_section() -> None:
    bad = _guide("A", MAPPED_VIDEO, line=1).model_copy(update={"source_url": "javascript:alert(1)"})
    good = _guide("B", MAPPED_VIDEO, line=9)

    assert render_reply(_answer([bad]), video_thumbnail_url=THUMBNAIL).cards_v2 == []
    sections = render_reply(_answer([bad, good]), video_thumbnail_url=THUMBNAIL).cards_v2[0][
        "card"
    ]["sections"]
    assert [section["header"] for section in sections] == ["Sezione B"]
    assert "javascript:" not in json.dumps(sections)


@pytest.mark.parametrize(
    ("raw", "kept", "gone"),
    [
        ("Apri www.evil.example ora", "Apri ora", "evil"),
        ("Vai su evil.example.com/login subito", "Vai su subito", "evil"),
        ("Vai su Evil.COM subito", "Vai su subito", "Evil"),
        ("Scrivi a mailto:x@y.invalid per info", "Scrivi a per info", "mailto"),
        ("Scarica ftp://files.example.invalid/a.zip qui", "Scarica qui", "ftp"),
        ("Scrivi a mario.rossi@azienda.example.org oggi", "Scrivi a oggi", "@"),
        ("Leggi [il portale](https://evil.example/x) ora", "Leggi il portale ora", "evil"),
        ("Leggi ![logo](https://evil.example/i.png) ora", "Leggi logo ora", "evil"),
        ("Apri https://evil.example/x.", "Apri.", "evil"),
    ],
)
def test_sanitize_prose_removes_every_link_form(raw: str, kept: str, gone: str) -> None:
    cleaned = sanitize_prose(raw)

    assert cleaned == kept
    assert gone not in cleaned


@pytest.mark.parametrize(
    "prose",
    [
        "Es. e.g. i.e. vale per tutti.",
        "Il bonus e 3.5 giorni, circa 12.50 euro.",
        "Usa la versione v1.2.3 del manuale.",
        "Apri il file main.py o config.yaml.",
        "Dalle 9.30 alle 17.45, Dr. Rossi risponde.",
        "Scrivi al responsabile diretto (HR) entro venerdi.",
    ],
)
def test_sanitize_prose_leaves_normal_prose_alone(prose: str) -> None:
    assert sanitize_prose(prose) == prose
