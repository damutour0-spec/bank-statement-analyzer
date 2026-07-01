from __future__ import annotations

import base64
import importlib.util
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image


class OcrUnavailableError(RuntimeError):
    pass


BAIDU_OCR_ENDPOINT = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"
BAIDU_TOKEN_ENDPOINT = "https://aip.baidubce.com/oauth/2.0/token"
_BAIDU_ACCESS_TOKEN = ""
_BAIDU_ACCESS_TOKEN_EXPIRES_AT = 0.0


def extract_text_from_image(path: Path) -> str:
    validate_image(path)
    provider = ocr_provider()

    if provider in {"baidu", "baidu_ocr"}:
        return extract_with_baidu_ocr(path)
    if provider == "rapidocr":
        return extract_with_rapidocr(path)
    if provider == "paddleocr":
        return extract_with_paddleocr(path)
    if provider == "tesseract":
        return extract_with_tesseract(path)
    if provider not in {"", "auto"}:
        raise OcrUnavailableError(f"Unsupported OCR_PROVIDER: {provider}")

    if importlib.util.find_spec("rapidocr_onnxruntime"):
        return extract_with_rapidocr(path)

    if importlib.util.find_spec("paddleocr"):
        return extract_with_paddleocr(path)

    if importlib.util.find_spec("pytesseract"):
        return extract_with_tesseract(path)

    if baidu_ocr_configured():
        return extract_with_baidu_ocr(path)

    raise OcrUnavailableError(
        "图片识别需要配置 OCR。Render 线上推荐配置百度 OCR 环境变量 "
        "BAIDU_OCR_API_KEY 和 BAIDU_OCR_SECRET_KEY；未配置前请上传 Excel、CSV 或原生文本 PDF。"
    )


def ocr_provider() -> str:
    return os.getenv("OCR_PROVIDER", "auto").strip().lower()


def baidu_ocr_configured() -> bool:
    return bool(os.getenv("BAIDU_OCR_API_KEY") and os.getenv("BAIDU_OCR_SECRET_KEY"))


def validate_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError("图片文件无法打开，请上传有效的 JPG/PNG/BMP/TIFF/WEBP 文件。") from exc


def extract_with_rapidocr(path: Path) -> str:
    if not importlib.util.find_spec("rapidocr_onnxruntime"):
        raise OcrUnavailableError("rapidocr_onnxruntime is not installed.")
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    result, _ = engine(str(path))
    if not result:
        return ""
    return "\n".join(item[1] for item in result if len(item) >= 2)


def extract_with_paddleocr(path: Path) -> str:
    if not importlib.util.find_spec("paddleocr"):
        raise OcrUnavailableError("paddleocr is not installed.")
    from paddleocr import PaddleOCR

    engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    result = engine.ocr(str(path), cls=True)
    lines: list[str] = []
    for page in result or []:
        for line in page or []:
            if len(line) >= 2 and line[1]:
                lines.append(str(line[1][0]))
    return "\n".join(lines)


def extract_with_tesseract(path: Path) -> str:
    if not importlib.util.find_spec("pytesseract"):
        raise OcrUnavailableError("pytesseract is not installed.")
    import pytesseract

    with Image.open(path) as image:
        return pytesseract.image_to_string(image, lang="chi_sim+eng")


def extract_with_baidu_ocr(path: Path) -> str:
    if not baidu_ocr_configured():
        raise OcrUnavailableError(
            "百度 OCR 未配置：请在 Render 环境变量中设置 BAIDU_OCR_API_KEY 和 BAIDU_OCR_SECRET_KEY。"
        )
    token = get_baidu_access_token()
    endpoint = os.getenv("BAIDU_OCR_ENDPOINT", BAIDU_OCR_ENDPOINT)
    url = f"{endpoint}?access_token={urllib.parse.quote(token)}"
    payload = urllib.parse.urlencode(baidu_ocr_payload(path)).encode("utf-8")
    data = post_form_json(url, payload)
    if "error_code" in data or "error_msg" in data:
        message = data.get("error_msg") or data.get("error") or "unknown error"
        raise RuntimeError(f"百度 OCR 调用失败：{message}")
    return "\n".join(item.get("words", "") for item in data.get("words_result", []) if item.get("words"))


def baidu_ocr_payload(path: Path) -> dict[str, str]:
    return {
        "image": base64.b64encode(path.read_bytes()).decode("ascii"),
        "language_type": os.getenv("BAIDU_OCR_LANGUAGE_TYPE", "CHN_ENG"),
        "detect_direction": os.getenv("BAIDU_OCR_DETECT_DIRECTION", "true"),
    }


def get_baidu_access_token() -> str:
    global _BAIDU_ACCESS_TOKEN, _BAIDU_ACCESS_TOKEN_EXPIRES_AT

    now = time.time()
    if _BAIDU_ACCESS_TOKEN and _BAIDU_ACCESS_TOKEN_EXPIRES_AT > now + 60:
        return _BAIDU_ACCESS_TOKEN

    api_key = os.environ["BAIDU_OCR_API_KEY"]
    secret_key = os.environ["BAIDU_OCR_SECRET_KEY"]
    query = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        }
    )
    token_endpoint = os.getenv("BAIDU_TOKEN_ENDPOINT", BAIDU_TOKEN_ENDPOINT)
    request = urllib.request.Request(
        f"{token_endpoint}?{query}",
        data=b"",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    if "access_token" not in data:
        raise RuntimeError(f"百度 OCR token 获取失败：{safe_error_payload(data)}")

    _BAIDU_ACCESS_TOKEN = data["access_token"]
    expires_in = int(data.get("expires_in") or 2592000)
    _BAIDU_ACCESS_TOKEN_EXPIRES_AT = now + max(expires_in - 300, 60)
    return _BAIDU_ACCESS_TOKEN


def post_form_json(url: str, payload: bytes) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_error_payload(data: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(data)
    for key in ("access_token", "refresh_token"):
        redacted.pop(key, None)
    return redacted


def reset_baidu_token_cache() -> None:
    global _BAIDU_ACCESS_TOKEN, _BAIDU_ACCESS_TOKEN_EXPIRES_AT
    _BAIDU_ACCESS_TOKEN = ""
    _BAIDU_ACCESS_TOKEN_EXPIRES_AT = 0.0
