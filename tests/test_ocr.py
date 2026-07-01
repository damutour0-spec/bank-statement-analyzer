import json
import urllib.parse
from pathlib import Path

import pytest

from statement_analyzer import ocr


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def clear_baidu_cache(monkeypatch):
    ocr.reset_baidu_token_cache()
    for name in (
        "BAIDU_OCR_API_KEY",
        "BAIDU_OCR_SECRET_KEY",
        "BAIDU_OCR_LANGUAGE_TYPE",
        "BAIDU_OCR_DETECT_DIRECTION",
        "BAIDU_OCR_ENDPOINT",
        "BAIDU_TOKEN_ENDPOINT",
        "OCR_PROVIDER",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    ocr.reset_baidu_token_cache()


def test_baidu_ocr_payload_uses_image_bytes_and_defaults(tmp_path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"abc")

    payload = ocr.baidu_ocr_payload(image)

    assert payload["image"] == "YWJj"
    assert payload["language_type"] == "CHN_ENG"
    assert payload["detect_direction"] == "true"


def test_baidu_access_token_is_cached(monkeypatch):
    monkeypatch.setenv("BAIDU_OCR_API_KEY", "api-key")
    monkeypatch.setenv("BAIDU_OCR_SECRET_KEY", "secret-key")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        assert "grant_type=client_credentials" in request.full_url
        assert "client_id=api-key" in request.full_url
        assert "client_secret=secret-key" in request.full_url
        return FakeResponse({"access_token": "token-1", "expires_in": 3600})

    monkeypatch.setattr(ocr.urllib.request, "urlopen", fake_urlopen)

    assert ocr.get_baidu_access_token() == "token-1"
    assert ocr.get_baidu_access_token() == "token-1"
    assert len(calls) == 1


def test_extract_with_baidu_ocr_posts_form_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("BAIDU_OCR_API_KEY", "api-key")
    monkeypatch.setenv("BAIDU_OCR_SECRET_KEY", "secret-key")
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"abc")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        if "oauth/2.0/token" in request.full_url:
            return FakeResponse({"access_token": "token-1", "expires_in": 3600})
        return FakeResponse({"words_result": [{"words": "交易日期 摘要"}, {"words": "2026-05-01 工资"}]})

    monkeypatch.setattr(ocr.urllib.request, "urlopen", fake_urlopen)

    text = ocr.extract_with_baidu_ocr(image)

    assert text == "交易日期 摘要\n2026-05-01 工资"
    ocr_request = calls[1]
    assert "general_basic?access_token=token-1" in ocr_request.full_url
    form = urllib.parse.parse_qs(ocr_request.data.decode("utf-8"))
    assert form["image"] == ["YWJj"]
    assert form["language_type"] == ["CHN_ENG"]
    assert form["detect_direction"] == ["true"]


def test_extract_with_baidu_ocr_requires_credentials(tmp_path):
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"abc")

    with pytest.raises(ocr.OcrUnavailableError) as exc_info:
        ocr.extract_with_baidu_ocr(image)

    assert "BAIDU_OCR_API_KEY" in str(exc_info.value)
