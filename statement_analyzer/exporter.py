from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Font, PatternFill

from .models import AnalysisResult, Statement


AMOUNT_FORMAT = "#,##0.00"


def export_workbook(statement: Statement, analysis: AnalysisResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = "标准流水"
    write_standard_transactions(ws, statement)
    write_findings(workbook.create_sheet("异常清单"), analysis)
    write_metrics(workbook.create_sheet("汇总指标"), analysis)
    write_monthly(workbook.create_sheet("月度汇总"), analysis)
    write_counterparties(workbook.create_sheet("对手方汇总"), analysis)
    for sheet in workbook.worksheets:
        autosize(sheet)
    workbook.save(path)


def write_standard_transactions(ws, statement: Statement) -> None:
    headers = ["行号", "交易时间", "摘要", "对方户名", "收入", "支出", "余额", "渠道", "附言", "置信度"]
    ws.append(headers)
    style_header(ws)
    for item in statement.transactions:
        ws.append(
            [
                item.row_no,
                item.transaction_date.strftime("%Y-%m-%d %H:%M:%S") if item.transaction_date else "",
                item.summary,
                item.counterparty_name,
                item.income_amount,
                item.expense_amount,
                item.balance if item.balance is not None else "",
                item.channel,
                item.postscript,
                item.confidence,
            ]
        )
    format_amount_columns(ws, ["E", "F", "G"])


def write_findings(ws, analysis: AnalysisResult) -> None:
    ws.append(["严重度", "类型", "标题", "行号", "说明", "建议"])
    style_header(ws)
    fills = {
        "high": PatternFill("solid", fgColor="FCA5A5"),
        "warn": PatternFill("solid", fgColor="FDE68A"),
        "info": PatternFill("solid", fgColor="BFDBFE"),
    }
    for finding in analysis.findings:
        ws.append(
            [
                finding.severity,
                finding.finding_type,
                finding.title,
                finding.row_no or "",
                finding.description,
                finding.suggestion,
            ]
        )
        fill = fills.get(finding.severity)
        if fill:
            for cell in ws[ws.max_row]:
                cell.fill = fill


def write_metrics(ws, analysis: AnalysisResult) -> None:
    ws.append(["指标", "值"])
    style_header(ws)
    labels = {
        "transaction_count": "交易笔数",
        "total_income": "总收入",
        "total_expense": "总支出",
        "net_flow": "净流入",
        "min_balance": "最低余额",
        "max_balance": "最高余额",
        "avg_balance": "平均余额",
    }
    amount_keys = {"total_income", "total_expense", "net_flow", "min_balance", "max_balance", "avg_balance"}
    for key, label in labels.items():
        value = analysis.metrics.get(key, "")
        ws.append([label, decimal_or_original(value) if key in amount_keys else value])
    format_amount_columns(ws, ["B"])


def write_monthly(ws, analysis: AnalysisResult) -> None:
    ws.append(["月份", "收入", "支出", "交易笔数"])
    style_header(ws)
    for month, values in analysis.metrics.get("monthly", {}).items():
        ws.append(
            [
                month,
                decimal_or_original(values.get("income")),
                decimal_or_original(values.get("expense")),
                values.get("count"),
            ]
        )
    format_amount_columns(ws, ["B", "C"])


def write_counterparties(ws, analysis: AnalysisResult) -> None:
    ws.append(["对手方", "收入", "支出", "总流水", "交易笔数"])
    style_header(ws)
    for item in analysis.metrics.get("top_counterparties", []):
        ws.append(
            [
                item["name"],
                decimal_or_original(item["income"]),
                decimal_or_original(item["expense"]),
                decimal_or_original(item["total_flow"]),
                item["count"],
            ]
        )
    format_amount_columns(ws, ["B", "C", "D"])


def decimal_or_original(value: Any) -> Decimal | Any:
    if value in (None, ""):
        return ""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return value


def format_amount_columns(ws, column_letters: list[str]) -> None:
    for letter in column_letters:
        for cell in ws[letter][1:]:
            if isinstance(cell.value, Decimal):
                cell.number_format = AMOUNT_FORMAT


def style_header(ws) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F2937")


def autosize(ws) -> None:
    for column in ws.columns:
        max_len = 0
        letter = column[0].column_letter
        for cell in column:
            max_len = max(max_len, len(str(cell.value or "")))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 42)
