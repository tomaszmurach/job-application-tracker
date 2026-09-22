# Job Application Tracker

> [!NOTE]
> **Documentation update in progress.**
> The project has recently been extended with Docker, PostgreSQL, CI/CD, container registry publishing, and Kubernetes deployment infrastructure. The README is being updated to reflect the current architecture and setup.

## 1. Overview

Job Application Tracker is an asynchronous REST API built with FastAPI for
managing and tracking recruitment applications.

The project demonstrates practical Python backend development with async
SQLAlchemy, Pydantic validation, Alembic migrations, environment-based
configuration, dependency injection, and isolated integration testing.

## 2. Features

- Asynchronous CRUD API built with FastAPI and SQLAlchemy 2.x.
- Request and response validation with Pydantic.
- Partial PATCH updates with explicit omitted-vs-null semantics.
- Status-based application filtering.
- Database-managed application timestamps.
- Versioned schema migrations with Alembic.
- Environment-based configuration with pydantic-settings.
- 28 automated integration and migration tests using pytest and HTTPX.

## 3. Technology stack

Tested with **Python 3.13**.

| Component | Technology |
| --- | --- |
| HTTP API | FastAPI, Uvicorn |
| Validation and configuration | Pydantic, pydantic-settings |
| Persistence | SQLAlchemy 2.x async ORM, SQLite, aiosqlite |
| Schema migrations | Alembic |
| Tests | pytest, pytest-asyncio, HTTPX |

Direct dependency versions are pinned in `requirements.txt` and
`requirements-dev.txt`.

## 4. API endpoints

| Method | Path | Behavior | Success |
| --- | --- | --- | --- |
| GET | `/health` | Application liveness | 200 |
| POST | `/applications` | Create an application | 201 |
| GET | `/applications` | List applications; optional `status` filter | 200 |
| GET | `/applications/{id}` | Retrieve one application | 200 |
| PATCH | `/applications/{id}` | Update supplied fields | 200 |
| DELETE | `/applications/{id}` | Delete an application | 204, empty body |

Missing applications return 404. Invalid request data returns 422.
An empty collection returns `[]`. The health endpoint does not check the database.

Example create request (also available through **Try it out** in `/docs`):

```http
POST /applications
Content-Type: application/json

{
  "company": "Example Company",
  "position": "Junior Python Developer",
  "status": "Applied",
  "notes": "Applied through the company website."
}
```

Responses include an integer `id` and `applied_at`. Filter using
`GET /applications?status=Interview`. Invalid statuses produce 422.
Listing currently returns all matching records, with no guaranteed ordering or
pagination.

## 5. Quick start

Clone this repository using its GitHub URL and enter the project directory:

```sh
git clone https://github.com/tomaszmurach/job-application-tracker.git
cd job-application-tracker
```

Create and activate a Python 3.13 virtual environment.

**Windows PowerShell:**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

**macOS / Linux:**

```sh
python3.13 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

From the project root, install dependencies, create the database schema, and start
the development server:

```sh
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn main:app --reload
```

For runtime-only installation, use `requirements.txt` instead.

Open the interactive API documentation at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
The health endpoint is
[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## 6. Project structure

```text
.
|-- main.py                 # App composition, lifespan, health endpoint
|-- config.py               # Environment-based settings
|-- database.py             # Async engine, sessions, declarative base
|-- models.py               # SQLAlchemy application model
|-- schemas.py              # Request/response validation
|-- routers/
|   `-- applications.py     # CRUD and filtering endpoints
|-- alembic/
|   |-- env.py              # Async migration execution
|   `-- versions/           # Versioned schema changes
|-- tests/
|   |-- conftest.py         # Temporary databases and HTTP client fixtures
|   |-- test_applications.py
|   `-- test_migrations.py
|-- alembic.ini
|-- .env.example
|-- requirements.txt
`-- requirements-dev.txt
```

## 7. Configuration

Copy `.env.example` to `.env`:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./applications.db
```

Pydantic Settings reads `DATABASE_URL` from the environment or `.env`;
environment variables take precedence. The setting is required. Both the API
and Alembic use it.

Run commands from the project root: `.env` and the example SQLite path are
relative to the working directory. The database is created locally by migrations.
Local environment files, databases, virtual environments, and caches are ignored
by Git.

## 8. Validation / PATCH semantics

- `company` and `position`: required on creation, 1-100 characters after
  trimming surrounding whitespace. Blank or whitespace-only values are rejected.
- `status`: one of `Applied`, `Interview`, `Offer`, or `Rejected`
  (case-sensitive).
- `notes`: optional, nullable, at most 500 characters. Formatting is preserved.
- `applied_at`: generated by SQLite using `CURRENT_TIMESTAMP` when a record is
  inserted. It represents creation in this tracker, not a user-entered historical
  application date. SQLite supplies UTC; the current API serializes it without
  a timezone suffix. Updates do not change it.

PATCH uses only explicitly supplied fields:

| Request body | Effect |
| --- | --- |
| `{"status": "Interview"}` | Change status; preserve all other fields |
| `{"notes": null}` | Clear notes |
| `{"company": null}` | Reject with 422; likewise for position and status |
| `{}` | Leave the record unchanged |

## 9. Database migrations

Alembic owns the schema; application startup does **not** create tables.

```sh
python -m alembic upgrade head
python -m alembic current
python -m alembic history
python -m alembic check
```

For a model change, generate a migration, review its operations, apply it, and run
the tests:

```sh
python -m alembic revision --autogenerate -m "Describe the schema change"
python -m alembic upgrade head
python -m pytest -q
```

Commit reviewed migration files alongside model changes. SQLite schema changes
use Alembic batch operations where needed. Use the connected migration workflow
above; the table-recreation migration requires database reflection.

## 10. Running tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Run only the migration integration test:

```sh
python -m pytest -q tests/test_migrations.py
```

Each HTTP test gets its own temporary SQLite database and async session factory.
Fixtures restore dependency overrides and dispose engines after use. Tests supply
their own configuration and do not require the developer's `.env` or database.

The suite covers CRUD, filtering, missing records, validation, PATCH omission/null
semantics, timestamp serialization, and migration of an empty database to head.

## 11. Design decisions

- **Async SQLAlchemy:** request handlers await database I/O through an async driver,
  with one session per request. This demonstrates an async persistence workflow;
  it does not remove SQLite's write-concurrency limits.
- **SQLite:** deliberate for a small, locally runnable portfolio API. It keeps
  setup simple without a separate database service.
- **Separate schemas and ORM models:** API validation stays distinct from database
  representation.
- **Alembic:** schema changes are explicit and versioned; runtime and migrations
  share the same database configuration.
- **Small structure:** one router and a few focused modules are sufficient for
  this scope. The current scope does not require additional service or repository layers.
- **Scope:** this is an unauthenticated portfolio API focused on backend architecture,
  persistence, validation, migrations, and testing rather than user management.
