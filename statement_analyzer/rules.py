from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from .models import AnalysisResult, Finding, Statement, Transaction


SENSITIVE_KEYWORDS = [
    "借款",
    "还款",
    "贷款",
    "网贷",
    "博彩",
    "担保",
    "保证金",
    "代偿",
    "逾期",
    "法院",
    "执行",
]


def analyze_statement(statement: Statement) -> AnalysisResult:
    transactions = sorted(
        statement.transactions,
        key=lambda item: (item.transaction_date or item.row_no, item.row_no),
    )
    findings: list[Finding] = []
    findings.extend(check_balance_continuity(transactions))
    findings.extend(check_duplicates(transactions))
    findings.extend(check_low_confidence(transactions))
    findings.extend(check_sensitive_keywords(transactions))
    findings.extend(check_large_round_amounts(transactions))
    findings.extend(check_same_day_in_out(transactions))
    metrics = build_metrics(transactions)
    findings.extend(check_counterparty_concentration(metrics))
    return AnalysisResult(findings=findings, metrics=metrics)


def check_balance_continuity(transactions: list[Transaction]) -> list[Finding]:
    findings = []
    previous = None
    tolerance = Decimal("0.02")
    for current in transactions:
        if previous and previous.balance is not None and current.balance is not None:
            expected = previous.balance + current.signed_amount()
            if abs(expected - current.balance) > tolerance:
                findings.append(
                    Finding(
                        finding_type="balance_continuity_failed",
                        severity="high",
                        title="余额连续性不匹配",
                        description=f"上一笔余额加本笔净额后应为 {expected}，实际余额为 {current.balance}。",
                        row_no=current.row_no,
                        evidence={
                            "previous_balance": str(previous.balance),
                            "signed_amount": str(current.signed_amount()),
                            "expected_balance": str(expected),
                            "actual_balance": str(current.balance),
                        },
                        suggestion="优先复核该行金额、借贷方向、余额，或检查是否缺页/漏行。",
                    )
                )
        previous = current
    return findings


def check_duplicates(transactions: list[Transaction]) -> list[Finding]:
    keys = Counter(transaction_key(item) for item in transactions)
    findings = []
    for item in transactions:
        key = transaction_key(item)
        if keys[key] > 1:
            findings.append(
                Finding(
                    finding_type="duplicate_transaction",
                    severity="warn",
                    title="疑似重复交易",
                    description="日期、摘要、金额、余额高度一致。",
                    row_no=item.row_no,
                    evidence={"duplicate_count": keys[key]},
                    suggestion="检查是否重复导入或 PDF 重复页。",
                )
            )
    return findings


def check_low_confidence(transactions: list[Transaction]) -> list[Finding]:
    return [
        Finding(
            finding_type="low_confidence",
            severity="warn",
            title="低置信度交易行",
            description="该行关键字段不完整或来自非结构化文本抽取。",
            row_no=item.row_no,
            evidence={"confidence": item.confidence},
            suggestion="建议在原始流水中人工确认。",
        )
        for item in transactions
        if item.confidence < 0.8
    ]


def check_sensitive_keywords(transactions: list[Transaction]) -> list[Finding]:
    findings = []
    for item in transactions:
        text = f"{item.summary} {item.postscript} {item.counterparty_name}"
        hits = [keyword for keyword in SENSITIVE_KEYWORDS if keyword in text]
        if hits:
            findings.append(
                Finding(
                    finding_type="sensitive_keyword",
                    severity="warn",
                    title="交易摘要包含敏感关键词",
                    description=f"命中关键词：{', '.join(hits)}。",
                    row_no=item.row_no,
                    evidence={"keywords": hits, "text": text[:160]},
                    suggestion="结合业务背景判断该交易是否需要说明材料。",
                )
            )
    return findings


def check_large_round_amounts(transactions: list[Transaction]) -> list[Finding]:
    findings = []
    for item in transactions:
        amount = max(item.income_amount, item.expense_amount)
        if amount >= Decimal("10000") and amount % Decimal("10000") == 0:
            findings.append(
                Finding(
                    finding_type="large_round_amount",
                    severity="info",
                    title="大额整数交易",
                    description=f"该笔交易金额为 {amount}，属于大额整数。",
                    row_no=item.row_no,
                    evidence={"amount": str(amount)},
                    suggestion="如用于贷款/审计材料，可补充交易背景。",
                )
            )
    return findings


def check_same_day_in_out(transactions: list[Transaction]) -> list[Finding]:
    by_day: dict[str, list[Transaction]] = defaultdict(list)
    for item in transactions:
        if item.transaction_date:
            by_day[item.transaction_date.strftime("%Y-%m-%d")].append(item)
    findings = []
    for day, items in by_day.items():
        income = sum((item.income_amount for item in items), Decimal("0"))
        expense = sum((item.expense_amount for item in items), Decimal("0"))
        if income >= Decimal("50000") and expense / income >= Decimal("0.8"):
            findings.append(
                Finding(
                    finding_type="same_day_in_out",
                    severity="warn",
                    title="当日大额进出",
                    description=f"{day} 收入 {income}，支出 {expense}，资金沉淀较低。",
                    evidence={"date": day, "income": str(income), "expense": str(expense)},
                    suggestion="复核是否为短期周转、过桥、归集或正常经营结算。",
                )
            )
    return findings


def check_counterparty_concentration(metrics: dict[str, Any]) -> list[Finding]:
    findings = []
    top = metrics.get("top_counterparties", [])
    total_flow = Decimal(str(metrics.get("total_income", "0"))) + Decimal(str(metrics.get("total_expense", "0")))
    if top and total_flow > 0:
        top_flow = Decimal(str(top[0]["total_flow"]))
        ratio = top_flow / total_flow
        if ratio >= Decimal("0.5"):
            findings.append(
                Finding(
                    finding_type="counterparty_concentration",
                    severity="warn",
                    title="对手方集中度较高",
                    description=f"最大对手方占全部流水约 {ratio:.1%}。",
                    evidence=top[0],
                    suggestion="确认该对手方是否为关联方、主要客户或固定资金通道。",
                )
            )
    return findings


def build_metrics(transactions: list[Transaction]) -> dict[str, Any]:
    total_income = sum((item.income_amount for item in transactions), Decimal("0"))
    total_expense = sum((item.expense_amount for item in transactions), Decimal("0"))
    balances = [item.balance for item in transactions if item.balance is not None]
    monthly: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0"), "count": 0}
    )
    counterparties: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"income": Decimal("0"), "expense": Decimal("0"), "total_flow": Decimal("0"), "count": 0}
    )
    for item in transactions:
        if item.transaction_date:
            month = item.transaction_date.strftime("%Y-%m")
            monthly[month]["income"] += item.income_amount
            monthly[month]["expense"] += item.expense_amount
            monthly[month]["count"] += 1
        name = item.counterparty_name or "未知对手方"
        counterparties[name]["income"] += item.income_amount
        counterparties[name]["expense"] += item.expense_amount
        counterparties[name]["total_flow"] += item.income_amount + item.expense_amount
        counterparties[name]["count"] += 1

    return {
        "transaction_count": len(transactions),
        "total_income": str(total_income),
        "total_expense": str(total_expense),
        "net_flow": str(total_income - total_expense),
        "min_balance": str(min(balances)) if balances else "",
        "max_balance": str(max(balances)) if balances else "",
        "avg_balance": str(sum(balances, Decimal("0")) / len(balances)) if balances else "",
        "monthly": {
            month: {key: str(value) for key, value in values.items()}
            for month, values in sorted(monthly.items())
        },
        "top_counterparties": [
            {"name": name, **{key: str(value) for key, value in values.items()}}
            for name, values in sorted(
                counterparties.items(),
                key=lambda pair: pair[1]["total_flow"],
                reverse=True,
            )[:10]
        ],
    }


def transaction_key(item: Transaction) -> tuple[str, str, str, str]:
    date = item.transaction_date.strftime("%Y-%m-%d %H:%M:%S") if item.transaction_date else ""
    return (date, item.summary, str(item.signed_amount()), str(item.balance))

