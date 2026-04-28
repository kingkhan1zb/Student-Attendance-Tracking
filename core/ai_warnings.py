"""
AI-powered warning message generator for flagged students.
Uses the Anthropic Messages API to create personalised, formal warning messages.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import anthropic

from core.models import StudentRecord, AttendanceStatus

logger = logging.getLogger(__name__)

_CLIENT: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    """Return a cached Anthropic client."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = anthropic.Anthropic()
    return _CLIENT


def _build_prompt(record: StudentRecord) -> str:
    """
    Build a prompt for generating a personalised warning message.

    Args:
        record: The student's attendance record.

    Returns:
        Formatted prompt string.
    """
    return (
        f"Generate a single, formal, concise academic warning message for a student with the following details:\n"
        f"- Name: {record.name}\n"
        f"- Attendance: {record.attendance_percentage}%\n"
        f"- Required threshold: {record.threshold}%\n"
        f"- Additional classes needed to meet the requirement: {record.deficit_classes}\n\n"
        f"Requirements:\n"
        f"1. Address the student by their full name.\n"
        f"2. State their current attendance percentage clearly.\n"
        f"3. Mention the number of additional classes they must attend.\n"
        f"4. Keep the tone formal and respectful.\n"
        f"5. Keep it to 2-3 sentences maximum.\n"
        f"6. Do NOT include a subject line, signature, or any extra text — just the message body.\n\n"
        f"Example style: \"Dear [Name], your attendance currently stands at [X]%, which is below the required "
        f"threshold of [T]%. You are required to attend [Y] more classes to meet the minimum requirement. "
        f"Please ensure regular attendance going forward.\""
    )


def generate_warning(record: StudentRecord, retries: int = 2) -> str:
    """
    Generate an AI warning message for a single student.

    Args:
        record: Student record (should be in Shortage status).
        retries: Number of retry attempts on transient failures.

    Returns:
        Warning message string, or a fallback message on failure.
    """
    client = _get_client()
    prompt = _build_prompt(record)

    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            logger.debug("AI warning generated for '%s' on attempt %d.", record.name, attempt + 1)
            return text

        except anthropic.RateLimitError:
            wait = 2 ** attempt
            logger.warning("Rate limit hit. Waiting %ds before retry %d.", wait, attempt + 1)
            time.sleep(wait)

        except anthropic.APIError as exc:
            logger.error("Anthropic API error for '%s': %s", record.name, exc)
            break

    # Fallback: deterministic message if API fails
    return (
        f"Dear {record.name}, your attendance currently stands at {record.attendance_percentage}%, "
        f"which is below the required threshold of {record.threshold}%. "
        f"Please attend {record.deficit_classes} more class(es) to meet the minimum requirement."
    )


def generate_warnings_for_flagged(
    records: List[StudentRecord],
    progress_callback=None,
) -> List[StudentRecord]:
    """
    Generate AI warning messages for all students with attendance shortage.

    Args:
        records: Full list of student records.
        progress_callback: Optional callable(current, total, name) for UI progress updates.

    Returns:
        Same list with ai_warning field populated for flagged students.
    """
    flagged = [r for r in records if r.status == AttendanceStatus.SHORTAGE]
    total = len(flagged)

    if total == 0:
        logger.info("No flagged students — skipping AI warning generation.")
        return records

    logger.info("Generating AI warnings for %d flagged student(s)...", total)

    for i, record in enumerate(flagged, start=1):
        if progress_callback:
            progress_callback(i, total, record.name)
        record.ai_warning = generate_warning(record)
        # Brief pause to be respectful of API rate limits
        if i < total:
            time.sleep(0.3)

    return records
