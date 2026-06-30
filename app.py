from __future__ import annotations

import json
import mimetypes
import os
import shutil
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from statement_analyzer.exporter import export_workbook
from statement_analyzer.parser import parse_statement
from statement_analyzer.rules import analyze_statement
from statement_analyzer.storage import create_job, get_job, list_jobs, update_job


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
UPLOAD_DIR = ROOT / "data" / "uploads"
EXPORT_DIR = ROOT / "data" / "exports"
HOST = "127.0.0.1"
PORT = 8765
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 1024 * 1024
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


def max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return max(value, 1024 * 1024)


class AppHandler(BaseHTTPRequestHandler):
    server_version = "BankStatementAnalyzer/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_file(PUBLIC_DIR / "index.html")
            return
        if path == "/api/jobs":
            self._send_json({"jobs": list_jobs()})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.split("/")[-1]
            job = get_job(job_id)
            if not job:
                self._send_json({"error": "job not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(job)
            return
        if path.startswith("/exports/"):
            export_path = EXPORT_DIR / Path(path).name
            self._serve_file(export_path, download=True)
            return
        self._serve_file(PUBLIC_DIR / path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload":
            self._handle_upload()
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _handle_upload(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json({"error": "multipart/form-data required"}, HTTPStatus.BAD_REQUEST)
            return

        boundary = extract_boundary(content_type)
        if not boundary:
            self._send_json({"error": "multipart boundary is missing"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json({"error": "invalid Content-Length"}, HTTPStatus.BAD_REQUEST)
            return

        upload_limit = max_upload_bytes()
        if length <= 0:
            self._send_json({"error": "empty upload request"}, HTTPStatus.BAD_REQUEST)
            return
        if length > upload_limit + MULTIPART_OVERHEAD_BYTES:
            self._send_json(
                {"error": f"file is too large; limit is {upload_limit // 1024 // 1024}MB"},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return

        body = self.rfile.read(length)
        file_name, file_bytes = parse_multipart_file(body, boundary.encode())
        if not file_name or not file_bytes:
            self._send_json({"error": "file field is required"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            validate_upload(file_name, file_bytes, upload_limit)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        safe_name = sanitize_filename(file_name)
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
        self._send_json(job)

    def _serve_file(self, path: Path, download: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        with path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[server] {self.address_string()} - {format % args}")


def extract_boundary(content_type: str) -> str:
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            return part.split("=", 1)[1].strip().strip('"')
    return ""


def parse_multipart_file(body: bytes, boundary: bytes) -> tuple[str | None, bytes | None]:
    delimiter = b"--" + boundary
    for part in body.split(delimiter):
        if b"Content-Disposition" not in part or b'name="file"' not in part:
            continue
        header, _, content = part.partition(b"\r\n\r\n")
        if not content:
            continue
        file_name = None
        disposition = header.decode("utf-8", errors="ignore")
        marker = 'filename="'
        if marker in disposition:
            file_name = disposition.split(marker, 1)[1].split('"', 1)[0]
        content = content.rstrip(b"\r\n")
        if content.endswith(b"--"):
            content = content[:-2]
        return file_name, content
    return None, None


def validate_upload(file_name: str, file_bytes: bytes, upload_limit: int) -> None:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise ValueError(f"unsupported file type: {suffix or 'missing suffix'}; allowed: {allowed}")
    if len(file_bytes) > upload_limit:
        raise ValueError(f"file is too large; limit is {upload_limit // 1024 // 1024}MB")
    if suffix == ".pdf" and not file_bytes.startswith(b"%PDF"):
        raise ValueError("invalid PDF file signature")


def sanitize_filename(name: str) -> str:
    keep = []
    for char in Path(name).name:
        keep.append(char if char.isalnum() or char in ".-_" else "_")
    return "".join(keep) or "statement"


def main() -> None:
    load_dotenv()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Bank Statement Analyzer running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
