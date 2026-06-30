from decimal import Decimal

from statement_analyzer.models import Statement, Transaction
from statement_analyzer.privacy import mask_name, mask_text, redact_statement


def test_mask_text_keeps_short_numbers_and_masks_long_numbers():
    assert mask_text("账号 1234567890123456 金额 100") == "账号 ************3456 金额 100"


def test_mask_name_masks_middle_characters():
    assert mask_name("江西联创电子有限公司") == "江西******公司"


def test_redact_statement_masks_counterparty_and_raw_text():
    statement = Statement(
        file_name="sample.csv",
        file_type="csv",
        account_name="江西联创电子有限公司",
        account_no_masked="1234567890123456",
        transactions=[
            Transaction(
                row_no=1,
                transaction_date=None,
                counterparty_name="江西亚年科技有限公司",
                raw_text="收款账号 9876543210987654",
                income_amount=Decimal("0"),
                expense_amount=Decimal("1"),
            )
        ],
    )

    redacted = redact_statement(statement)

    assert redacted.account_name != statement.account_name
    assert redacted.account_no_masked == "************3456"
    assert redacted.transactions[0].counterparty_name != statement.transactions[0].counterparty_name
    assert "9876543210987654" not in redacted.transactions[0].raw_text
