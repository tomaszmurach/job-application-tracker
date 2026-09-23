import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def application_data() -> dict[str, str | None]:
    return {
        "company": "Test Company",
        "position": "Developer",
        "status": "Applied",
        "notes": "Test notes",
    }


@pytest_asyncio.fixture
async def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    # Configure before importing the app, outside the developer's .env directory.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from database import Base, get_db
    from main import app

    database_path = tmp_path / "applications.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        app.dependency_overrides[get_db] = override_get_db
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as test_client:
                yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        await engine.dispose()


@pytest_asyncio.fixture
async def created_application(
    client: AsyncClient, application_data: dict[str, str | None]
) -> dict[str, Any]:
    response = await client.post("/applications", json=application_data)
    assert response.status_code == 201
    return response.json()
