from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

from .models import AnalysisResult, Statement


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
                float(item.income_amount),
                float(item.expense_amount),
                float(item.balance) if item.balance is not None else "",
                item.channel,
                item.postscript,
                item.confidence,
            ]
        )


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
    for key, label in labels.items():
        ws.append([label, analysis.metrics.get(key, "")])


def write_monthly(ws, analysis: AnalysisResult) -> None:
    ws.append(["月份", "收入", "支出", "交易笔数"])
    style_header(ws)
    for month, values in analysis.metrics.get("monthly", {}).items():
        ws.append([month, values.get("income"), values.get("expense"), values.get("count")])


def write_counterparties(ws, analysis: AnalysisResult) -> None:
    ws.append(["对手方", "收入", "支出", "总流水", "交易笔数"])
    style_header(ws)
    for item in analysis.metrics.get("top_counterparties", []):
        ws.append([item["name"], item["income"], item["expense"], item["total_flow"], item["count"]])


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
