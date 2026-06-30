from decimal import Decimal

from statement_analyzer.parser import parse_statement


def test_parse_csv_statement(tmp_path):
    csv_path = tmp_path / "cmb_sample.csv"
    csv_path.write_text(
        "\n".join(
            [
                "招商银行账户交易明细,",
                "交易日期,摘要,对方户名,收入,支出,余额,渠道,附言",
                "2026-01-01,工资,某公司,10000.00,,10000.00,网银,一月工资",
                "2026-01-02,房租,某房东,,3000.00,7000.00,转账,一月房租",
            ]
        ),
        encoding="utf-8",
    )

    statement = parse_statement(csv_path)

    assert statement.bank_name == "招商银行"
    assert len(statement.transactions) == 2
    assert statement.transactions[0].income_amount == Decimal("10000.00")
    assert statement.transactions[1].expense_amount == Decimal("3000.00")
    assert statement.transactions[1].balance == Decimal("7000.00")
    assert statement.confidence == 0.95
