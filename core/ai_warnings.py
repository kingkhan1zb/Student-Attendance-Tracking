"""
AI-powered warning message generator for flagged students.
Uses the Groq (Grok) API to create personalised, formal warning messages.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from groq import Groq  # ← REPLACED anthropic

from core.models import StudentRecord, AttendanceStatus

logger = logging.getLogger(__name__)

_CLIENT: Optional[Groq] = None


def _get_client() -> Groq:
    """Return a cached Groq client using a hardcoded API key."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = Groq(
            api_key="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"   # ← Paste your real key here
        )
    return _CLIENT


def _build_prompt(record: StudentRecord) -> str:
    """
    Build a prompt for generating a personalised warning message.
    """

    return (
        f"Generate a single, formal, concise academic warning message for a student with these details:\n"
        f"- Name: {record.name}\n"
        f"- Attendance: {record.attendance_percentage}%\n"
        f"- Required threshold: {record.threshold}%\n"
        f"- Additional classes needed: {record.deficit_classes}\n\n"
        f"Requirements:\n"
        f"1. Address the student by their full name.\n"
        f"2. State attendance clearly.\n"
        f"3. Mention how many more classes they must attend.\n"
        f"4. Tone must be formal and respectful.\n"
        f"5. Keep it 2–3 sentences maximum.\n"
        f"6. DO NOT add subject lines, signatures, or extra text.\n\n"
        f"Example style: \"Dear [Name], your attendance currently stands at [X]%, which is below the required "
        f"threshold of [T]%. You are required to attend [Y] additional classes to meet the minimum requirement. "
        f"Please ensure regular attendance moving forward.\""
    )


def generate_warning(record: StudentRecord, retries: int = 2) -> str:
    """
    Generate an AI warning message for a single student.
    """

    client = _get_client()
    prompt = _build_prompt(record)

    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="grok-2-latest",  # ← REPLACED Claude model
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.2,
            )

            text = response.choices[0].message["content"].strip()
            logger.debug("AI warning generated for '%s' on attempt %d.", record.name, attempt + 1)
            return text

        except Exception as exc:
            # Groq does not have Anthropic-style subclasses → handle generally
            wait = 2 ** attempt
            logger.warning("Groq API issue on attempt %d. Waiting %ds. Error: %s", attempt + 1, wait, exc)

            if attempt < retries:
                time.sleep(wait)
            else:
                logger.error("Groq API failed for '%s': %s", record.name, exc)

    # Fallback if API fails
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

        if i < total:
            time.sleep(0.3)  # Gentle rate-limit spacing

    return records