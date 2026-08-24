"""
Shared types for the curriculum data layer.
Used by all language curriculum modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
LessonType = Literal[
    "grammar",
    "vocabulary",
    "reading",
    "writing",
    "listening",
    "speaking",
    "review",
]


@dataclass
class CurriculumUnit:
    id: str  # e.g. "a1-unit-1"
    level: str
    unit_number: int
    title: str
    grammar_points: list[str]
    vocabulary_set_ids: list[str]
    lesson_types: list[LessonType]
    competency_checklist: list[str]
    default_weeks: int
    prerequisite_unit: str | None = None


Skill = Literal["grammar", "vocabulary", "reading"]


@dataclass
class AssessmentQuestion:
    id: str  # e.g. "g-a1-001", "v-b2-003", "r-c1-001"
    skill: Skill
    difficulty: CEFRLevel
    question: str
    options: list[str]  # exactly 4
    correct: str  # must match one option exactly
    grammar_slug: str | None = None


PartOfSpeech = Literal[
    "noun",
    "verb",
    "adjective",
    "adverb",
    "phrase",
    "conjunction",
    "preposition",
    "numeral",
    "pronoun",
]


@dataclass
class VocabularyEntry:
    word: str
    pos: PartOfSpeech
    definition: str
    example: str
    ipa: str | None = None
    frequency_rank: int | None = None


@dataclass
class VocabularySet:
    id: str  # e.g. "identity_a1", "saludos_es_a1"
    level: CEFRLevel
    topic: str
    unit_ref: str  # e.g. "a1-unit-1"
    words: list[VocabularyEntry]


Register = Literal["formal", "neutral", "informal"]


@dataclass
class PhrasebookEntry:
    text: str  # the phrase in the target language
    context: str  # when/where to use it
    register: Register
    unit_ref: str | None = None
    romanization: str | None = None  # pinyin / romaji / revised-romanization


@dataclass
class PhrasebookCategory:
    id: str  # e.g. "greetings", "restaurant_a2"
    level: CEFRLevel
    situation: str  # e.g. "Greetings & Introductions"
    icon: str  # single emoji, e.g. "👋"
    phrases: list[PhrasebookEntry]


@dataclass
class GrammarExample:
    text: str  # the example sentence in the target language
    translation: str | None = None
    note: str | None = None


@dataclass
class GrammarMistake:
    wrong: str
    correct: str
    note: str


@dataclass
class GrammarTopic:
    slug: str  # e.g. "present-simple", "ser"
    title: str
    level: CEFRLevel
    category: str  # language-specific grammar category
    summary: str
    explanation: str  # Markdown-lite
    structure: str | None = None
    rules: list[str] = field(default_factory=list)
    examples: list[GrammarExample] = field(default_factory=list)
    common_mistakes: list[GrammarMistake] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
