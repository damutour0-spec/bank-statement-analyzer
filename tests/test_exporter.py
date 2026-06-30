from datetime import datetime
from decimal import Decimal

import openpyxl

from statement_analyzer.exporter import export_workbook
from statement_analyzer.models import AnalysisResult, Statement, Transaction


def test_export_workbook_has_expected_sheets_and_amount_format(tmp_path):
    statement = Statement(
        file_name="sample.csv",
        file_type="csv",
        transactions=[
            Transaction(
                row_no=1,
                transaction_date=datetime(2026, 1, 1),
                summary="工资",
                income_amount=Decimal("10000.10"),
                expense_amount=Decimal("0"),
                balance=Decimal("10000.10"),
            )
        ],
    )
    analysis = AnalysisResult(findings=[], metrics={"transaction_count": 1, "total_income": "10000.10"})
    output = tmp_path / "analysis.xlsx"

    export_workbook(statement, analysis, output)

    workbook = openpyxl.load_workbook(output, data_only=True)
    assert workbook.sheetnames == ["标准流水", "异常清单", "汇总指标", "月度汇总", "对手方汇总"]
    assert Decimal(str(workbook["标准流水"]["E2"].value)) == Decimal("10000.10")
    assert workbook["标准流水"]["E2"].number_format == "#,##0.00"
