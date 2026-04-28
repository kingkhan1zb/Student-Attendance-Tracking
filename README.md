# 📋 Student Attendance Management System

A production-quality Python tool for processing student attendance data, generating professional reports, and delivering AI-powered personalised warning messages.

---

## ✨ Features

| Feature | Details |
|---|---|
| **File Input** | Supports `.csv` and `.xlsx` / `.xls` formats with flexible column name detection |
| **Attendance Calculation** | Accurate percentage computation with configurable threshold |
| **Flagging** | Identifies students below threshold and computes exact deficit classes |
| **Excel Export** | Multi-sheet, colour-coded, professional `.xlsx` report |
| **PDF Export** | Paginated, landscape A4 PDF with KPI summary and full data table |
| **Console Report** | Rich, colour-coded terminal output |
| **AI Warnings** | Personalised formal warning messages via Groq AI API |
| **Web UI** | Streamlit app with upload, filtering, charts, and download buttons |
| **CLI** | Full `argparse`-based CLI for headless / scripted usage |

---

## 📁 Project Structure

```
attendance_system/
│
├── app.py                    # Streamlit web application (main UI)
├── cli.py                    # CLI tool (argparse)
│
├── core/
│   ├── models.py             # StudentRecord dataclass + business logic
│   ├── ingestion.py          # File parsing, column resolution, validation
│   └── ai_warnings.py        # Groq AI warning message generator
│
├── exporters/
│   ├── excel_exporter.py     # .xlsx report (openpyxl)
│   ├── pdf_exporter.py       # .pdf report (ReportLab)
│   └── console_report.py     # Terminal output (Rich)
│
├── sample_input.csv          # Sample data for testing
├── generate_sample_xlsx.py   # Script to generate sample_input.xlsx
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key (for AI warnings)

```bash
export Groq_Api="your_api_key_here"
```

### 3a. Run the Web App (Streamlit)

```bash
    python -m streamlit run app.py
```

Then open http://localhost:8501 in your browser.

### 3b. Run the CLI

```bash
# Console output (default)
python cli.py sample_input.csv

# With custom threshold
python cli.py sample_input.csv --threshold 80

# Export to Excel
python cli.py sample_input.csv --output excel --out-file report.xlsx

# Export to PDF
python cli.py sample_input.csv --output pdf --out-file report.pdf

# With AI warnings
python cli.py sample_input.csv --ai --output pdf

# All options
python cli.py sample_input.xlsx --threshold 80 --ai --output excel --out-file my_report.xlsx
```

---

## 📄 Input File Format

Your CSV or Excel file must contain these columns (flexible naming supported):

| Required Field | Accepted Column Names |
|---|---|
| Student Name | `Student Name`, `Name`, `Student`, `Full Name` |
| Roll Number | `Roll Number`, `Roll No`, `Roll No.`, `RollNo`, `ID`, `Student ID` |
| Total Classes Held | `Total Classes Held`, `Total Classes`, `Classes Held`, `Total` |
| Classes Attended | `Classes Attended`, `Attended`, `Present`, `Attendance` |

### Sample Input (`sample_input.csv`)

```csv
Student Name,Roll Number,Total Classes Held,Classes Attended
Ahmed Ali,CS-001,40,38
Fatima Khan,CS-002,40,28
Muhammad Usman,CS-003,40,22
...
```

---

## 📊 Output Reports

### Excel Report (3 sheets)
- **📊 Summary** — KPI cards: total, passing, failing, average
- **📋 Full Report** — All students with colour-coded rows and auto-filter
- **⚠️ Flagged Students** — Only shortage students + AI warning messages

### PDF Report
- Executive summary (KPI panel)
- Full attendance table (paginated, landscape A4)
- AI warning messages section

### Console Report
- Rich colour-coded table with emoji status
- KPI summary row
- Flagged students panel with AI warnings

---

## 🧮 Business Logic

### Attendance Percentage
```
attendance_percentage = (classes_attended / total_classes) × 100
```

### Deficit Classes
The minimum number of additional classes a student must attend to reach the threshold:
```
deficit = ⌈(threshold × total - attended) / (1 - threshold)⌉
```
This accounts for the fact that attending more classes also increases the denominator (total classes).

---

## 🤖 AI Warning Example

```
Dear Imran Baig, your attendance currently stands at 25.0%, which is significantly below
the required threshold of 75%. You are required to attend at least 50 more classes to
meet the minimum attendance requirement. Please ensure regular attendance going forward.
```

---

## ⚙️ Configuration

| Parameter | Default | Description |
|---|---|---|
| `--threshold` | `75.0` | Minimum attendance percentage required |
| `--output` | `console` | Output format: `console`, `excel`, `pdf`, `csv` |
| `--out-file` | auto | Output file path |
| `--ai` | `False` | Enable AI warning message generation |
| `--quiet` | `False` | Suppress info-level logs |

---

## 🛡️ Edge Cases Handled

- Zero total classes → attendance set to 0%
- Attended > Total → validation error with skip
- Missing / blank name or roll number → row skipped with warning
- Non-numeric class counts → row skipped with warning  
- Unsupported file formats → clear error message
- Empty files → clear error message
- Flexible column name matching (case-insensitive, alias-based)
- AI API failures → deterministic fallback message

---

## 📦 Dependencies

```
pandas          ≥ 2.0    — data processing
openpyxl        ≥ 3.1    — Excel generation
xlrd            ≥ 2.0    — legacy .xls support
reportlab       ≥ 4.0    — PDF generation
streamlit       ≥ 1.35   — web interface
rich            ≥ 13.0   — console output
groq       ≥ 0.40   — AI warning messages
```

## Video Link (Google Drive)
https://drive.google.com/file/d/11Q4dQT2xSoTbkeJSTNr532FUivAZvfwj/view?usp=sharing
