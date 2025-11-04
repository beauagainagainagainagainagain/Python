"""Example use case inspired by Google Gemini.

The real [Google Gemini](https://deepmind.google/technologies/gemini/) family
of models is designed to operate in a multimodal setting (text, image, audio,
and more) while also supporting reasoning and structured output.

This module implements a light-weight, fully local simulation of a possible
workflow that such a model could enable: automatically summarising the key
moments of a meeting by combining textual notes, image observations, and
structured action items.  The goal of the example is educational – showing how
one could *organise* information for a multimodal model, not to replicate any
proprietary model behaviour.

The :class:`GeminiMeetingSummarizer` exposes two public methods:

``summarize``
    Produces a human readable summary string.

``build_structured_report``
    Produces a JSON-serialisable dictionary emphasising the same information
    but in a machine friendly format.

Both methods rely on simple, deterministic heuristics to keep the example
self-contained and easy to test.  Nevertheless, the overall flow mirrors a real
Gemini use case:

1. Gather information from multiple modalities (textual notes and image
   observations).
2. Extract salient talking points via keyword scoring.
3. Merge the salient points with previously computed action items.
4. Return both natural language and structured artefacts.

Example
-------

>>> documents = [
...     MeetingDocument(
...         title="Roadmap discussion",
...         content="We reviewed Q3 targets and prioritised the Gemini launch.",
...     ),
...     MeetingDocument(
...         title="Budget",
...         content="Marketing receives additional funds to prepare promo videos.",
...     ),
... ]
>>> observations = [
...     ImageObservation(description="Slide showing Gemini app mock-ups."),
... ]
>>> action_items = [
...     ActionItem(owner="Alex", task="Draft launch blog post", due_date="2024-06-18"),
... ]
>>> summarizer = GeminiMeetingSummarizer()
>>> summarizer.summarize(documents, observations, action_items)
'Key updates: Gemini launch prioritised. Marketing receives additional funds. Visual assets reviewed from slides. Action items: Alex to Draft launch blog post by 2024-06-18.'

Even though the underlying logic is intentionally straightforward, the
structure of the code demonstrates how a developer might prepare data for a
multimodal, reasoning-centric assistant such as Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "that",
    "the",
    "to",
    "we",
}


@dataclass(frozen=True)
class MeetingDocument:
    """Represents a textual artefact discussed during a meeting."""

    title: str
    content: str


@dataclass(frozen=True)
class ImageObservation:
    """Stores a short natural language description of an observed visual."""

    description: str


@dataclass(frozen=True)
class ActionItem:
    """Represents a structured task decided in the meeting."""

    owner: str
    task: str
    due_date: str


class GeminiMeetingSummarizer:
    """Summarises meeting artefacts in the spirit of a Gemini-style workflow."""

    def summarize(
        self,
        documents: Sequence[MeetingDocument],
        observations: Sequence[ImageObservation],
        action_items: Sequence[ActionItem],
    ) -> str:
        """Return a readable summary of the provided meeting artefacts."""

        highlights = self._generate_highlights(documents, observations)
        actions = self._render_actions(action_items)

        if highlights:
            sentence = "Key updates: " + " ".join(highlights)
        else:
            sentence = "No textual highlights captured."

        if actions:
            sentence += f" Action items: {actions}."
        else:
            sentence += " No action items captured."

        return sentence.strip()

    def build_structured_report(
        self,
        documents: Sequence[MeetingDocument],
        observations: Sequence[ImageObservation],
        action_items: Sequence[ActionItem],
    ) -> dict[str, object]:
        """Return a JSON-serialisable representation of the meeting."""

        highlights = self._generate_highlights(documents, observations)
        return {
            "highlights": highlights,
            "action_items": [
                {
                    "owner": item.owner,
                    "task": item.task,
                    "due_date": item.due_date,
                }
                for item in action_items
            ],
            "source_documents": [
                {"title": doc.title, "content": doc.content}
                for doc in documents
            ],
            "visual_observations": [
                observation.description for observation in observations
            ],
        }

    @staticmethod
    def _generate_highlights(
        documents: Sequence[MeetingDocument],
        observations: Sequence[ImageObservation],
    ) -> list[str]:
        highlights = []

        for doc in documents:
            summary = _first_relevant_sentence(doc.content)
            if summary:
                highlights.append(summary)

        if observations:
            visual_summary = _summarise_visuals(observations)
            highlights.append(visual_summary)

        return highlights

    @staticmethod
    def _render_actions(action_items: Sequence[ActionItem]) -> str:
        if not action_items:
            return ""

        formatted = [
            f"{item.owner} to {item.task} by {item.due_date}"
            for item in action_items
        ]
        return "; ".join(formatted)


def _first_relevant_sentence(text: str) -> str:
    """Return the first sentence containing a meaningful keyword."""

    sentences = _split_into_sentences(text)
    if not sentences:
        return ""

    best_sentence = ""
    best_score = 0
    for sentence in sentences:
        score = _keyword_score(sentence)
        if score > best_score:
            best_sentence = sentence
            best_score = score

    return best_sentence if best_sentence else sentences[0]


def _split_into_sentences(text: str) -> list[str]:
    candidate = [part.strip() for part in text.replace("\n", " ").split(".")]
    return [sentence for sentence in candidate if sentence]


def _keyword_score(sentence: str) -> int:
    score = 0
    for word in sentence.split():
        word = _normalise_word(word)
        if len(word) > 3 and word not in STOPWORDS:
            score += 1
    return score


def _normalise_word(word: str) -> str:
    return "".join(char for char in word.lower() if char.isalpha())


def _summarise_visuals(observations: Iterable[ImageObservation]) -> str:
    keywords = []
    for observation in observations:
        keywords.extend(
            word
            for word in map(_normalise_word, observation.description.split())
            if word and word not in STOPWORDS
        )

    if not keywords:
        return "Visuals reviewed with no prominent details."

    primary = _select_top_keywords(keywords)
    return f"Visual assets reviewed from {' '.join(primary)}." if primary else (
        "Visuals reviewed with no prominent details."
    )


def _select_top_keywords(words: Iterable[str], limit: int = 3) -> list[str]:
    frequency: dict[str, int] = {}
    for word in words:
        frequency[word] = frequency.get(word, 0) + 1

    ranked = sorted(
        frequency.items(), key=lambda item: (-item[1], item[0])
    )
    return [word for word, _ in ranked[:limit]]


__all__ = [
    "ActionItem",
    "GeminiMeetingSummarizer",
    "ImageObservation",
    "MeetingDocument",
]

