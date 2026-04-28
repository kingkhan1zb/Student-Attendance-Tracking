"""
Student Attendance Management System — CLI Tool.

Usage:
    python cli.py input.csv
    python cli.py input.xlsx --threshold 80 --output pdf
    python cli.py input.csv --ai --output excel --out-file report.xlsx
"""

from __future__ import annotations

import argparse
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="attendance",
        description="📋 Student Attendance Management System — process attendance data and generate reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py sample_input.csv
  python cli.py data.xlsx --threshold 80
  python cli.py data.csv --output excel --out-file report.xlsx
  python cli.py data.csv --ai --output pdf --out-file report.pdf
        """,
    )
    parser.add_argument("file", help="Path to input CSV or XLSX file.")
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=75.0,
        metavar="PCT",
        help="Attendance threshold percentage (default: 75).",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["console", "excel", "pdf", "csv"],
        default="console",
        help="Output format (default: console).",
    )
    parser.add_argument(
        "--out-file", "-f",
        default=None,
        metavar="PATH",
        help="Output file path (auto-named if not specified).",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Generate AI-powered warning messages for flagged students.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress informational output (warnings and errors still shown).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.quiet:
        logging.getLogger().setLevel(logging.INFO)

    # ── Import here to avoid slow startup for --help ────────────────────────
    from core.ingestion import parse_file, DataIngestionError
    from core.models import AttendanceStatus
    from core.ai_warnings import generate_warnings_for_flagged
    from exporters.console_report import print_report
    from exporters.excel_exporter import export_excel
    from exporters.pdf_exporter import export_pdf

    # ── Read input file ─────────────────────────────────────────────────────
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}", file=sys.stderr)
        return 1

    print(f"📂 Reading: {input_path.name}")
    try:
        records, warnings = parse_file(str(input_path), input_path.name, threshold=args.threshold)
    except DataIngestionError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if warnings:
        print(f"⚠️  {len(warnings)} parsing warning(s):")
        for w in warnings:
            print(f"   • {w}")

    print(f"✅ Loaded {len(records)} student records.")

    # ── AI warnings ─────────────────────────────────────────────────────────
    if args.ai:
        flagged = [r for r in records if r.status == AttendanceStatus.SHORTAGE]
        if flagged:
            print(f"🤖 Generating AI warnings for {len(flagged)} flagged student(s)…")
            def progress(cur, tot, name):
                print(f"   [{cur}/{tot}] {name}")
            records = generate_warnings_for_flagged(records, progress_callback=progress)
        else:
            print("✅ No flagged students — skipping AI warnings.")

    # ── Output ───────────────────────────────────────────────────────────────
    if args.output == "console":
        print_report(records, threshold=args.threshold)
        return 0

    elif args.output == "excel":
        out_path = Path(args.out_file or "attendance_report.xlsx")
        data = export_excel(records, threshold=args.threshold)
        out_path.write_bytes(data)
        print(f"📊 Excel report saved: {out_path.resolve()}")

    elif args.output == "pdf":
        out_path = Path(args.out_file or "attendance_report.pdf")
        data = export_pdf(records, threshold=args.threshold)
        out_path.write_bytes(data)
        print(f"📄 PDF report saved: {out_path.resolve()}")

    elif args.output == "csv":
        import pandas as pd
        out_path = Path(args.out_file or "attendance_report.csv")
        rows = [r.to_dict() for r in records]
        pd.DataFrame(rows).to_csv(out_path, index=False)
        print(f"📋 CSV report saved: {out_path.resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
