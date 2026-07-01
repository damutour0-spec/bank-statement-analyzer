def test_sqlite_storage_roundtrip(tmp_path, monkeypatch):
    import statement_analyzer.storage as storage

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(storage, "LEGACY_JSON_PATH", tmp_path / "jobs.json")

    storage.create_job("job_1", "statement.csv")
    storage.update_job("job_1", {"status": "done", "metrics": {"transaction_count": 2}})

    job = storage.get_job("job_1")
    assert job is not None
    assert job["id"] == "job_1"
    assert job["file_name"] == "statement.csv"
    assert job["status"] == "done"
    assert job["metrics"] == {"transaction_count": 2}
    assert "updated_at" in job

    jobs = storage.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "job_1"


def test_legacy_jobs_json_is_migrated_once(tmp_path, monkeypatch):
    import statement_analyzer.storage as storage

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "jobs.sqlite3")
    monkeypatch.setattr(storage, "LEGACY_JSON_PATH", tmp_path / "jobs.json")
    storage.LEGACY_JSON_PATH.write_text(
        '{"job_legacy":{"id":"job_legacy","file_name":"old.csv","status":"done","created_at":"2026-01-01T00:00:00"}}',
        encoding="utf-8",
    )

    job = storage.get_job("job_legacy")
    assert job is not None
    assert job["file_name"] == "old.csv"
    assert job["status"] == "done"


def test_storage_uses_postgres_only_for_postgres_database_url(monkeypatch):
    import statement_analyzer.storage as storage

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert storage.using_postgres() is False

    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/jobs.sqlite3")
    assert storage.using_postgres() is False

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    assert storage.using_postgres() is True

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/db")
    assert storage.using_postgres() is True


def test_sql_placeholder_changes_by_backend(monkeypatch):
    import statement_analyzer.storage as storage

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert storage.format_sql("WHERE id = {placeholder}") == "WHERE id = ?"

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    assert storage.format_sql("WHERE id = {placeholder}") == "WHERE id = %s"
