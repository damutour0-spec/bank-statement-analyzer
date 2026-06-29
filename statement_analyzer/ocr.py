from __future__ import annotations

import base64
import importlib.util
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image


class OcrUnavailableError(RuntimeError):
    pass


def extract_text_from_image(path: Path) -> str:
    validate_image(path)

    if importlib.util.find_spec("rapidocr_onnxruntime"):
        return extract_with_rapidocr(path)

    if importlib.util.find_spec("paddleocr"):
        return extract_with_paddleocr(path)

    if importlib.util.find_spec("pytesseract"):
        return extract_with_tesseract(path)

    if os.getenv("BAIDU_OCR_API_KEY") and os.getenv("BAIDU_OCR_SECRET_KEY"):
        return extract_with_baidu_ocr(path)

    raise OcrUnavailableError(
        "Image upload is supported, but no OCR engine is configured. "
        "Install rapidocr_onnxruntime/PaddleOCR/Tesseract, or set "
        "BAIDU_OCR_API_KEY and BAIDU_OCR_SECRET_KEY."
    )


def validate_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError("The image file cannot be opened. Please upload a valid JPG/PNG file.") from exc


def extract_with_rapidocr(path: Path) -> str:
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    result, _ = engine(str(path))
    if not result:
        return ""
    return "\n".join(item[1] for item in result if len(item) >= 2)


def extract_with_paddleocr(path: Path) -> str:
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
    import pytesseract

    with Image.open(path) as image:
        return pytesseract.image_to_string(image, lang="chi_sim+eng")


def extract_with_baidu_ocr(path: Path) -> str:
    token = get_baidu_access_token()
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={token}"
    payload = urllib.parse.urlencode(
        {"image": base64.b64encode(path.read_bytes()).decode("ascii")}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    if "error_msg" in data:
        raise RuntimeError(f"Baidu OCR failed: {data.get('error_msg')}")
    return "\n".join(item.get("words", "") for item in data.get("words_result", []))


def get_baidu_access_token() -> str:
    api_key = os.environ["BAIDU_OCR_API_KEY"]
    secret_key = os.environ["BAIDU_OCR_SECRET_KEY"]
    query = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        }
    )
    with urllib.request.urlopen(f"https://aip.baidubce.com/oauth/2.0/token?{query}", timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    if "access_token" not in data:
        raise RuntimeError(f"Baidu token request failed: {data}")
    return data["access_token"]
