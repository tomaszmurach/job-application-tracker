import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_empty_database_upgrades_to_head(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "alembic.ini"
    database_path = tmp_path / "migrated.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    environment["PYTHONPATH"] = str(project_root)

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(config_path), "upgrade", "head"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert database_path.is_file()

    head = ScriptDirectory.from_config(Config(str(config_path))).get_current_head()
    connection = sqlite3.connect(database_path)
    try:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        assert revision == (head,)
        connection.execute(
            "INSERT INTO applications (company, position, status) VALUES (?, ?, ?)",
            ("Migration test", "Developer", "Applied"),
        )
        timestamp = connection.execute("SELECT applied_at FROM applications").fetchone()[0]
        assert isinstance(datetime.fromisoformat(timestamp), datetime)
    finally:
        connection.close()
