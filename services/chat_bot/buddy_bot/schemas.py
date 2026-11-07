"""Typed values the workflow passes around: retrieved evidence, model outputs and the reply."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    """One retrieved source, built only from tool results of the current run (BOT-05)."""

    model_config = ConfigDict(frozen=True)

    source_url: str
    kind: Literal["handbook", "guides"]
    title: str
    text: str
    revision_date: str
    revision_kind: Literal["last_updated", "indexed_on"]
    video_url: str | None = None


class Referente(BaseModel):
    """The person or role a refusal or referral points to; the contact is quoted, never made up."""

    model_config = ConfigDict(frozen=True)

    role: str
    contact: str | None = None
    contact_source: Evidence | None = None


class Reformulation(BaseModel):
    """Output of the reformulation step (Haiku): standalone question and search keywords."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    standalone_question: str = Field(min_length=1)
    keywords_it: list[str] = Field(min_length=1, max_length=5)
    keywords_en: list[str] = Field(min_length=1, max_length=5)
    intent: Literal["question", "chitchat", "off_topic"]
    sensitive_topic: str | None = None


class RetryPlan(BaseModel):
    """Output of the retry step: different keywords for the single retrieval retry (D-03)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    keywords_it: list[str] = Field(min_length=1, max_length=5)
    keywords_en: list[str] = Field(min_length=1, max_length=5)


class ContactExtraction(BaseModel):
    """Output of the contact step: a contact copied from a handbook page, or null (D-04)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    contact: str | None = None
    source_url: str | None = None


class AnswerDraft(BaseModel):
    """Output of the answer step (Sonnet): untrusted until the gate has checked the citations."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    answer: str
    citations: list[str]
    grounded: bool
    confidence: float = Field(ge=0, le=1)


class BotReply(BaseModel):
    """What the bot says; rendered into a Chat message by render.py."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["answer", "refusal", "referral", "smalltalk", "error"]
    answer: str = ""
    sources: list[Evidence] = Field(default_factory=list)
    referente: Referente | None = None
    gap_reported: bool = False
    gate_reason: str | None = None
