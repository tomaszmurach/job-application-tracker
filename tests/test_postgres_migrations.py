"""Opt in with RUN_POSTGRES_TESTS=1; requires Docker and no external database."""

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import asyncpg
import pytest


INITIAL_REVISION = "cdd629732d9d"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def postgres_url() -> Iterator[str]:
    if os.environ.get("RUN_POSTGRES_TESTS") != "1":
        pytest.skip("Set RUN_POSTGRES_TESTS=1 to run the isolated Docker regression")

    docker = shutil.which("docker")
    assert docker is not None, "Docker is required when RUN_POSTGRES_TESTS=1"
    result = subprocess.run(
        [
            docker, "run", "--rm", "--detach",
            "--publish", "127.0.0.1::5432",
            "--tmpfs", "/var/lib/postgresql/data",
            "--env", "POSTGRES_DB=migration_test",
            "--env", "POSTGRES_PASSWORD=migration-test",
            "postgres:17-alpine",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    container_id = result.stdout.strip()
    try:
        deadline = time.monotonic() + 30
        while True:
            ready = subprocess.run(
                [docker, "exec", container_id, "pg_isready", "-h", "127.0.0.1",
                 "-U", "postgres", "-d", "migration_test"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if ready.returncode == 0:
                break
            assert time.monotonic() < deadline, ready.stdout + ready.stderr
            time.sleep(0.2)

        port = subprocess.run(
            [docker, "port", container_id, "5432/tcp"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip().rsplit(":", 1)[1]
        yield (
            f"postgresql+asyncpg://postgres:migration-test@127.0.0.1:{port}"
            "/migration_test"
        )
    finally:
        subprocess.run(
            [docker, "rm", "--force", container_id],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )


def run_alembic(tmp_path: Path, url: str, command: str, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(PROJECT_ROOT / "alembic.ini"),
         command, revision],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_populated_postgres_preserves_ids_across_migrations(
    tmp_path: Path, postgres_url: str
) -> None:
    run_alembic(tmp_path, postgres_url, "upgrade", INITIAL_REVISION)
    connection = await asyncpg.connect(
        postgres_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    try:
        for company in ["Existing A", "Existing B", "Existing C"]:
            await connection.execute(
                "INSERT INTO applications (company, position, status) "
                "VALUES ($1, 'Developer', 'Applied')", company,
            )
        original = await connection.fetch(
            "SELECT id, company, position, status, notes FROM applications ORDER BY id"
        )
        identity_query = (
            "SELECT to_regclass('applications')::oid AS table_oid, "
            "pg_get_serial_sequence('applications', 'id')::regclass::oid AS sequence_oid"
        )
        original_identity = await connection.fetchrow(identity_query)

        run_alembic(tmp_path, postgres_url, "upgrade", "head")
        assert await connection.fetch(
            "SELECT id, company, position, status, notes FROM applications ORDER BY id"
        ) == original
        assert all(
            isinstance(row["applied_at"], datetime)
            for row in await connection.fetch("SELECT applied_at FROM applications")
        )
        inserted = await connection.fetchrow(
            "INSERT INTO applications (company, position, status) "
            "VALUES ('After upgrade', 'Developer', 'Applied') RETURNING id, applied_at"
        )
        assert inserted["id"] > max(row["id"] for row in original)
        assert isinstance(inserted["applied_at"], datetime)
        assert inserted["applied_at"].tzinfo is None
        assert await connection.fetchrow(identity_query) == original_identity
        with pytest.raises(asyncpg.NotNullViolationError):
            await connection.execute(
                "INSERT INTO applications (company, position, status, applied_at) "
                "VALUES ('Invalid null', 'Developer', 'Applied', NULL)"
            )

        before_downgrade = await connection.fetch(
            "SELECT id, company, position, status, notes FROM applications ORDER BY id"
        )
        run_alembic(tmp_path, postgres_url, "downgrade", INITIAL_REVISION)
        assert await connection.fetchrow(identity_query) == original_identity
        assert await connection.fetch(
            "SELECT id, company, position, status, notes FROM applications ORDER BY id"
        ) == before_downgrade
        assert not await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'applications' "
            "AND column_name = 'applied_at')"
        )
        downgraded_id = await connection.fetchval(
            "INSERT INTO applications (company, position, status) "
            "VALUES ('After downgrade', 'Developer', 'Applied') RETURNING id"
        )
        assert downgraded_id > inserted["id"]

        run_alembic(tmp_path, postgres_url, "upgrade", "head")
        assert await connection.fetchrow(identity_query) == original_identity
        rows = await connection.fetch("SELECT id, applied_at FROM applications")
        assert len(rows) == len(original) + 2
        assert all(isinstance(row["applied_at"], datetime) for row in rows)
        assert await connection.fetchval(
            "INSERT INTO applications (company, position, status) "
            "VALUES ('After re-upgrade', 'Developer', 'Applied') RETURNING id"
        ) > downgraded_id
    finally:
        await connection.close()
