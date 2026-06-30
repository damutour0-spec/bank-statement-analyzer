# Bank Statement Analyzer

Upload bank statement files and export a standardized Excel workbook with
transaction rows, review findings, monthly summaries, and counterparty
summaries.

## Features

- Upload CSV, XLSX, XLSM, TXT, text-based PDF, JPG, JPEG, PNG, BMP, TIFF, and WEBP.
- Normalize common bank-statement fields into one transaction schema.
- Use local OCR for image files through `rapidocr_onnxruntime`.
- Export a multi-sheet Excel report.
- Run review rules for:
  - balance continuity
  - duplicate transactions
  - low-confidence extraction
  - sensitive keywords
  - large round-number transactions
  - same-day large in/out activity
  - counterparty concentration
- Includes receipt OCR template adapters for:
  - ICBC e-receipts
  - ABC account transaction details
  - BOCOM receipts
  - bank acceptance bill endorsement/pledge backs
- Runs on FastAPI with upload validation and 24-hour file retention by default.
- Stores job state in local SQLite and automatically migrates legacy `data/jobs.json` when possible.

## Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the app:

```powershell
python app.py
```

Or run directly with Uvicorn:

```powershell
python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

In the Codex bundled runtime, use:

```powershell
& "C:\Users\刘国良\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "C:\Users\刘国良\Documents\软件开发\bank-statement-analyzer\app.py"
```

## Runtime Settings

Optional environment variables:

```text
MAX_UPLOAD_BYTES=20971520
FILE_RETENTION_HOURS=24
```

`FILE_RETENTION_HOURS` applies to uploaded source files and exported reports.
The default is 24 hours.

Job state is stored in:

```text
data/jobs.sqlite3
```

If a legacy `data/jobs.json` file exists and the SQLite database is empty, the
app imports those job records once on startup/use.

## Receipt OCR Templates

Receipt templates are text-only adapters. They consume OCR text and do not
commit or require private image fixtures in the repository.

Currently covered templates:

- ICBC e-receipts: amount, date, payer/payee, summary, serial number.
- ABC account transaction details: amount, transaction date, payee, summary, purpose.
- BOCOM receipts: debit/credit flag, amount, payee, summary, accounting serial number.
- Bank acceptance bill backs: endorsement/pledge party, bill number, endorsement date.

## Optional Cloud OCR

The parser tries OCR providers in this order:

1. `rapidocr_onnxruntime`
2. `paddleocr`
3. `pytesseract`
4. Baidu OCR, when keys are configured

For Baidu OCR, copy `.env.example` to `.env` and fill in:

```text
BAIDU_OCR_API_KEY=your_api_key
BAIDU_OCR_SECRET_KEY=your_secret_key
```

Restart the app after changing `.env`.

## Product Boundary

This project does not connect to bank accounts and does not claim to determine
whether a statement is genuine. It provides standardization, data-quality
checks, and auxiliary review findings.
