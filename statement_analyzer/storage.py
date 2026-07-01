from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "jobs.sqlite3"
LEGACY_JSON_PATH = DATA_DIR / "jobs.json"


def create_job(job_id: str, file_name: str) -> None:
    now = now_iso()
    job = {
        "id": job_id,
        "file_name": file_name,
        "status": "processing",
        "created_at": now,
    }
    save_job(job)


def update_job(job_id: str, patch: dict[str, Any]) -> None:
    job = get_job(job_id) or {"id": job_id, "created_at": now_iso()}
    job.update(patch)
    job["updated_at"] = now_iso()
    save_job(job)


def get_job(job_id: str) -> dict[str, Any] | None:
    init_db()
    with closing(connect()) as connection:
        row = execute_fetchone(connection, "SELECT data_json FROM jobs WHERE id = {placeholder}", (job_id,))
    if not row:
        return None
    return json.loads(row_value(row, "data_json"))


def list_jobs() -> list[dict[str, Any]]:
    init_db()
    with closing(connect()) as connection:
        rows = execute_fetchall(connection, "SELECT data_json FROM jobs ORDER BY created_at DESC, id DESC", ())
    return [json.loads(row_value(row, "data_json")) for row in rows]


def save_job(job: dict[str, Any]) -> None:
    init_db(migrate_legacy=False)
    insert_job(job)


def insert_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    created_at = str(job.get("created_at") or now_iso())
    updated_at = str(job.get("updated_at") or "")
    file_name = str(job.get("file_name") or "")
    status = str(job.get("status") or "")
    data_json = json.dumps(job, ensure_ascii=False, default=str)

    with closing(connect()) as connection:
        execute(
            connection,
            """
            INSERT INTO jobs (id, file_name, status, created_at, updated_at, data_json)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            ON CONFLICT(id) DO UPDATE SET
                file_name = excluded.file_name,
                status = excluded.status,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                data_json = excluded.data_json
            """,
            (job_id, file_name, status, created_at, updated_at, data_json),
        )
        commit(connection)


def init_db(migrate_legacy: bool = True) -> None:
    if using_postgres():
        init_postgres_schema()
    else:
        init_sqlite_schema()
        if migrate_legacy:
            migrate_legacy_json_once()


def init_sqlite_schema() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as connection:
        connection.execute(schema_sql())
        connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC)")
        connection.commit()


def init_postgres_schema() -> None:
    with closing(connect()) as connection:
        execute(connection, schema_sql(), ())
        execute(connection, "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC)", ())
        commit(connection)


def schema_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        file_name TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT '',
        data_json TEXT NOT NULL
    )
    """


def migrate_legacy_json_once() -> None:
    if using_postgres() or not LEGACY_JSON_PATH.exists():
        return
    with closing(connect()) as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
    if count:
        return

    try:
        legacy_data = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return

    if not isinstance(legacy_data, dict):
        return

    for job_id, job in legacy_data.items():
        if isinstance(job, dict):
            job.setdefault("id", job_id)
            insert_job(job)


def database_url() -> str:
    return os.getenv("DATABASE_URL", "")


def using_postgres() -> bool:
    value = database_url().lower()
    return value.startswith("postgres://") or value.startswith("postgresql://")


def connect():
    if using_postgres():
        from psycopg import connect as pg_connect
        from psycopg.rows import dict_row

        return pg_connect(database_url(), row_factory=dict_row)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def execute(connection, sql: str, params: tuple[Any, ...]):
    return connection.execute(format_sql(sql), params)


def execute_fetchone(connection, sql: str, params: tuple[Any, ...]):
    return execute(connection, sql, params).fetchone()


def execute_fetchall(connection, sql: str, params: tuple[Any, ...]):
    return execute(connection, sql, params).fetchall()


def format_sql(sql: str) -> str:
    placeholder = "%s" if using_postgres() else "?"
    return sql.replace("{placeholder}", placeholder)


def commit(connection) -> None:
    connection.commit()


def row_value(row: Any, key: str) -> Any:
    return row[key]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
