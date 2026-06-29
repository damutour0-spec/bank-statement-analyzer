from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class Transaction:
    row_no: int
    transaction_date: datetime | None
    summary: str = ""
    counterparty_name: str = ""
    income_amount: Decimal = Decimal("0")
    expense_amount: Decimal = Decimal("0")
    balance: Decimal | None = None
    currency: str = "CNY"
    channel: str = ""
    postscript: str = ""
    raw_text: str = ""
    confidence: float = 1.0

    def signed_amount(self) -> Decimal:
        return self.income_amount - self.expense_amount

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("income_amount", "expense_amount", "balance"):
            if data[key] is not None:
                data[key] = str(data[key])
        if self.transaction_date:
            data["transaction_date"] = self.transaction_date.strftime("%Y-%m-%d %H:%M:%S")
        return data


@dataclass
class Finding:
    finding_type: str
    severity: str
    title: str
    description: str
    row_no: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Statement:
    file_name: str
    file_type: str
    bank_name: str = "未知银行"
    account_name: str = ""
    account_no_masked: str = ""
    transactions: list[Transaction] = field(default_factory=list)
    confidence: float = 1.0

    def to_summary_dict(self) -> dict[str, Any]:
        dates = [item.transaction_date for item in self.transactions if item.transaction_date]
        return {
            "file_name": self.file_name,
            "file_type": self.file_type,
            "bank_name": self.bank_name,
            "account_name": self.account_name,
            "account_no_masked": self.account_no_masked,
            "transaction_count": len(self.transactions),
            "start_date": min(dates).strftime("%Y-%m-%d") if dates else "",
            "end_date": max(dates).strftime("%Y-%m-%d") if dates else "",
            "confidence": self.confidence,
        }


@dataclass
class AnalysisResult:
    findings: list[Finding]
    metrics: dict[str, Any]

