from datetime import datetime
from decimal import Decimal

from statement_analyzer.models import Statement, Transaction
from statement_analyzer.rule_config import load_rule_config, resolve_profile
from statement_analyzer.rules import analyze_statement


def txn(row_no, date, income="0", expense="0", balance=None, confidence=0.95):
    return Transaction(
        row_no=row_no,
        transaction_date=datetime.strptime(date, "%Y-%m-%d"),
        income_amount=Decimal(income),
        expense_amount=Decimal(expense),
        balance=Decimal(balance) if balance is not None else None,
        confidence=confidence,
    )


def finding_types(result):
    return {finding.finding_type for finding in result.findings}


def test_load_default_rule_profile():
    config = load_rule_config()

    assert config["_profile"] == "enterprise_flow_review"
    assert config["same_day_in_out"]["min_income"] == "50000"


def test_resolve_profile_deep_merges_defaults():
    config = resolve_profile(
        {"profiles": {"custom": {"same_day_in_out": {"min_income": "100"}}}},
        "custom",
    )

    assert config["_profile"] == "custom"
    assert config["same_day_in_out"]["min_income"] == "100"
    assert config["same_day_in_out"]["expense_income_ratio"] == "0.8"


def test_rule_threshold_config_changes_results():
    statement = Statement(
        file_name="sample.csv",
        file_type="csv",
        transactions=[
            txn(1, "2026-01-01", income="1000", balance="1000"),
            txn(2, "2026-01-01", expense="800", balance="200"),
        ],
    )
    strict_config = resolve_profile(
        {"profiles": {"strict": {"same_day_in_out": {"min_income": "100", "expense_income_ratio": "0.7"}}}},
        "strict",
    )
    loose_config = resolve_profile(
        {"profiles": {"loose": {"same_day_in_out": {"min_income": "2000", "expense_income_ratio": "0.9"}}}},
        "loose",
    )

    assert "same_day_in_out" in finding_types(analyze_statement(statement, strict_config))
    assert "same_day_in_out" not in finding_types(analyze_statement(statement, loose_config))
