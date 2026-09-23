# Operations runbook

Commands run from the repository root. Azure examples use PowerShell. Replace
placeholders and select the intended environment before running commands. Stop
after any failed step; do not continue to an API rollout after a failed migration.
These are manual procedures, not CI deployment automation.

## Local Kubernetes

Prerequisites: Docker, kind, kubectl, a working local cluster, and a default
StorageClass capable of provisioning the PostgreSQL PVC. For a new demo cluster:

```sh
kind create cluster --name job-tracker
kubectl config use-context kind-job-tracker
kubectl config current-context
kubectl get storageclass
kubectl apply -f k8s/namespace.yaml
```

If a cluster already exists, select and verify its context instead of creating
another. Create a local `.env.k8s` file with these four keys and your own disposable
values (do not commit or print them):

| Key | Requirement |
| --- | --- |
| `POSTGRES_DB` | Database to initialize |
| `POSTGRES_USER` | PostgreSQL user to initialize |
| `POSTGRES_PASSWORD` | Raw local database password |
| `DATABASE_URL` | SQLAlchemy `postgresql+asyncpg` URL for those credentials, host `postgres`, port `5432`, and the same database |

Percent-encode the password component when constructing the URL, retaining the
raw password in `POSTGRES_PASSWORD`. `.env.k8s` is Git-ignored and excluded from
the image build context. Create the Secret and start PostgreSQL:

```sh
kubectl -n job-tracker create secret generic job-tracker-db --from-env-file=.env.k8s
kubectl apply -f k8s/postgres.yaml
kubectl -n job-tracker rollout status statefulset/postgres --timeout=180s
```

Secret creation above is a first-time step. Replacing a Secret does not change
credentials already initialized in a persistent PostgreSQL volume; credential
rotation requires a separate, coordinated procedure.

For each release, set the **same published full commit-SHA image** in
`k8s/migration-job.yaml` and `k8s/api.yaml`. The committed pins need not match the
latest repository HEAD. Ensure no migration is running before deleting the old
fixed-name Job:

```sh
kubectl -n job-tracker get jobs
kubectl -n job-tracker delete job database-migration --ignore-not-found
kubectl apply -f k8s/migration-job.yaml
kubectl -n job-tracker wait --for=condition=complete job/database-migration --timeout=300s
kubectl -n job-tracker logs job/database-migration
```

If the wait fails or times out, inspect
`kubectl -n job-tracker describe job database-migration` and its pods/logs. A timeout
alone does not mean the Job has stopped. Resolve the failure before proceeding.
Once the Job completes:

```sh
kubectl apply -f k8s/api.yaml
kubectl -n job-tracker rollout status deployment/api --timeout=180s
kubectl -n job-tracker get pods
kubectl -n job-tracker port-forward service/api 8000:80
```

Keep port forwarding running and check
[health](http://127.0.0.1:8000/health),
[readiness](http://127.0.0.1:8000/ready), and
[API docs](http://127.0.0.1:8000/docs) from another terminal/browser.

Ingress is optional. `k8s/ingress.yaml` requires a running Cloud Provider KIND
supporting ingress class `cloud-provider-kind`; follow the
[kind ingress guide](https://kind.sigs.k8s.io/docs/user/ingress/), then apply
`kubectl apply -f k8s/ingress.yaml`. It exposes HTTP without configured TLS.

To remove this disposable cluster and its local database data:

```sh
kind delete cluster --name job-tracker
```

## Azure prerequisites

- Install Terraform 1.16.0 or newer and Azure CLI with Container Apps commands.
- Authenticate to the intended subscription and configure the provider's
  subscription environment variable locally. Do not put its value in source.
- Precreate the backend Resource Group, Storage Account, and Blob Container
  separately. Align `terraform/providers.tf` with that backend before initializing.
  This workload configuration cannot bootstrap its own backend.
- Grant backend blob data permissions, such as Storage Blob Data Contributor at
  an appropriate scope, as well as workload management permissions. Backend
  authentication uses Azure CLI / Microsoft Entra ID. See the
  [Azure Blob backend documentation](https://developer.hashicorp.com/terraform/language/backend/azurerm).
- Have required resource providers registered, including `Microsoft.App` and
  `Microsoft.DBforPostgreSQL`; automatic registration is disabled in this repo.
- Review `terraform/terraform.tfvars` for workload names, region, and published
  image. Globally unique names must be available for a fresh environment.
- Verify the narrow PostgreSQL firewall rule matches the environment's observed
  outbound connectivity. The checked-in observed IP is not a portable guarantee.
  A new environment may need an intentionally reviewed rule update.

```powershell
az login --output none
az account set --subscription "<subscription-name>"
$env:ARM_SUBSCRIPTION_ID = az account show --query id --output tsv
terraform -chdir=terraform init
terraform -chdir=terraform validate
```

State contains credentials even when CLI output marks them sensitive. Do not dump
state, reveal secret values, or commit saved plan files. The following procedures
read only nonsensitive outputs and status fields.

## Azure release and migrations

### Existing environment

Use this procedure for an image release whose migration can run while the old API
is still serving. For incompatible schema changes, plan maintenance/compatibility
steps first. Avoid concurrent releases or overlapping migration executions.

1. Wait for CI validation and GHCR publishing on `main` to succeed. Update
   `container_image` in `terraform/terraform.tfvars` to the published full
   commit-SHA tag. Keep the Kubernetes pins aligned too if releasing that example.
2. Review the proposed Terraform changes before executing anything:

   ```powershell
   terraform -chdir=terraform plan
   ```

   An image-only release should update the API and migration Job image references.
   Investigate unexpected replacements, password changes, or drift. This procedure
   assumes the database, secret, and connectivity configuration already work; an
   infrastructure change may require a separately reviewed sequence.

3. Set release variables. `$Image` must exactly match the new tfvars value; the app
   and Job names below match the checked-in configuration (adjust if customized):

   ```powershell
   $ResourceGroup = terraform -chdir=terraform output -raw resource_group_name
   $App = "job-tracker-api"
   $Job = "job-tracker-db-migration"
   $Image = "ghcr.io/tomaszmurach/job-application-tracker:<full-commit-SHA>"
   ```

4. Start a migration execution using the new release image **before** applying
   the API image change:

   ```powershell
   $Execution = az containerapp job start --name $Job --resource-group $ResourceGroup --container-name migration --image $Image --command alembic --args upgrade head --env-vars DATABASE_URL=secretref:database-url --cpu 0.25 --memory 0.5Gi --query name --output tsv
   if ($LASTEXITCODE -ne 0 -or -not $Execution) { throw "Migration execution did not start" }
   ```

   Execution overrides replace the execution template, so this command supplies
   the current container's command, arguments, secret reference, and resources as
   well as its image. It does not change the saved Job template or expose the
   database URL. Keep these flags aligned if the Terraform Job template changes.
   See [Azure job execution overrides](https://learn.microsoft.com/en-us/azure/container-apps/jobs#start-a-job-execution-on-demand).

5. Starting a Job is not proof it succeeded. Check this execution until it reaches
   a terminal status; rerun the **status command**, not the start command:

   ```powershell
   az containerapp job execution show --name $Job --resource-group $ResourceGroup --job-execution-name $Execution --query properties.status --output tsv
   ```

   Proceed only after `Succeeded`. If `Running`, wait and check again. On failure,
   inspect the Job's execution history and logs in the Azure portal, correct the
   cause, and verify a successful execution before continuing.

6. After migration success, roll out the API and persist the matching Job image:

   ```powershell
   terraform -chdir=terraform plan
   terraform -chdir=terraform apply
   ```

   Recheck the apply-time plan before confirming; no automatic approval flag is
   used. Review revisions and verify endpoints as shown below. Successful
   readiness alone is not proof of schema compatibility.

### First deployment

After prerequisites, review `terraform -chdir=terraform plan`, then run
`terraform -chdir=terraform apply` and review its confirmation. This creates both
API and migration Job; it does **not** execute Alembic. The API revision may become
reachable before the schema exists because readiness only runs `SELECT 1`.

Set `$ResourceGroup`, `$App`, and `$Job` as above, then start the configured Job
without an image override (its saved image must be the intended published SHA):

```powershell
$Execution = az containerapp job start --name $Job --resource-group $ResourceGroup --query name --output tsv
if ($LASTEXITCODE -ne 0 -or -not $Execution) { throw "Migration execution did not start" }
az containerapp job execution show --name $Job --resource-group $ResourceGroup --job-execution-name $Execution --query properties.status --output tsv
```

Wait for `Succeeded` as in the existing-environment procedure. Verify health,
readiness, and expected API behavior before treating the deployment as usable.
An empty-schema API can pass both probes, so migration status is a separate gate.

## Azure diagnostics and recovery

With `$ResourceGroup`, `$App`, and `$Job` set as above, check the stable ingress:

```powershell
$Fqdn = terraform -chdir=terraform output -raw container_app_fqdn
Invoke-RestMethod "https://$Fqdn/health"
Invoke-RestMethod "https://$Fqdn/ready"
```

Expect `status: ok` and `status: ready`. Check `/docs` and intended API behavior
using synthetic data. Scale-to-zero may delay the first request; inspect revision
and startup state before treating a cold start as a database problem.

```powershell
az containerapp revision list --name $App --resource-group $ResourceGroup --all --query "[].{name:name,active:properties.active,health:properties.healthState,provisioning:properties.provisioningState}" --output table
az containerapp logs show --name $App --resource-group $ResourceGroup --type system --tail 100
az containerapp logs show --name $App --resource-group $ResourceGroup --type console --tail 100
az containerapp job execution list --name $Job --resource-group $ResourceGroup --query "[].{name:name,status:properties.status}" --output table
```

Console logs require a running replica; if the app is scaled to zero, request its
ingress and inspect system logs/revision status. Use `--revision <revision-name>`
with the console log command when diagnosing a particular revision. The Azure
portal's Job execution history provides per-execution diagnostics; app logs are
not a substitute for checking migration execution status.

| Symptom | Investigation / next action |
| --- | --- |
| `/health` is 200, `/ready` is 503 | Inspect database availability, firewall/outbound IP, connectivity, and configured secret reference. Do not print secret values. This split occurred during a manual firewall-failure exercise. |
| Probes pass but CRUD fails with missing schema | Verify migration execution and release image. Readiness does not inspect Alembic state or application tables. |
| New revision fails to provision | Inspect image name/tag accessibility, revision state, and system logs. An invalid-image exercise retained the previously healthy revision; do not assume every failure behaves identically. |
| Terraform reports drift | Compare actual changes with intended configuration using `terraform plan`. Either deliberately update configuration or restore it through a reviewed apply. Investigate replacements before approving; do not mask drift with an unreviewed apply. |
| Migration execution fails or times out | Inspect that execution's logs/status and database connectivity. Resolve the cause before starting another execution or rolling out the API. |

For a failed release, assess the schema before selecting a previously healthy
image. Reverting an image does not revert migrations. This repository does not
implement automatic rollback, schema-aware readiness, or a zero-downtime release
guarantee. Earlier drift recovery and failed-image exercises are learning evidence,
not a production availability claim.

## Teardown and retained state

Review `terraform -chdir=terraform plan -destroy`, then use
`terraform -chdir=terraform destroy` only when workload and database data are no
longer needed. Separate backend bootstrap resources must remain available while
Terraform still needs state for cleanup or retention. Remove them only as a
separate, deliberate action after workload teardown and state-retention needs
have been resolved.
