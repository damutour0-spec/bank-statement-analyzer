from __future__ import annotations

from dataclasses import replace

from .models import Statement, Transaction


def redact_statement(statement: Statement) -> Statement:
    return replace(
        statement,
        account_name=mask_name(statement.account_name),
        account_no_masked=mask_text(statement.account_no_masked),
        transactions=[redact_transaction(item) for item in statement.transactions],
    )


def redact_transaction(transaction: Transaction) -> Transaction:
    return replace(
        transaction,
        summary=mask_text(transaction.summary),
        counterparty_name=mask_name(mask_text(transaction.counterparty_name)),
        channel=mask_text(transaction.channel),
        postscript=mask_text(transaction.postscript),
        raw_text=mask_text(transaction.raw_text),
    )


def mask_text(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    buffer = ""
    for char in str(value):
        if char.isdigit():
            buffer += char
            continue
        if buffer:
            parts.append(mask_number(buffer))
            buffer = ""
        parts.append(char)
    if buffer:
        parts.append(mask_number(buffer))
    return "".join(parts)


def mask_number(value: str) -> str:
    if len(value) < 8:
        return value
    return "*" * max(len(value) - 4, 1) + value[-4:]


def mask_name(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if len(text) <= 1:
        return "*"
    if len(text) == 2:
        return text[0] + "*"
    if len(text) <= 4:
        return text[0] + "*" * (len(text) - 2) + text[-1]
    return text[:2] + "*" * max(len(text) - 4, 2) + text[-2:]
