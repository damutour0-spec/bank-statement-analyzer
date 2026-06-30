from __future__ import annotations

from .models import Transaction


CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("payroll", ("salary", "payroll", "bonus", "工资", "薪资", "奖金")),
    ("operating_income", ("revenue", "income", "service fee", "项目款", "合同款", "回款")),
    ("procurement", ("purchase", "supplier", "material", "采购", "材料", "设备")),
    ("tax", ("tax", "税", "税务")),
    ("rent_utilities", ("rent", "utility", "房租", "租金", "物业", "水电")),
    ("financing", ("loan", "interest", "finance", "借款", "还款", "利息")),
    ("investment", ("fund", "security", "dividend", "理财", "基金", "证券", "分红")),
    ("internal_transfer", ("internal", "reimburse", "往来", "备用金", "报销")),
    ("bill_business", ("bill", "acceptance", "endorsement", "汇票", "票据", "背书")),
)

DEFAULT_CATEGORY = "other"


def classify_transaction(transaction: Transaction) -> str:
    text = normalize_text(
        " ".join(
            [
                transaction.summary,
                transaction.postscript,
                transaction.counterparty_name,
                transaction.channel,
                transaction.raw_text,
            ]
        )
    )
    for category, keywords in CATEGORY_RULES:
        if any(normalize_text(keyword) in text for keyword in keywords):
            return category
    return DEFAULT_CATEGORY


def normalize_text(value: str) -> str:
    return "".join(str(value or "").lower().split())
