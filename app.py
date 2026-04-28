"""
Student Attendance Management System — Streamlit Web Application.

Run with:
    python -m streamlit run app.py
"""

from __future__ import annotations

import io
import logging
import traceback
from typing import List, Optional

import pandas as pd
import streamlit as st

from core.ingestion import parse_file, DataIngestionError
from core.models import StudentRecord, AttendanceStatus
from core.ai_warnings import generate_warnings_for_flagged
from exporters.excel_exporter import export_excel
from exporters.pdf_exporter import export_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Attendance Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Global App Background ───────────────────────────── */
    .stApp {
        background-color: var(--background-color);
        color: var(--text-color);
    }

    /* ── Metric Cards ───────────────────────────────────── */
    div[data-testid="metric-container"] {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }

    div[data-testid="metric-container"] label {
        color: var(--text-color) !important;
        opacity: 0.7;
        font-size: 13px !important;
    }

    div[data-testid="metric-container"] div[data-testid="metric-value"] {
        color: var(--text-color) !important;
        font-size: 28px !important;
        font-weight: 700 !important;
    }

    /* ── Section Headers ────────────────────────────────── */
    .section-header {
        color: var(--text-color);
        font-size: 18px;
        font-weight: 700;
        margin: 20px 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid var(--primary-color);
    }

    /* ── Warning Card ───────────────────────────────────── */
    .warning-card {
        background: rgba(255, 165, 0, 0.12);
        border-left: 4px solid orange;
        border-radius: 6px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 14px;
        color: var(--text-color);
    }

    /* ── Info Box ───────────────────────────────────────── */
    .info-box {
        background: var(--secondary-background-color);
        border-radius: 10px;
        padding: 14px 18px;
        margin: 10px 0;
        font-size: 14px;
        color: var(--text-color);
        border: 1px solid rgba(128,128,128,0.15);
    }

    /* ── Buttons ────────────────────────────────────────── */
    div[data-testid="stDownloadButton"] button,
    div[data-testid="stButton"] button {
    background-color: var(--primary-color) !important;
    color: var(--text-color) !important;

    border: 1px solid rgba(128, 128, 128, 0.4);  /* ✅ adaptive border */
    border-radius: 8px !important;

    font-weight: 600 !important;
    padding: 8px 20px !important;

    transition: all 0.2s ease;
    }

    div[data-testid="stDownloadButton"] button:hover,
    div[data-testid="stButton"] button:hover {
        filter: brightness(1.1);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }

    /* ── Sidebar ────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: var(--secondary-background-color);
    }

    /* REMOVE forced white text — let Streamlit handle it */

    /* ── DataFrame Tweaks ───────────────────────────────── */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* ── Subtle Scrollbar (optional polish) ─────────────── */
    ::-webkit-scrollbar {
        height: 8px;
        width: 8px;
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(120,120,120,0.4);
        border-radius: 6px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(120,120,120,0.6);
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state helpers ──────────────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "records": None,
        "parse_warnings": [],
        "ai_generated": False,
        "filename": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _reset_state() -> None:
    st.session_state.records = None
    st.session_state.parse_warnings = []
    st.session_state.ai_generated = False
    st.session_state.filename = ""


# ── DataFrame rendering ────────────────────────────────────────────────────────

def _records_to_df(records: List[StudentRecord]) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append({
            "Student Name": r.name,
            "Roll Number": r.roll_number,
            "Total Classes": r.total_classes,
            "Classes Attended": r.classes_attended,
            "Attendance %": r.attendance_percentage,
            "Deficit Classes": r.deficit_classes,
            "Status": r.status.value,
            "AI Warning": r.ai_warning or "",
        })
    return pd.DataFrame(rows)


def _style_dataframe(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def row_style(row):
        if "⚠️" in str(row.get("Status", "")):
            return ["background-color: #FCE4D6; color: #7F0000"] * len(row)
        return [""] * len(row)

    def pct_color(val):
        try:
            v = float(val)
            if v >= 85:
                return "color: #274E13; font-weight: 700"
            elif v >= 75:
                return "color: #1A5276; font-weight: 600"
            elif v >= 60:
                return "color: #D4AC0D; font-weight: 600"
            else:
                return "color: #922B21; font-weight: 700"
        except (TypeError, ValueError):
            return ""

    styled = (
        df.style
        .apply(row_style, axis=1)
        .map(pct_color, subset=["Attendance %"])
        .format({"Attendance %": "{:.1f}%"})
        .set_properties(**{"text-align": "center"}, subset=["Roll Number", "Total Classes",
                                                              "Classes Attended", "Attendance %",
                                                              "Deficit Classes"])
    )
    return styled


# ── Main application ───────────────────────────────────────────────────────────

def main() -> None:
    _init_state()

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 📋 Attendance System")
        st.markdown("---")

        st.markdown("### ⚙️ Configuration")
        threshold = st.slider(
            "Attendance Threshold (%)",
            min_value=50,
            max_value=100,
            value=75,
            step=1,
            help="Students below this percentage are flagged as 'Shortage'.",
        )

        st.markdown("---")
        st.markdown("### 🤖 AI Features")
        use_ai = st.checkbox(
            "Generate AI Warnings",
            value=True,
            help="Use Claude AI to generate personalised warning messages for flagged students.",
        )

        st.markdown("---")
        st.markdown("### 📁 Upload File")
        uploaded_file = st.file_uploader(
            "Choose CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            help="Upload your attendance data file.",
        )

        if uploaded_file:
            if st.button("🔄 Process File", use_container_width=True):
                _reset_state()
                st.session_state.filename = uploaded_file.name
                with st.spinner("Parsing attendance data…"):
                    try:
                        records, warnings = parse_file(
                            io.BytesIO(uploaded_file.read()),
                            uploaded_file.name,
                            threshold=float(threshold),
                        )
                        st.session_state.records = records
                        st.session_state.parse_warnings = warnings
                        st.success(f"✅ Loaded {len(records)} student records.")
                    except DataIngestionError as exc:
                        st.error(f"❌ {exc}")
                    except Exception:
                        st.error("An unexpected error occurred. Please check the file format.")
                        logger.error(traceback.format_exc())

        if st.session_state.records and use_ai and not st.session_state.ai_generated:
            if st.button("🤖 Generate AI Warnings", use_container_width=True):
                flagged = [r for r in st.session_state.records if r.status == AttendanceStatus.SHORTAGE]
                if not flagged:
                    st.info("No flagged students — all attendance is above threshold.")
                else:
                    progress = st.progress(0, text="Generating AI warnings…")
                    def update_progress(current, total, name):
                        pct = current / total
                        progress.progress(pct, text=f"Processing {name}… ({current}/{total})")

                    try:
                        st.session_state.records = generate_warnings_for_flagged(
                            st.session_state.records,
                            progress_callback=update_progress,
                        )
                        st.session_state.ai_generated = True
                        progress.progress(1.0, text="Done!")
                        st.success("✅ AI warnings generated!")
                    except Exception as exc:
                        st.warning(f"AI generation partially failed: {exc}")
                        st.session_state.ai_generated = True

        st.markdown("---")
        st.markdown(
            "<small style='color:#8BAFD4'>Built with Streamlit · Pandas · ReportLab · OpenPyXL · Claude AI</small>",
            unsafe_allow_html=True,
        )

    # ── Main content ───────────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='color:#1F3864; margin-bottom:0'>📋 Student Attendance Management System</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:#666; font-size:15px'>Threshold: <b>{threshold}%</b></p>",
        unsafe_allow_html=True,
    )

    records: Optional[List[StudentRecord]] = st.session_state.records

    if not records:
        # ── Landing page ────────────────────────────────────────────────────────
        st.markdown("<div class='info-box'>", unsafe_allow_html=True)
        st.markdown(
            "### 👈 Get Started\n"
            "1. Upload your attendance CSV or Excel file from the sidebar\n"
            "2. Set your attendance threshold\n"
            "3. Click **Process File** to analyse\n"
            "4. Optionally generate AI-powered warning messages\n"
            "5. Download reports in Excel or PDF format",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### 📄 Expected File Format")
        sample_df = pd.DataFrame({
            "Student Name": ["Ahmed Ali", "Fatima Khan"],
            "Roll Number": ["CS-001", "CS-002"],
            "Total Classes Held": [40, 40],
            "Classes Attended": [38, 28],
        })
        st.dataframe(sample_df, use_container_width=True, hide_index=True)

        st.markdown(
            "<small>Supported column name variants: <i>Name, Student, Full Name</i> | "
            "<i>Roll No, ID, Student ID</i> | <i>Total Classes, Classes Held, Total</i> | "
            "<i>Attended, Present</i></small>",
            unsafe_allow_html=True,
        )
        return

    # ── Parse warnings ─────────────────────────────────────────────────────────
    if st.session_state.parse_warnings:
        with st.expander(f"⚠️ {len(st.session_state.parse_warnings)} parsing warning(s)", expanded=False):
            for w in st.session_state.parse_warnings:
                st.warning(w)

    # ── KPI metrics ────────────────────────────────────────────────────────────
    ok_records = [r for r in records if r.status == AttendanceStatus.OK]
    shortage_records = [r for r in records if r.status == AttendanceStatus.SHORTAGE]
    avg_pct = sum(r.attendance_percentage for r in records) / len(records)
    max_r = max(records, key=lambda r: r.attendance_percentage)
    min_r = min(records, key=lambda r: r.attendance_percentage)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👥 Total Students", len(records))
    c2.metric("✅ Meeting Threshold", len(ok_records))
    c3.metric("⚠️ Below Threshold", len(shortage_records),
              delta=f"-{len(shortage_records)}" if shortage_records else None,
              delta_color="inverse")
    c4.metric("📊 Average Attendance", f"{avg_pct:.1f}%")
    c5.metric("📈 Highest / Lowest",
              f"{max_r.attendance_percentage:.0f}% / {min_r.attendance_percentage:.0f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab_all, tab_shortage, tab_warnings, tab_export = st.tabs([
        "📋 All Students", "⚠️ Flagged Students", "🤖 AI Warnings", "💾 Export"
    ])

    df = _records_to_df(records)

    with tab_all:
        st.markdown(f"<div class='section-header'>All Students ({len(records)})</div>",
                    unsafe_allow_html=True)

        search = st.text_input("🔍 Search by name or roll number", placeholder="Type to filter…")
        display_df = df.copy()
        if search.strip():
            mask = (
                df["Student Name"].str.contains(search, case=False, na=False) |
                df["Roll Number"].str.contains(search, case=False, na=False)
            )
            display_df = df[mask]

        cols_to_show = [c for c in display_df.columns if c != "AI Warning"]
        st.dataframe(
            _style_dataframe(display_df[cols_to_show]),
            use_container_width=True,
            hide_index=True,
            height=min(400, 40 + len(display_df) * 35),
        )
        st.caption(f"Showing {len(display_df)} of {len(records)} records.")

    with tab_shortage:
        if not shortage_records:
            st.success("🎉 All students meet the attendance threshold! No flagged students.")
        else:
            st.markdown(
                f"<div class='section-header'>⚠️ Flagged Students ({len(shortage_records)})</div>",
                unsafe_allow_html=True,
            )
            shortage_df = df[df["Status"].str.contains("Shortage")].copy()
            cols_to_show = [c for c in shortage_df.columns if c != "AI Warning"]
            st.dataframe(
                _style_dataframe(shortage_df[cols_to_show]),
                use_container_width=True,
                hide_index=True,
                height=min(400, 40 + len(shortage_df) * 35),
            )

            # Deficit bar chart
            st.markdown("<div class='section-header'>Deficit Classes by Student</div>",
                        unsafe_allow_html=True)
            chart_df = shortage_df[["Student Name", "Deficit Classes"]].set_index("Student Name")
            st.bar_chart(chart_df, color="#E74C3C")

    with tab_warnings:
        flagged_with_warnings = [r for r in shortage_records if r.ai_warning]
        if not st.session_state.ai_generated:
            st.info(
                "🤖 Click **Generate AI Warnings** in the sidebar to create personalised "
                "warning messages for flagged students."
            )
        elif not flagged_with_warnings:
            st.info("No AI warnings generated (all students may be above threshold).")
        else:
            st.markdown(
                f"<div class='section-header'>AI Warning Messages ({len(flagged_with_warnings)} students)</div>",
                unsafe_allow_html=True,
            )
            for record in flagged_with_warnings:
                with st.container():
                    st.markdown(
                        f"<div class='warning-card'>"
                        f"<b>⚠️ {record.name}</b> ({record.roll_number}) — "
                        f"<span style='color:#E65100'>{record.attendance_percentage:.1f}%</span> | "
                        f"Needs <b>{record.deficit_classes}</b> more class(es)<br><br>"
                        f"<i>{record.ai_warning}</i>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    with tab_export:
        st.markdown("<div class='section-header'>Download Reports</div>",
                    unsafe_allow_html=True)
        st.markdown("Generate and download your attendance report in multiple formats.")

        col_xl, col_pdf = st.columns(2)

        with col_xl:
            st.markdown("#### 📊 Excel Report (.xlsx)")
            st.markdown(
                "- Full report sheet\n"
                "- Summary KPI sheet\n"
                "- Flagged students sheet (with AI warnings)\n"
                "- Professional colour-coded formatting"
            )
            if st.button("Generate Excel", use_container_width=True):
                with st.spinner("Building Excel report…"):
                    try:
                        xl_bytes = export_excel(records, threshold=float(threshold))
                        st.download_button(
                            label="⬇️ Download Excel Report",
                            data=xl_bytes,
                            file_name="attendance_report.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                    except Exception as exc:
                        st.error(f"Excel generation failed: {exc}")
                        logger.error(traceback.format_exc())

        with col_pdf:
            st.markdown("#### 📄 PDF Report (.pdf)")
            st.markdown(
                "- Executive summary with KPIs\n"
                "- Full paginated attendance table\n"
                "- AI warning messages section\n"
                "- Professional header & footer"
            )
            if st.button("Generate PDF", use_container_width=True):
                with st.spinner("Building PDF report…"):
                    try:
                        pdf_bytes = export_pdf(records, threshold=float(threshold))
                        st.download_button(
                            label="⬇️ Download PDF Report",
                            data=pdf_bytes,
                            file_name="attendance_report.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    except Exception as exc:
                        st.error(f"PDF generation failed: {exc}")
                        logger.error(traceback.format_exc())

        st.markdown("---")
        st.markdown("#### 📋 CSV Export")
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name="attendance_report.csv",
            mime="text/csv",
            use_container_width=False,
        )


if __name__ == "__main__":
    main()
