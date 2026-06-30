from decimal import Decimal

from statement_analyzer.categories import classify_transaction
from statement_analyzer.models import Transaction


def make_txn(summary="", postscript="", counterparty_name="", channel="", raw_text=""):
    return Transaction(
        row_no=1,
        transaction_date=None,
        summary=summary,
        postscript=postscript,
        counterparty_name=counterparty_name,
        channel=channel,
        raw_text=raw_text,
        income_amount=Decimal("0"),
        expense_amount=Decimal("0"),
    )


def test_classify_payroll():
    assert classify_transaction(make_txn(summary="工资发放")) == "payroll"


def test_classify_procurement_from_raw_text():
    assert classify_transaction(make_txn(raw_text="设备采购款")) == "procurement"


def test_classify_bill_business():
    assert classify_transaction(make_txn(channel="电子银行承兑汇票")) == "bill_business"


def test_classify_other_when_no_keyword_matches():
    assert classify_transaction(make_txn(summary="普通转账")) == "other"
