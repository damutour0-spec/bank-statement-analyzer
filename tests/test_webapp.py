from http import HTTPStatus

import pytest
from fastapi import HTTPException

from webapp.main import sanitize_filename, validate_upload


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
