"""Unit tests for the Google Gemini inspired use case."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from other.google_gemini_use_case import (
    ActionItem,
    GeminiMeetingSummarizer,
    ImageObservation,
    MeetingDocument,
)


def build_sample_data():
    documents = [
        MeetingDocument(
            title="Roadmap",
            content=(
                "We reviewed Q3 targets. Gemini launch remains the top priority "
                "with additional focus on reliability testing."
            ),
        ),
        MeetingDocument(
            title="Budget",
            content=(
                "Marketing receives extra funds for promotional videos. Support "
                "teams asked for analytics dashboard improvements."
            ),
        ),
    ]
    observations = [
        ImageObservation(description="Slides showing updated Gemini app mock ups"),
        ImageObservation(description="Chart comparing engagement metrics"),
    ]
    action_items = [
        ActionItem(owner="Alex", task="Draft launch blog post", due_date="2024-06-18"),
        ActionItem(owner="Jody", task="Prepare testing checklist", due_date="2024-06-11"),
    ]
    return documents, observations, action_items


def test_summarize_produces_keyword_rich_sentence():
    documents, observations, action_items = build_sample_data()

    summary = GeminiMeetingSummarizer().summarize(
        documents, observations, action_items
    )

    assert "Gemini launch remains the top priority" in summary
    assert "Visual assets reviewed" in summary
    assert "Alex to Draft launch blog post" in summary
    assert summary.endswith("2024-06-11.")


def test_structured_report_contains_expected_sections():
    documents, observations, action_items = build_sample_data()

    report = GeminiMeetingSummarizer().build_structured_report(
        documents, observations, action_items
    )

    assert {"highlights", "action_items", "source_documents", "visual_observations"} <= (
        report.keys()
    )
    assert len(report["action_items"]) == 2
    assert len(report["visual_observations"]) == 2
    assert report["action_items"][0]["owner"] == "Alex"

