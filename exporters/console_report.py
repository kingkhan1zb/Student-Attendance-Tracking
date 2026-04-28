"""
Console report renderer using the Rich library.
"""

from __future__ import annotations

from typing import List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from core.models import AttendanceStatus, StudentRecord

console = Console()


def print_report(records: List[StudentRecord], threshold: float = 75.0) -> None:
    """
    Print a rich, colour-coded attendance report to the console.

    Args:
        records: List of StudentRecord objects.
        threshold: The attendance threshold used.
    """
    ok = [r for r in records if r.status == AttendanceStatus.OK]
    shortage = [r for r in records if r.status == AttendanceStatus.SHORTAGE]
    avg = sum(r.attendance_percentage for r in records) / len(records) if records else 0

    # ── Header ─────────────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel.fit(
            "[bold white]📋 Student Attendance Report[/bold white]\n"
            f"[dim]Threshold: {threshold}%  |  Total Students: {len(records)}  |  "
            f"Avg Attendance: {avg:.1f}%[/dim]",
            border_style="navy_blue",
            padding=(1, 4),
        )
    )
    console.print()

    # ── KPI row ────────────────────────────────────────────────────────────────
    kpi_table = Table(box=box.ROUNDED, show_header=False, padding=(0, 3))
    kpi_table.add_column(justify="center")
    kpi_table.add_column(justify="center")
    kpi_table.add_column(justify="center")

    kpi_table.add_row(
        f"[bold blue]Total Students[/bold blue]\n[bold white on blue] {len(records)} [/bold white on blue]",
        f"[bold green]✅ Meeting Threshold[/bold green]\n[bold white on green] {len(ok)} [/bold white on green]",
        f"[bold red]⚠️  Below Threshold[/bold red]\n[bold white on red] {len(shortage)} [/bold white on red]",
    )
    console.print(kpi_table)
    console.print()

    # ── Main table ─────────────────────────────────────────────────────────────
    table = Table(
        title="[bold navy_blue]Attendance Records[/bold navy_blue]",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold white on navy_blue",
        title_style="bold",
        padding=(0, 1),
    )

    table.add_column("#", style="dim", justify="right", width=3)
    table.add_column("Student Name", min_width=20)
    table.add_column("Roll No.", justify="center", min_width=10)
    table.add_column("Total", justify="center", width=7)
    table.add_column("Attended", justify="center", width=9)
    table.add_column("Attendance %", justify="center", width=13)
    table.add_column("Deficit", justify="center", width=8)
    table.add_column("Status", justify="center", width=12)

    for idx, record in enumerate(records, start=1):
        is_shortage = record.status == AttendanceStatus.SHORTAGE
        pct = record.attendance_percentage
        row_style = "on grey93" if idx % 2 == 0 and not is_shortage else ""

        pct_text = Text(f"{pct:.1f}%")
        if pct >= threshold:
            pct_text.stylize("bold green")
        elif pct >= threshold - 10:
            pct_text.stylize("bold yellow")
        else:
            pct_text.stylize("bold red")

        status_text = (
            "[bold green]✅ OK[/bold green]"
            if not is_shortage
            else "[bold red]⚠️ Shortage[/bold red]"
        )
        deficit = str(record.deficit_classes) if record.deficit_classes > 0 else "[dim]—[/dim]"

        table.add_row(
            str(idx),
            f"[bold]{record.name}[/bold]" if is_shortage else record.name,
            record.roll_number,
            str(record.total_classes),
            str(record.classes_attended),
            pct_text,
            deficit,
            status_text,
            style="on misty_rose1" if is_shortage else row_style,
        )

    console.print(table)
    console.print()

    # ── Flagged students with AI warnings ──────────────────────────────────────
    if shortage:
        console.print(
            Panel(
                "\n".join(
                    f"[bold red]{r.name}[/bold red] ({r.roll_number}) — "
                    f"[yellow]{r.attendance_percentage:.1f}%[/yellow], "
                    f"needs [cyan]{r.deficit_classes}[/cyan] more class(es)\n"
                    + (f"  [dim italic]{r.ai_warning}[/dim italic]" if r.ai_warning else "")
                    for r in shortage
                ),
                title="[bold red]⚠️  Students Below Threshold[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        console.print()
