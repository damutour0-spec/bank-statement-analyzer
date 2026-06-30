from datetime import datetime
from decimal import Decimal

from statement_analyzer.models import Statement, Transaction
from statement_analyzer.rules import analyze_statement


def txn(
    row_no,
    date,
    summary="",
    counterparty_name="",
    income="0",
    expense="0",
    balance=None,
    confidence=0.95,
):
    return Transaction(
        row_no=row_no,
        transaction_date=datetime.strptime(date, "%Y-%m-%d"),
        summary=summary,
        counterparty_name=counterparty_name,
        income_amount=Decimal(income),
        expense_amount=Decimal(expense),
        balance=Decimal(balance) if balance is not None else None,
        confidence=confidence,
    )


def finding_types(result):
    return {finding.finding_type for finding in result.findings}


def test_rules_find_core_review_findings():
    statement = Statement(
        file_name="sample.csv",
        file_type="csv",
        bank_name="招商银行",
        transactions=[
            txn(1, "2026-01-01", "期初", "A", income="1000", balance="1000"),
            txn(2, "2026-01-02", "借款", "B", income="100", balance="1200"),
            txn(3, "2026-01-03", "重复", "C", income="10000", balance="11200"),
            txn(4, "2026-01-03", "重复", "C", income="10000", balance="11200"),
            txn(5, "2026-01-04", "低置信度", "D", income="1", balance="11201", confidence=0.6),
            txn(6, "2026-01-05", "大额进入", "E", income="60000", balance="71201"),
            txn(7, "2026-01-05", "大额转出", "F", expense="50000", balance="21201"),
        ],
    )

    result = analyze_statement(statement)
    types = finding_types(result)

    assert "balance_continuity_failed" in types
    assert "duplicate_transaction" in types
    assert "low_confidence" in types
    assert "sensitive_keyword" in types
    assert "large_round_amount" in types
    assert "same_day_in_out" in types
    assert result.metrics["transaction_count"] == 7
    assert result.metrics["total_income"] == "81101"
    assert result.metrics["total_expense"] == "50000"
