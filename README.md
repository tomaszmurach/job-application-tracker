# Job Application Tracker

## 1. Project overview

An asynchronous REST API for tracking job applications, built with FastAPI,
SQLAlchemy, and Alembic. It demonstrates validation, partial updates, database
migrations, container packaging, automated testing, and a manually operated Azure
deployment. This is a learning/portfolio project using synthetic, disposable data.

CI validates changes and publishes images. Azure deployment and migrations remain
manual. The [operations runbook](docs/operations.md) covers release ordering and
troubleshooting.

## 2. Live demo

**Swagger UI:** https://job-tracker-api.blackmeadow-6e76cb9e.westeurope.azurecontainerapps.io/docs

The API is deployed on Azure Container Apps with PostgreSQL Flexible Server.
The environment is intended for portfolio/demo use only. CRUD endpoints are
intentionally unauthenticated, so only synthetic or disposable data should be used.

## 3. Architecture and stack

Requests flow from FastAPI through an async SQLAlchemy session to PostgreSQL in
container/deployed environments, or SQLite for lightweight local development.
Alembic owns the schema; API startup does **not** create tables or run migrations.

| Component | Technology / responsibility |
| --- | --- |
| Runtime | Python 3.13, FastAPI, Uvicorn |
| Validation / configuration | Pydantic, pydantic-settings, required `DATABASE_URL` |
| Persistence | SQLAlchemy 2.x async ORM; asyncpg for PostgreSQL, aiosqlite for SQLite |
| Schema | Alembic, using the same database configuration as the API |
| Tests | pytest, pytest-asyncio, HTTPX; SQLite and focused PostgreSQL 17 regression |
| Packaging | Docker; Compose API + PostgreSQL development environment |
| CI / registry | GitHub Actions and GitHub Container Registry (GHCR) |
| Deployment examples | Local kind Kubernetes; Terraform-managed Azure Container Apps and PostgreSQL Flexible Server |

Direct dependency versions are pinned in [requirements.txt](requirements.txt) and
[requirements-dev.txt](requirements-dev.txt). Request schemas are separate from
ORM models; database-backed requests use their own async sessions.

## 4. API endpoints

| Method | Path | Behavior | Success |
| --- | --- | --- | --- |
| GET | `/health` | Process/liveness check, independent of the database | 200 |
| GET | `/ready` | Bounded database connectivity check | 200; 503 on failure |
| POST | `/applications` | Create an application | 201 |
| GET | `/applications` | List applications; optional `status` filter | 200 |
| GET | `/applications/{id}` | Retrieve one application | 200 |
| PATCH | `/applications/{id}` | Update supplied fields | 200 |
| DELETE | `/applications/{id}` | Delete an application | 204, empty body |

Missing applications return 404; invalid request data returns 422. An empty
collection returns `[]`. Listing has no pagination or guaranteed ordering.
Interactive documentation is available at `/docs`.

Example create request, also usable through **Try it out** in `/docs`:

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

Responses include an integer `id` and `applied_at`. Filter with
`GET /applications?status=Interview`.

- `company` and `position`: required on creation, 1–100 characters after trimming
  surrounding whitespace; blank values are rejected.
- `status`: `Applied`, `Interview`, `Offer`, or `Rejected` (case-sensitive).
- `notes`: optional, nullable, at most 500 characters; formatting is preserved.
- `applied_at`: non-null database-generated `CURRENT_TIMESTAMP`, representing
  creation in this tracker, not a user-entered historical application date.
  Updates preserve it. The API serializes a timestamp without a timezone suffix;
  SQLite supplies UTC, while PostgreSQL's timezone-naive column depends on the
  session timezone when the default is evaluated.

PATCH uses only explicitly supplied fields:

| Request body | Effect |
| --- | --- |
| `{"status": "Interview"}` | Change status; preserve other fields |
| `{"notes": null}` | Clear notes |
| `{"company": null}` | Reject with 422; likewise for position and status |
| `{}` | Leave the record unchanged |

## 5. Local quick start

Clone the repository and enter its root:

```sh
git clone https://github.com/tomaszmurach/job-application-tracker.git
cd job-application-tracker
```

Create a Python 3.13 virtual environment and copy the local configuration.

**Windows PowerShell:**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

**macOS / Linux (Bash):**

```sh
python3.13 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

The example selects SQLite:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./applications.db
```

`DATABASE_URL` is required. Environment variables override `.env`; both the API
and Alembic use this setting. Run from the repository root because `.env` and the
SQLite path are relative to the working directory. Remove any previously exported
remote `DATABASE_URL` before using this local example.

```sh
python -m pip install -r requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn main:app --reload
```

Use `requirements.txt` for runtime-only dependencies. Open
[API docs](http://127.0.0.1:8000/docs),
[health](http://127.0.0.1:8000/health), and
[readiness](http://127.0.0.1:8000/ready).

Inspect the configured database's migration state with:

```sh
python -m alembic current
python -m alembic history
python -m alembic check
```

For model changes, generate a revision with
`python -m alembic revision --autogenerate -m "Describe the schema change"`, review
its operations, upgrade the local database, and run tests. Use connected
migrations: SQLite batch recreation requires database reflection. The `applied_at`
migration uses batch recreation on SQLite and native column alterations on
PostgreSQL to preserve the existing ID sequence.

## 6. Tests

With development dependencies installed:

```sh
python -m pytest -q
python -m pytest -q tests/test_migrations.py
```

The suite currently collects **33 tests**: the default local run executes 32 and
skips the PostgreSQL regression. HTTP tests use isolated temporary SQLite
databases and cover CRUD, filtering, validation, PATCH semantics, timestamps,
and readiness failures/timeouts. The fast SQLite migration test upgrades an empty
database to head. Test configuration does not require a developer's database.

Enable the PostgreSQL regression with Docker running:

**PowerShell:**

```powershell
$env:RUN_POSTGRES_TESTS = "1"
try { python -m pytest -q } finally { Remove-Item Env:\RUN_POSTGRES_TESTS }
```

**Bash:**

```sh
RUN_POSTGRES_TESTS=1 python -m pytest -q
```

All 33 tests run when enabled; CI enables this automatically. To run only this
regression, use `tests/test_postgres_migrations.py` with the same environment
variable. It starts isolated PostgreSQL 17 in Docker on a random loopback port,
populates IDs at the initial revision, upgrades to head, and checks preserved
rows, sequence/table identity, a new generated ID above existing IDs, and
`applied_at` default/nullability. It also checks downgrade/re-upgrade and removes
its container in fixture cleanup. It never targets Azure.

## 7. Docker Compose

The [Dockerfile](Dockerfile) installs dependencies in a cached layer, explicitly
copies runtime files, and runs as the non-root `app` user. The restrictive
[.dockerignore](.dockerignore) allows only build/runtime inputs: infrastructure,
tests, local environment files, and state stay outside the build context. A new
runtime module may require updating both allowlists. API and Alembic use the same
image.

[compose.yaml](compose.yaml) provides the API and PostgreSQL 17 with disposable
local development credentials and a persistent `postgres_data` volume. PostgreSQL
has no published host port; the API publishes port 8000 on the host. Run each step
only after the preceding step succeeds:

```sh
docker compose build api
docker compose up -d --wait db
docker compose run --rm api alembic upgrade head
docker compose up -d api
```

Then use the same local `/docs`, `/health`, and `/ready` URLs. Database health
gates container startup, but Compose does not run migrations automatically.
For an updated image, repeat the build → migration → API sequence.

```sh
docker compose logs --tail=100 api db
docker compose down
```

`down` preserves data; `docker compose down --volumes` also deletes the local
database volume. Use disposable data, and stop another local API before binding
the same port.

## 8. CI and GHCR image publishing

[GitHub Actions](.github/workflows/ci.yml) validates pushes to `main`, pull requests
targeting `main`, and manual workflow runs. Validation installs Python 3.13
dependencies, runs pytest with `RUN_POSTGRES_TESTS=1`, validates Compose, and builds
the Docker image.

After successful validation, **only a push to `main`** publishes:

```text
ghcr.io/tomaszmurach/job-application-tracker:latest
ghcr.io/tomaszmurach/job-application-tracker:<full-commit-SHA>
```

`packages: write` is scoped to the publish job. Deployments use the commit-SHA tag
as an immutable release reference; do not overwrite it. `latest` is a moving tag.
CI does not run Terraform, deploy Azure resources, or execute deployed migrations.
Current deployment definitions assume the GHCR image is publicly pullable; they
do not configure private-registry credentials.

## 9. Kubernetes

The [k8s/](k8s/) manifests are a local, kind-oriented deployment example:

- `namespace.yaml`: the `job-tracker` namespace.
- `postgres.yaml`: PostgreSQL 17 StatefulSet, headless Service, and a 1 GiB PVC.
- `migration-job.yaml`: fixed-name `database-migration` Job running Alembic.
- `api.yaml`: two API replicas, Service, resource limits, `/health` liveness and
  `/ready` readiness probes.
- `ingress.yaml`: optional HTTP ingress using class `cloud-provider-kind`.

The API and migration Job pin the same commit-SHA image. Supply the
`job-tracker-db` Secret separately, start PostgreSQL, run and verify the migration
Job, then apply the API Deployment. A completed fixed-name Job does not rerun
merely because a new release exists: explicitly delete/recreate it when no
migration is active. Follow the [Kubernetes runbook](docs/operations.md#local-kubernetes)
instead of applying the entire directory without migration ordering.

## 10. Terraform / Azure architecture

[terraform/](terraform/) manages a workload Resource Group, Container Apps
environment, HTTPS API Container App, PostgreSQL 17 Flexible Server/database,
narrow firewall rule, and a manually triggered Container Apps migration Job.
The API uses Single revision mode and scales between zero and one replica.

Both API and migration Job use `container_image` and the same `database-url`
secret value as `DATABASE_URL`. Terraform generates the administrator password;
PostgreSQL receives the raw value, while only the password component of the
SQLAlchemy URL is encoded with `urlencode(...)`. This preserves URL-significant
characters without changing the password. Azure connections retain `?ssl=require`.

Explicit API probes use `/health` for startup/liveness and `/ready` for readiness.
The `container_app_fqdn` output is the stable application ingress hostname, not a
revision-specific hostname.

Remote state lives in Azure Blob Storage. Before `terraform init`, install
Terraform **1.16.0 or newer**, authenticate Azure CLI, and ensure the backend
Resource Group, Storage Account, and Blob Container already exist. They are
bootstrap resources managed separately from this workload. Configure the backend
in [providers.tf](terraform/providers.tf) for your environment and grant suitable
blob data access (including state locking), plus workload management permissions.
Resource provider registration is disabled in the provider configuration;
required Azure providers must already be registered.

State contains sensitive values. Restrict backend access; keep state, saved plans,
and credentials out of documentation and version control. See the
[backend prerequisites](docs/operations.md#azure-prerequisites) and
[Azure Blob backend reference](https://developer.hashicorp.com/terraform/language/backend/azurerm).

## 11. Azure deployment and migration workflow

For an existing environment, the intended manual release order is:

1. Let CI validate and publish the full commit-SHA image.
2. Update `container_image` in `terraform/terraform.tfvars` to that image and
   review the Terraform plan.
3. Run the migration Job with that release image and verify execution **Succeeded**.
4. Apply the reviewed Terraform configuration to roll out the API and persist the
   matching migration Job image.
5. Check `/health`.
6. Check `/ready`, then verify expected API/schema behavior.
7. Inspect revisions and logs if anything fails.

The [Azure runbook](docs/operations.md#azure-release-and-migrations) shows a complete
execution-only job override so new migrations can run before the API update.
Terraform itself does not execute the Job or enforce this order.

**First deployment exception:** the initial Terraform apply creates both API and
Job. The API can become reachable before the first migration; do not treat the
deployment as usable until migration succeeds and verification completes. There
is no automatic first-deployment schema gate in this configuration.

**Readiness checks database connectivity, not the Alembic revision or pending
migrations. Migration ordering remains an operator responsibility.**

## 12. Health and readiness semantics

| Endpoint | Implementation | Meaning |
| --- | --- | --- |
| `/health` | Returns `{"status":"ok"}` without database I/O | The process can serve this route |
| `/ready` | Acquires a connection and executes `SELECT 1` within a 0.8-second timeout | Database connectivity succeeded |

Readiness succeeds with `{"status":"ready"}` and returns 503 with
`{"detail":"Database unavailable"}` on connection/query failure or timeout.
A database outage can leave `/health` at 200 while `/ready` is 503. Readiness does
not check table existence, schema compatibility, or whether migrations ran.
Azure probe timeouts are two seconds, longer than the application's readiness
timeout. Cold starts can delay the first response when the app scales to zero.

## 13. Observability and troubleshooting

Use Container Apps execution status, revision state, and console/system logs;
see [diagnostic commands](docs/operations.md#azure-diagnostics-and-recovery).
The repository does not provision a dedicated Log Analytics workspace or an
application tracing/metrics stack.

Manual deployment exercises have included:

- Inspecting revisions and logs, including scale-to-zero/cold-start behavior.
- A database firewall failure where `/health` remained 200 and `/ready` returned
  503, distinguishing a running process from database access.
- Detecting Terraform drift and recovering through reviewed configuration/plan
  reconciliation.
- An invalid-image deployment attempt where the previously healthy revision
  remained available. This observation is not a general availability guarantee.
- Starting the migration Job manually and checking execution status.

If migrations fail, inspect their execution before rolling out the API. If an
image fails to start, inspect provisioning and pull errors before retrying. An
image rollback does not undo database migrations.

## 14. Known limitations and trade-offs

- This is a portfolio deployment, not an enterprise production platform.
- CRUD endpoints are unauthenticated. Use synthetic/disposable data; there is no
  user isolation or access-control layer.
- PostgreSQL uses a public endpoint with a narrow rule for an observed Container
  Apps outbound IP. That IP can change; the setup is operationally brittle.
  No NAT Gateway, VNet integration, or private database networking was added.
- The application currently uses PostgreSQL administrator credentials. Production
  systems should use a narrower application-specific role and appropriate
  migration permissions.
- Migration execution and release ordering are manual. Schema-incompatible
  changes require additional coordination with the running API.
- Azure scales to zero, has at most one API replica, and can incur cold starts.
  Availability, backup restoration, and disaster recovery are not demonstrated by
  passing probes or the failed-image exercise.
- Kubernetes manifests are educational/local, not an automated production
  deployment system. The optional ingress has no TLS configuration.
- SQLite keeps local setup fast but differs from PostgreSQL in concurrency and
  migrations; the focused regression is not a duplicate PostgreSQL API suite.

## 15. Terraform teardown

From the repository root, with the intended Azure account/backend selected:

```sh
terraform -chdir=terraform plan -destroy
terraform -chdir=terraform destroy
```

Review the proposed destruction and confirmation prompt. This removes the managed
workload infrastructure, including PostgreSQL and its data; export any data you
need beforehand. Backend bootstrap resources are separate and are not removed by
this workload configuration. Do not delete them while state still needs to be
retained or used for cleanup.

## 16. Repository structure

```text
.
|-- main.py                 # FastAPI composition, lifespan, health/readiness
|-- config.py               # Required database configuration
|-- database.py             # Async engine, sessions, declarative base
|-- models.py               # SQLAlchemy application model
|-- schemas.py              # Request/response validation
|-- routers/applications.py # CRUD and filtering
|-- alembic.ini
|-- alembic/                # Async migration environment and revisions
|-- tests/
|   |-- conftest.py
|   |-- test_applications.py
|   |-- test_migrations.py
|   `-- test_postgres_migrations.py
|-- Dockerfile
|-- .dockerignore           # Build-context allowlist
|-- compose.yaml
|-- .github/workflows/ci.yml
|-- k8s/                    # Local Kubernetes manifests
|-- terraform/              # Azure workload and remote backend configuration
|-- docs/operations.md      # Manual deployment and recovery runbook
|-- .env.example
|-- requirements.txt
`-- requirements-dev.txt
```
