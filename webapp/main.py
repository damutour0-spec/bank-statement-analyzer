from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from statement_analyzer.exporter import export_workbook
from statement_analyzer.parser import parse_statement
from statement_analyzer.rules import analyze_statement
from statement_analyzer.storage import create_job, get_job, list_jobs, update_job


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
UPLOAD_DIR = ROOT / "data" / "uploads"
EXPORT_DIR = ROOT / "data" / "exports"
HOST = "127.0.0.1"
PORT = 8765
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_FILE_RETENTION_HOURS = 24
ALLOWED_SUFFIXES = {
    ".csv",
    ".txt",
    ".xlsx",
    ".xlsm",
    ".xltx",
    ".xltm",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
}


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def int_from_env(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def max_upload_bytes() -> int:
    return int_from_env("MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES, 1024 * 1024)


def file_retention_hours() -> int:
    return int_from_env("FILE_RETENTION_HOURS", DEFAULT_FILE_RETENTION_HOURS, 1)


def cleanup_expired_files() -> None:
    cutoff = time.time() - file_retention_hours() * 3600
    for directory in (UPLOAD_DIR, EXPORT_DIR):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    load_dotenv()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_expired_files()
    yield


app = FastAPI(title="Bank Statement Analyzer", version="0.2", lifespan=lifespan)


@app.get("/api/jobs")
def api_list_jobs() -> dict[str, Any]:
    cleanup_expired_files()
    return {"jobs": list_jobs()}


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="job not found")
    return job


@app.post("/api/upload")
async def api_upload(file: Annotated[UploadFile, File(...)]) -> dict[str, Any]:
    upload_limit = max_upload_bytes()
    file_bytes = await read_upload_bytes(file, upload_limit)
    validate_upload(file.filename or "statement", file_bytes, upload_limit)

    job_id = f"job_{uuid.uuid4().hex[:12]}"
    safe_name = sanitize_filename(file.filename or "statement")
    upload_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(file_bytes)

    create_job(job_id, safe_name)
    try:
        statement = parse_statement(upload_path)
        analysis = analyze_statement(statement)
        export_file = EXPORT_DIR / f"{job_id}_analysis.xlsx"
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        export_workbook(statement, analysis, export_file)
        update_job(
            job_id,
            {
                "status": "done",
                "statement": statement.to_summary_dict(),
                "transactions": [item.to_dict() for item in statement.transactions],
                "findings": [item.to_dict() for item in analysis.findings],
                "metrics": analysis.metrics,
                "export_url": f"/exports/{export_file.name}",
            },
        )
    except Exception as exc:
        update_job(job_id, {"status": "failed", "error": str(exc)})

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="job state missing")
    return job


@app.get("/exports/{file_name}")
def download_export(file_name: str) -> FileResponse:
    cleanup_expired_files()
    export_path = EXPORT_DIR / Path(file_name).name
    if not export_path.exists() or not export_path.is_file():
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="export not found or expired")
    return FileResponse(
        export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=export_path.name,
    )


async def read_upload_bytes(file: UploadFile, upload_limit: int) -> bytes:
    file_bytes = await file.read(upload_limit + 1)
    if not file_bytes:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="file field is required")
    if len(file_bytes) > upload_limit:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail=f"file is too large; limit is {upload_limit // 1024 // 1024}MB",
        )
    return file_bytes


def validate_upload(file_name: str, file_bytes: bytes, upload_limit: int) -> None:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"unsupported file type: {suffix or 'missing suffix'}; allowed: {allowed}",
        )
    if len(file_bytes) > upload_limit:
        raise HTTPException(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail=f"file is too large; limit is {upload_limit // 1024 // 1024}MB",
        )
    if suffix == ".pdf" and not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid PDF file signature")


def sanitize_filename(name: str) -> str:
    keep = []
    for char in Path(name).name:
        keep.append(char if char.isalnum() or char in ".-_" else "_")
    return "".join(keep) or "statement"


def run() -> None:
    uvicorn.run("webapp.main:app", host=HOST, port=PORT, reload=False)


app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")


if __name__ == "__main__":
    run()
