from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import Transaction


@dataclass(frozen=True)
class ReceiptTemplate:
    name: str
    bank_name: str
    keywords: tuple[str, ...]
    channel: str
    default_summary: str
    confidence: float


TEMPLATES = [
    ReceiptTemplate(
        name="icbc_e_receipt",
        bank_name="中国工商银行",
        keywords=("中国工商银行", "网上银行电子回单", "电子回单号码"),
        channel="工商银行电子回单",
        default_summary="工商银行电子回单",
        confidence=0.78,
    ),
    ReceiptTemplate(
        name="abc_transaction_detail",
        bank_name="中国农业银行",
        keywords=("中国农业银行", "账户交易明细"),
        channel="农业银行账户交易明细",
        default_summary="农业银行账户交易明细",
        confidence=0.78,
    ),
    ReceiptTemplate(
        name="bocom_receipt",
        bank_name="交通银行",
        keywords=("交通银行", "回单编号", "业务名称"),
        channel="交通银行回单",
        default_summary="交通银行回单",
        confidence=0.78,
    ),
    ReceiptTemplate(
        name="bank_acceptance_bill_back",
        bank_name="未知银行",
        keywords=("电子银行承兑汇票", "背书", "被背书人"),
        channel="电子银行承兑汇票",
        default_summary="电子银行承兑汇票背书/质押",
        confidence=0.62,
    ),
]


RECEIPT_KEYWORDS = ("电子回单", "回单号码", "回单编号", "交易流水号", "账户交易明细", "电子银行承兑汇票")


AMOUNT_LABELS = ("金额", "小写", "交易金额", "票据金额", "实付金额")
DATE_LABELS = ("交易日期", "记账日期", "打印日期", "委托日期", "时间戳", "背书日期", "出票日期")
SUMMARY_LABELS = ("摘要", "用途", "交易用途", "业务名称", "业务种类", "业务（产品）种类", "附加信息")
POSTSCRIPT_LABELS = ("备注", "附言", "附加信息", "企业自制凭证号", "票据号码", "交易流水号", "回单编号")
COUNTERPARTY_LABELS = ("收款人名称", "收款户名", "收款人", "收款方", "被背书人名称", "质押权人名称")
PAYER_LABELS = ("付款人名称", "付款户名", "付款人", "付款方", "背书人名称", "出质人名称")


def transactions_from_receipt_text(text: str) -> list[Transaction]:
    if not looks_like_receipt(text):
        return []

    template = detect_template(text)
    if template and template.name == "bank_acceptance_bill_back":
        return transaction_from_bill_back(text, template)

    amount = extract_amount(text)
    date = extract_date(text)
    if amount is None or date is None:
        return []

    direction = infer_direction(text)
    income = amount if direction == "income" else Decimal("0")
    expense = amount if direction == "expense" else Decimal("0")
    if direction == "unknown":
        income = amount

    summary = first_value(text, SUMMARY_LABELS) or (template.default_summary if template else "银行电子回单")
    counterparty = extract_counterparty(text)
    postscript = extract_postscript(text)
    channel = template.channel if template else "电子回单"
    raw = compact_raw_text(text)

    return [
        Transaction(
            row_no=1,
            transaction_date=date,
            summary=summary[:120],
            counterparty_name=counterparty[:80],
            income_amount=income,
            expense_amount=expense,
            balance=None,
            channel=channel,
            postscript=postscript[:120],
            raw_text=raw,
            confidence=template.confidence if template else 0.68,
        )
    ]


def looks_like_receipt(text: str) -> bool:
    return any(keyword in text for keyword in RECEIPT_KEYWORDS)


def detect_template(text: str) -> ReceiptTemplate | None:
    for template in TEMPLATES:
        if all(keyword in text for keyword in template.keywords):
            return template
    for template in TEMPLATES:
        if sum(1 for keyword in template.keywords if keyword in text) >= 2:
            return template
    return None


def transaction_from_bill_back(text: str, template: ReceiptTemplate) -> list[Transaction]:
    date = extract_date(text)
    if date is None:
        return []
    counterparty = first_value(text, COUNTERPARTY_LABELS) or first_value(text, ("质押权人名称",))
    bill_no = first_value(text, ("票据号码",))
    postscript_parts = [part for part in [f"票据号码：{bill_no}" if bill_no else "", extract_postscript(text)] if part]
    return [
        Transaction(
            row_no=1,
            transaction_date=date,
            summary=template.default_summary,
            counterparty_name=counterparty[:80],
            income_amount=Decimal("0"),
            expense_amount=Decimal("0"),
            balance=None,
            channel=template.channel,
            postscript="；".join(postscript_parts)[:120],
            raw_text=compact_raw_text(text),
            confidence=template.confidence,
        )
    ]


def extract_amount(text: str) -> Decimal | None:
    patterns = [
        r"[￥¥]\s*([\d,]+(?:\.\d{1,2})?)\s*元?",
        r"(?:金额|小写|交易金额|票据金额|实付金额)\s*(?:[:：])?\s*(?:人民币)?\s*[￥¥]?\s*([\d,]+(?:\.\d{1,2})?)",
        r"([\d,]+(?:\.\d{1,2})?)\s*元整",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return parse_amount(match.group(1), allow_none=True)
    return None


def extract_date(text: str) -> datetime | None:
    patterns = [
        r"(?:交易日期|交易时间|记账日期|打印日期|委托日期|背书日期|出票日期)\s*[:：]?\s*(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:[日])?(?:\s+\d{1,2}:\d{1,2}:\d{1,2})?)",
        r"时间戳\s*[:：]?\s*(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})[-\s.]?\d{0,2}",
        r"(20\d{2}年\d{1,2}月\d{1,2}日)",
        r"(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}(?:\s+\d{1,2}:\d{1,2}:\d{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            parsed = parse_date(match.group(1))
            if parsed:
                return parsed
    return None


def infer_direction(text: str) -> str:
    compact = normalize_text(text)
    if any(keyword in compact for keyword in ["借贷标志借方", "付款人", "付款方", "转账汇出", "付方", "借方"]):
        return "expense"
    if any(keyword in compact for keyword in ["借贷标志贷方", "收款入账", "转账汇入", "收款方到账", "贷方"]):
        return "income"
    return "unknown"


def extract_counterparty(text: str) -> str:
    counterparty = first_value(text, COUNTERPARTY_LABELS)
    if counterparty:
        return counterparty
    value = value_near_section(text, "收款", ("户名", "名称"))
    if value:
        return value
    return first_value(text, PAYER_LABELS)


def extract_postscript(text: str) -> str:
    values = []
    for labels in (POSTSCRIPT_LABELS, ("流水号",), ("日志号",), ("凭证号",)):
        value = first_value(text, labels)
        if value and value not in values:
            values.append(value)
    return "；".join(values)


def first_value(text: str, labels: tuple[str, ...]) -> str:
    lines = clean_lines(text)
    for index, line in enumerate(lines):
        for label in labels:
            value = value_from_line(line, label)
            if value:
                return value
            if normalize_text(line) == normalize_text(label) and index + 1 < len(lines):
                return strip_known_labels(lines[index + 1])[:120]
    compact = " ".join(lines)
    for label in labels:
        value = value_after_label_in_compact_text(compact, label)
        if value:
            return value[:120]
    return ""


def value_from_line(line: str, label: str) -> str:
    normalized_line = normalize_text(line)
    normalized_label = normalize_text(label)
    if not normalized_line.startswith(normalized_label):
        return ""
    value = line[len(label) :].strip(" ：:")
    return strip_known_labels(value)[:120]


def value_after_label_in_compact_text(text: str, label: str) -> str:
    stop = "|".join(re.escape(item) for item in ALL_STOP_LABELS)
    pattern = rf"{re.escape(label)}\s*[:：]?\s*(?P<value>.*?)(?:\s+(?:{stop})\s*[:：]?|$)"
    match = re.search(pattern, text)
    if not match:
        return ""
    return strip_known_labels(match.group("value").strip())[:120]


def value_near_section(text: str, section: str, labels: tuple[str, ...]) -> str:
    lines = clean_lines(text)
    for index, line in enumerate(lines):
        if section not in line:
            continue
        window = " ".join(lines[index : index + 6])
        value = first_value(window, labels)
        if value:
            return value
    return ""


def strip_known_labels(value: str) -> str:
    value = value.strip(" ：:")
    for label in ALL_STOP_LABELS:
        if value == label:
            return ""
        if value.startswith(label):
            value = value.replace(label, "", 1).strip(" ：:")
    return value


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def compact_raw_text(text: str) -> str:
    return " ".join(clean_lines(text))[:2000]


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
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def parse_amount(value: str, allow_none: bool = False) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None if allow_none else Decimal("0")
    cleaned = str(value).strip()
    cleaned = cleaned.replace(",", "").replace("￥", "").replace("¥", "").replace("元", "")
    cleaned = cleaned.replace("人民币", "").replace("小写", "").replace("金额", "")
    cleaned = cleaned.strip(" ：:")
    if cleaned in ["-", "--"]:
        return None if allow_none else Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
        if not numbers:
            return None if allow_none else Decimal("0")
        return Decimal(numbers[-1])


ALL_STOP_LABELS = (
    AMOUNT_LABELS
    + DATE_LABELS
    + SUMMARY_LABELS
    + POSTSCRIPT_LABELS
    + COUNTERPARTY_LABELS
    + PAYER_LABELS
    + ("账号", "户名", "开户行", "币种", "金额大写", "大写", "小写", "受理渠道")
)
