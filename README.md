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
- Includes a receipt fallback parser for bank e-receipt screenshots.

## Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the app:

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:8765
```

In the Codex bundled runtime, use:

```powershell
& "C:\Users\刘国良\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "C:\Users\刘国良\Documents\软件开发\bank-statement-analyzer\app.py"
```

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
