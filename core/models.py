"""
Data models for the Student Attendance Management System.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class AttendanceStatus(str, Enum):
    """Attendance status for a student."""
    OK = "✅ OK"
    SHORTAGE = "⚠️ Shortage"


@dataclass
class StudentRecord:
    """
    Represents a single student's attendance record.

    Attributes:
        name: Full name of the student.
        roll_number: Unique roll number identifier.
        total_classes: Total number of classes held.
        classes_attended: Number of classes the student attended.
        threshold: Minimum required attendance percentage (0–100).
    """

    name: str
    roll_number: str
    total_classes: int
    classes_attended: int
    threshold: float = 75.0
    ai_warning: Optional[str] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate and sanitize fields after initialization."""
        self.name = str(self.name).strip()
        self.roll_number = str(self.roll_number).strip()

        if self.total_classes < 0:
            raise ValueError(f"total_classes cannot be negative for '{self.name}'.")
        if self.classes_attended < 0:
            raise ValueError(f"classes_attended cannot be negative for '{self.name}'.")
        if self.classes_attended > self.total_classes and self.total_classes > 0:
            raise ValueError(
                f"classes_attended ({self.classes_attended}) exceeds "
                f"total_classes ({self.total_classes}) for '{self.name}'."
            )

    @property
    def attendance_percentage(self) -> float:
        """Attendance percentage, returns 0.0 if no classes were held."""
        if self.total_classes == 0:
            return 0.0
        return round((self.classes_attended / self.total_classes) * 100, 2)

    @property
    def status(self) -> AttendanceStatus:
        """Whether the student meets the attendance threshold."""
        return (
            AttendanceStatus.OK
            if self.attendance_percentage >= self.threshold
            else AttendanceStatus.SHORTAGE
        )

    @property
    def deficit_classes(self) -> int:
        """
        Number of additional classes needed to meet the threshold.
        Returns 0 if already meeting or exceeding the threshold.

        Formula:
            classes_needed = ceil((threshold% * total) - attended) / (1 - threshold%)
            But we solve: attended + x >= threshold * (total + x)
            => x >= (threshold * total - attended) / (1 - threshold)
        """
        if self.status == AttendanceStatus.OK:
            return 0
        if self.threshold >= 100.0:
            return self.total_classes - self.classes_attended
        threshold_ratio = self.threshold / 100.0
        numerator = threshold_ratio * self.total_classes - self.classes_attended
        denominator = 1.0 - threshold_ratio
        if denominator <= 0:
            return 0
        import math
        return max(0, math.ceil(numerator / denominator))

    def to_dict(self) -> dict:
        """Serialize record to a plain dictionary for DataFrame/export use."""
        return {
            "Student Name": self.name,
            "Roll Number": self.roll_number,
            "Total Classes": self.total_classes,
            "Classes Attended": self.classes_attended,
            "Attendance %": self.attendance_percentage,
            "Deficit Classes": self.deficit_classes,
            "Status": self.status.value,
            "AI Warning": self.ai_warning or "",
        }
