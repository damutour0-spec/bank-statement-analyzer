# Bank Statement Analyzer

Upload bank statement files and export a standardized Excel workbook with
transaction rows, review findings, monthly summaries, and counterparty
summaries.

## Features

- Upload CSV, XLSX, XLSM, TXT, text-based PDF, JPG, JPEG, PNG, BMP, TIFF, and WEBP.
- Normalize common bank-statement fields into one transaction schema.
- Use local OCR for image files through `rapidocr_onnxruntime`, `paddleocr`, or `pytesseract`.
- Use Baidu OCR for cloud image recognition when API keys are configured.
- Export an enhanced multi-sheet Excel report with cover, findings, summaries, rules, and raw text.
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
- Supports SQLite locally and PostgreSQL on cloud platforms such as Render.
- Stores job state in local SQLite by default and automatically migrates legacy `data/jobs.json` when possible.

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
DATABASE_URL=
MAX_UPLOAD_BYTES=20971520
MAX_BATCH_FILES=10
FILE_RETENTION_HOURS=24
REDACT_EXPORTS=false
RULE_PROFILE=enterprise_flow_review
CORS_ORIGINS=*
OCR_PROVIDER=auto
BAIDU_OCR_API_KEY=
BAIDU_OCR_SECRET_KEY=
BAIDU_OCR_LANGUAGE_TYPE=CHN_ENG
BAIDU_OCR_DETECT_DIRECTION=true
BAIDU_OCR_ENDPOINT=https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic
```

`FILE_RETENTION_HOURS` applies to uploaded source files and exported reports.
The default is 24 hours.

Job state is stored in local SQLite when `DATABASE_URL` is empty:

```text
data/jobs.sqlite3
```

When `DATABASE_URL` starts with `postgres://` or `postgresql://`, the app uses
PostgreSQL instead. The `jobs` table and index are created automatically during
normal app use.

If a legacy `data/jobs.json` file exists and the SQLite database is empty, the
app imports those job records once on startup/use. This legacy JSON migration is
only used for local SQLite mode.

## Render Deployment

This repository includes `render.yaml` for Render Blueprint deployment.

Recommended setup:

```text
Cloudflare Pages: frontend and domain
Render Web Service: FastAPI backend
Render PostgreSQL: job state database
Cloudflare R2: future upload/export object storage
```

To deploy the backend and database on Render:

1. Push this repository to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Render reads `render.yaml` and creates:
   - `bank-statement-api`
   - `bank-statement-db`
4. Keep both services in the Singapore region.
5. After deploy, use the Render service URL as the API base URL for the frontend.

Manual Render Web Service settings, if not using Blueprint:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn webapp.main:app --host 0.0.0.0 --port $PORT
```

Set `DATABASE_URL` to the Render PostgreSQL internal connection string.

### Render OCR setup

For Render Free/Starter instances, prefer Baidu OCR instead of installing heavy
local OCR packages. Add these secret environment variables manually in Render:

```text
BAIDU_OCR_API_KEY=your_api_key
BAIDU_OCR_SECRET_KEY=your_secret_key
```

The non-secret defaults are already documented in `render.yaml`:

```text
OCR_PROVIDER=auto
BAIDU_OCR_LANGUAGE_TYPE=CHN_ENG
BAIDU_OCR_DETECT_DIRECTION=true
BAIDU_OCR_ENDPOINT=https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic
```

After changing OCR environment variables, redeploy the Render Web Service.

## Excel Report Sheets

The exported workbook includes:

- `报告封面`: file metadata, date range, confidence, finding counts, and report boundary notice.
- `标准流水`: normalized transaction rows with frozen header and filters.
- `异常清单`: review findings with severity, explanation, evidence, and suggestion.
- `汇总指标`: total income, total expense, net flow, and balance statistics.
- `月度汇总`: monthly income, expense, net flow, and transaction count.
- `对手方汇总`: top counterparties, flow amount, share, and transaction count.
- `规则说明`: rule logic and suggested handling.
- `原始文本`: extracted raw row/OCR text for manual traceability.

## Receipt OCR Templates

Receipt templates are text-only adapters. They consume OCR text and do not
commit or require private image fixtures in the repository.

Currently covered templates:

- ICBC e-receipts: amount, date, payer/payee, summary, serial number.
- ABC account transaction details: amount, transaction date, payee, summary, purpose.
- BOCOM receipts: debit/credit flag, amount, payee, summary, accounting serial number.
- Bank acceptance bill backs: endorsement/pledge party, bill number, endorsement date.

## OCR Strategy

The parser tries OCR providers in this order when `OCR_PROVIDER=auto`:

1. `rapidocr_onnxruntime`
2. `paddleocr`
3. `pytesseract`
4. Baidu OCR, when keys are configured

To force Baidu OCR for image uploads, set:

```text
OCR_PROVIDER=baidu
```

For Baidu OCR, copy `.env.example` to `.env` locally or configure Render secrets:

```text
BAIDU_OCR_API_KEY=your_api_key
BAIDU_OCR_SECRET_KEY=your_secret_key
```

Baidu OCR access tokens are cached in memory until shortly before expiry to
avoid requesting a new token for every uploaded image.

## Product Boundary

This project does not connect to bank accounts and does not claim to determine
whether a statement is genuine. It provides standardization, data-quality
checks, and auxiliary review findings.
