from datetime import datetime
from decimal import Decimal
from http import HTTPStatus

import pytest
from fastapi import HTTPException

from statement_analyzer.ocr import OcrUnavailableError
from webapp.main import (
    job_id_from_export_name,
    parse_datetime,
    parse_decimal,
    parse_optional_decimal,
    sanitize_filename,
    statement_from_job,
    upload_error_message,
    validate_upload,
)


def test_sanitize_filename_removes_path_and_unsafe_characters():
    assert sanitize_filename("../银行 流水.xlsx") == "银行_流水.xlsx"


def test_validate_upload_accepts_supported_csv():
    validate_upload("statement.csv", b"date,amount\n", 1024)


def test_validate_upload_rejects_unsupported_suffix():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload("statement.exe", b"x", 1024)

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_validate_upload_rejects_invalid_pdf_signature():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload("statement.pdf", b"not a pdf", 1024)

    assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST


def test_validate_upload_rejects_large_file():
    with pytest.raises(HTTPException) as exc_info:
        validate_upload("statement.csv", b"12345", 4)

    assert exc_info.value.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE


def test_job_id_from_export_name():
    assert job_id_from_export_name("job_abc123_analysis.xlsx") == "job_abc123"
    assert job_id_from_export_name("../job_abc123_analysis.xlsx") == "job_abc123"
    assert job_id_from_export_name("job_abc123.txt") == ""
    assert job_id_from_export_name("abc123_analysis.xlsx") == ""


def test_parse_datetime_accepts_saved_transaction_format():
    assert parse_datetime("2026-05-01 00:00:00") == datetime(2026, 5, 1)
    assert parse_datetime("2026-05-01") == datetime(2026, 5, 1)
    assert parse_datetime("") is None


def test_parse_decimal_helpers():
    assert parse_decimal("100.50") == Decimal("100.50")
    assert parse_decimal("") == Decimal("0")
    assert parse_optional_decimal("100.50") == Decimal("100.50")
    assert parse_optional_decimal("") is None


def test_statement_from_saved_job_payload():
    job = {
        "file_name": "sample.csv",
        "statement": {
            "file_name": "job_1_sample.csv",
            "file_type": "csv",
            "bank_name": "未知银行",
            "confidence": 0.95,
        },
        "transactions": [
            {
                "row_no": 2,
                "transaction_date": "2026-05-01 00:00:00",
                "summary": "工资",
                "counterparty_name": "某公司",
                "income_amount": "20000.00",
                "expense_amount": "0",
                "balance": "30000.00",
                "confidence": 0.95,
            }
        ],
    }

    statement = statement_from_job(job)

    assert statement.file_name == "job_1_sample.csv"
    assert statement.file_type == "csv"
    assert statement.confidence == 0.95
    assert len(statement.transactions) == 1
    assert statement.transactions[0].income_amount == Decimal("20000.00")
    assert statement.transactions[0].balance == Decimal("30000.00")


def test_upload_error_message_preserves_ocr_guidance():
    message = upload_error_message(OcrUnavailableError("图片识别需要配置 OCR。"))

    assert message == "图片识别需要配置 OCR。"


def test_upload_error_message_rewrites_unrecognized_transactions():
    message = upload_error_message(ValueError("未能识别交易明细，请上传带表头的 Excel/CSV。"))

    assert "图片或扫描件请先配置百度 OCR" in message
