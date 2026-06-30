from __future__ import annotations

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
import pdfplumber

from .models import Statement, Transaction
from .ocr import extract_text_from_image
from .receipts import transactions_from_receipt_text as parse_receipt_transactions


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

BANK_KEYWORDS = {
    "招商银行": ["招商银行", "cmb", "china merchants bank"],
    "中国工商银行": ["工商银行", "icbc"],
    "中国建设银行": ["建设银行", "ccb"],
    "中国农业银行": ["农业银行", "abc"],
    "中国银行": ["中国银行", "bank of china", "boc"],
    "交通银行": ["交通银行", "bank of communications"],
    "邮储银行": ["邮储银行", "邮政储蓄"],
    "平安银行": ["平安银行"],
    "兴业银行": ["兴业银行"],
    "民生银行": ["民生银行"],
}

HEADER_ALIASES = {
    "transaction_date": ["交易日期", "交易时间", "记账日期", "日期", "date", "time"],
    "summary": ["摘要", "交易摘要", "用途", "交易类型", "说明", "description", "summary"],
    "counterparty_name": ["对方户名", "对方名称", "交易对手", "对手方", "对方账号名称", "counterparty"],
    "income_amount": ["收入", "贷方", "贷方发生额", "收入金额", "入账金额", "credit"],
    "expense_amount": ["支出", "借方", "借方发生额", "支出金额", "出账金额", "debit"],
    "balance": ["余额", "账户余额", "balance"],
    "channel": ["渠道", "交易渠道", "交易方式", "channel"],
    "postscript": ["附言", "备注", "postscript", "note"],
}


def parse_statement(path: Path) -> Statement:
    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xlsm", ".xltx", ".xltm"]:
        rows = read_excel_rows(path)
        statement = statement_from_rows(path.name, "excel", rows)
    elif suffix in [".csv", ".txt"]:
        rows = read_csv_rows(path)
        statement = statement_from_rows(path.name, "csv", rows)
    elif suffix == ".pdf":
        text, rows = read_pdf(path)
        statement = statement_from_rows(path.name, "pdf", rows, fallback_text=text)
    elif suffix in IMAGE_SUFFIXES:
        text = read_image_text(path)
        statement = statement_from_rows(path.name, "image", [], fallback_text=text)
    else:
        raise ValueError(f"暂不支持的文件类型: {suffix}")
    return statement


def read_excel_rows(path: Path) -> list[list[Any]]:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet = workbook.active
    rows = []
    for row in sheet.iter_rows(values_only=True):
        if any(value not in (None, "") for value in row):
            rows.append(list(row))
    return rows


def read_csv_rows(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")
    sample = text[:2048]
    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|") if sample.strip() else csv.excel
    return [row for row in csv.reader(text.splitlines(), dialect) if any(cell.strip() for cell in row)]


def read_pdf(path: Path) -> tuple[str, list[list[str]]]:
    text_parts = []
    rows: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    if row and any(cell for cell in row):
                        rows.append([cell or "" for cell in row])
    return "\n".join(text_parts), rows


def read_image_text(path: Path) -> str:
    return extract_text_from_image(path)


def statement_from_rows(
    file_name: str,
    file_type: str,
    rows: list[list[Any]],
    fallback_text: str = "",
) -> Statement:
    flat_text = "\n".join(" ".join("" if cell is None else str(cell) for cell in row) for row in rows)
    bank_name = detect_bank(flat_text + "\n" + fallback_text)
    header_index, mapping = detect_header(rows)
    transactions: list[Transaction] = []

    if header_index is not None:
        for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            txn = transaction_from_mapped_row(offset, row, mapping)
            if txn:
                transactions.append(txn)

    if not transactions and fallback_text:
        transactions = transactions_from_text(fallback_text)

    if not transactions:
        raise ValueError("未能识别交易明细，请上传带表头的 Excel/CSV、原生文本 PDF，或配置图片 OCR。")

    return Statement(
        file_name=file_name,
        file_type=file_type,
        bank_name=bank_name,
        transactions=transactions,
        confidence=estimate_confidence(transactions),
    )


def detect_bank(text: str) -> str:
    lowered = text.lower()
    for bank, keywords in BANK_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return bank
    return "未知银行"


def detect_header(rows: list[list[Any]]) -> tuple[int | None, dict[str, int]]:
    best_index = None
    best_mapping: dict[str, int] = {}
    best_score = 0
    for index, row in enumerate(rows[:20]):
        normalized = [normalize_header(cell) for cell in row]
        mapping: dict[str, int] = {}
        for field, aliases in HEADER_ALIASES.items():
            for col, value in enumerate(normalized):
                if any(alias.lower() in value for alias in aliases):
                    mapping[field] = col
                    break
        score = len(mapping)
        if "transaction_date" in mapping:
            score += 2
        if "balance" in mapping:
            score += 1
        if score > best_score:
            best_score = score
            best_index = index
            best_mapping = mapping
    if best_score < 3:
        return None, {}
    return best_index, best_mapping


def normalize_header(value: Any) -> str:
    return re.sub(r"\s+", "", "" if value is None else str(value)).lower()


def transaction_from_mapped_row(row_no: int, row: list[Any], mapping: dict[str, int]) -> Transaction | None:
    def cell(field: str) -> str:
        index = mapping.get(field)
        if index is None or index >= len(row):
            return ""
        return "" if row[index] is None else str(row[index]).strip()

    date = parse_date(cell("transaction_date"))
    income = parse_amount(cell("income_amount"))
    expense = parse_amount(cell("expense_amount"))
    balance = parse_amount(cell("balance"), allow_none=True)

    if not date and income == 0 and expense == 0 and balance is None:
        return None

    raw_text = " | ".join("" if item is None else str(item) for item in row)
    return Transaction(
        row_no=row_no,
        transaction_date=date,
        summary=cell("summary"),
        counterparty_name=cell("counterparty_name"),
        income_amount=income,
        expense_amount=expense,
        balance=balance,
        channel=cell("channel"),
        postscript=cell("postscript"),
        raw_text=raw_text,
        confidence=0.95 if date and balance is not None else 0.75,
    )


def transactions_from_text(text: str) -> list[Transaction]:
    transactions = []
    pattern = re.compile(
        r"(?P<date>20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}[日]?)\s+"
        r"(?P<body>.*?)\s+"
        r"(?P<a1>[+-]?\d[\d,]*\.\d{2})\s+"
        r"(?P<a2>[+-]?\d[\d,]*\.\d{2})?",
        re.S,
    )
    for idx, match in enumerate(pattern.finditer(text), start=1):
        date = parse_date(match.group("date"))
        amount = parse_amount(match.group("a1"))
        balance = parse_amount(match.group("a2"), allow_none=True)
        income = amount if amount > 0 else Decimal("0")
        expense = abs(amount) if amount < 0 else Decimal("0")
        transactions.append(
            Transaction(
                row_no=idx,
                transaction_date=date,
                summary=match.group("body").strip()[:120],
                income_amount=income,
                expense_amount=expense,
                balance=balance,
                raw_text=match.group(0),
                confidence=0.6,
            )
        )
    if transactions:
        return transactions
    return parse_receipt_transactions(text)


def transaction_from_receipt_text(text: str) -> list[Transaction]:
    return parse_receipt_transactions(text)


def extract_receipt_amount(text: str) -> Decimal | None:
    match = re.search(r"[￥¥]\s*([\d,]+(?:\.\d{2})?)\s*元?", text)
    if not match:
        match = re.search(r"金额\s*([\d,]+(?:\.\d{2})?)", text)
    return parse_amount(match.group(1), allow_none=True) if match else None


def extract_receipt_date(text: str) -> datetime | None:
    patterns = [
        r"时间戳\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",
        r"委托日期[:：]?\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",
        r"记账日期\s*(20\d{2}年\d{1,2}月\d{1,2}日)",
        r"打印日期[:：]?\s*(20\d{2}年\d{1,2}月\d{1,2}日)",
        r"(20\d{2}年\d{1,2}月\d{1,2}日)",
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            parsed = parse_date(match.group(1))
            if parsed:
                return parsed
    return None


def extract_label_value(text: str, label: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line.startswith(label):
            value = line.replace(label, "", 1).strip(" ：:")
            if value:
                return value[:120]
            if index + 1 < len(lines):
                return lines[index + 1][:120]
    return ""


def extract_receipt_counterparty(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line in ["收款", "收款人", "收款户名"] and index + 1 < len(lines):
            return lines[index + 1][:80]
    return ""


def parse_date(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip().replace("年", "-").replace("月", "-").replace("日", "")
    value = value.replace("/", "-").replace(".", "-")
    candidates = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d",
        "%m-%d",
    ]
    for fmt in candidates:
        try:
            parsed = datetime.strptime(value[:19], fmt)
            if fmt == "%m-%d":
                parsed = parsed.replace(year=datetime.now().year)
            return parsed
        except ValueError:
            continue
    return None


def parse_amount(value: str, allow_none: bool = False) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None if allow_none else Decimal("0")
    cleaned = str(value).strip()
    cleaned = cleaned.replace(",", "").replace("￥", "").replace("¥", "").replace("元", "")
    cleaned = cleaned.replace("收入", "").replace("支出", "").replace("余额", "")
    cleaned = cleaned.strip()
    if cleaned in ["-", "--"]:
        return None if allow_none else Decimal("0")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        amount = Decimal(cleaned)
        return -amount if negative else amount
    except InvalidOperation:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
        if not numbers:
            return None if allow_none else Decimal("0")
        return Decimal(numbers[-1])


def estimate_confidence(transactions: list[Transaction]) -> float:
    if not transactions:
        return 0
    return round(sum(item.confidence for item in transactions) / len(transactions), 4)
