# Architecture Decision Log

This document tracks key technical decisions taken during the build,
their rationale, and trade-offs accepted.

---

## ADR-001 — Databricks Free Edition over Community Edition

**Date:** 2026-05-01
**Status:** Accepted

### Context

The original project brief assumed Databricks Community Edition for development
and a 14-day Databricks-on-GCP trial for the end-to-end GCS integration.
Community Edition has been deprecated in favour of Databricks Free Edition,
a serverless-only, quota-limited environment with no time limit.

### Decision

Use Databricks Free Edition as the primary development environment.
Defer the Databricks-on-GCP trial activation to the final phase of the project
(architecture diagram + Loom recording), when the GCS → Databricks → BigQuery
end-to-end flow is being demonstrated.

### Consequences

**Positive**
- No 14-day countdown pressure during development.
- Identical Spark + Delta Lake + Unity Catalog feature surface as production.
- Zero risk of incurring cloud costs during the build phase.

**Negative / accepted trade-offs**
- Free Edition is serverless-only — the JVM SparkContext is not accessible
  (`spark.sparkContext.uiWebUrl` and similar low-level introspection blocked).
  Mitigated by relying on Spark UI surfaced through the workspace UI and
  high-level DataFrame API only.
- Cannot mount external GCS buckets in Free Edition. The end-to-end GCS
  integration will be validated on a short-lived Databricks-on-GCP trial
  workspace at the recording stage.

---

## ADR-002 — Airflow logs on Docker volume, not bind mount

**Date:** 2026-05-01
**Status:** Accepted

### Context

Running Apache Airflow 2.10 inside Docker on WSL2 (Windows host) caused
persistent `PermissionError` writing scheduler logs when `./logs` was bind-mounted
from the host filesystem. The Airflow image creates subdirectories as different
UIDs during init vs runtime; WSL2's UID/GID translation does not honour the
group-write contract that the official image relies on.

### Decision

Replace the bind mount for `logs/` and `plugins/` with named Docker volumes
(`airflow-logs`, `airflow-plugins`) plus a sidecar `permissions-fix` service
that runs as root before init and chowns/chmods the volume contents to the
Airflow runtime UID/GID.

### Consequences

**Positive**
- Stable Airflow startup on WSL2.
- No host-side permission churn — volume is fully managed by Docker.

**Negative / accepted trade-offs**
- Logs are no longer directly browsable from the host filesystem; they must be
  inspected via the Airflow UI or via `docker compose exec airflow-scheduler bash`.
  Acceptable: the UI is the canonical place to inspect task logs anyway.
- Resetting the environment requires `docker compose down -v` to also wipe
  the logs volume, which is a slightly heavier reset than deleting a folder.

---

## ADR-003 — Terraform service account with least-privilege roles

**Date:** 2026-05-02
**Status:** Accepted

### Context

Terraform needs GCP credentials to provision resources. Two options:
(a) use the developer's user credentials (Application Default Credentials), or
(b) create a dedicated service account with explicit roles.

### Decision

Create a dedicated `terraform-sa` service account with three roles:
- `roles/storage.admin` — create and manage GCS buckets
- `roles/bigquery.admin` — create and manage BigQuery datasets and tables
- `roles/iam.serviceAccountUser` — required for some Terraform-driven IAM operations

The JSON key is stored at `~/.config/gcloud-keys/terraform-sa-jjs-project-1.json`,
**outside the repository**, with file permissions `600` (read/write only for the owner).
The repo's `.gitignore` blocks any `*sa.json` and `*-key.json` patterns as defence-in-depth.

### Consequences

**Positive**
- Principle of least privilege: Terraform cannot escalate beyond storage and BigQuery.
- Reproducible: any future CI/CD pipeline mounts the same key with the same scope.
- Auditable: GCP audit logs distinguish human actions from Terraform actions.

**Negative / accepted trade-offs**
- The JSON key is a long-lived credential. Best practice would be to rotate it
  every 90 days or use Workload Identity Federation. For a portfolio project
  on a personal laptop with budget alerts, this is acceptable; it would not be
  in a production setting.
- Local-only: anyone cloning the repo must create their own service account
  and key. Documented in the README.

---

## ADR-004 — GCS bucket layout: layered + Hive-style partitioning

**Date:** 2026-05-13
**Status:** Accepted

### Context

The GCS data lake needs a directory layout that:
(a) separates medallion layers (Bronze, Silver, Gold),
(b) supports partition pruning by Spark, BigQuery external tables, and Delta Lake,
(c) scales to multiple taxi types and multiple years of data,
(d) preserves traceability to the original source filenames.

### Decision

Adopt a layered + Hive-style partitioning scheme:

    gs://<bucket>/<layer>/<dataset>/year=YYYY/month=MM/<file>

Where:

- `<layer>` is one of `bronze`, `silver`, `gold`.
- `<dataset>` identifies the source (e.g., `yellow_taxi`, `green_taxi`).
- `year=YYYY/month=MM` are Hive-style partition columns that Spark/BigQuery
  recognise automatically for partition pruning.
- File names in Bronze preserve the original source filename for traceability.
- File names in Silver/Gold follow Spark/Databricks defaults
  (such as `part-*.snappy.parquet` for plain Parquet, or `_delta_log/`
  metadata for Delta Lake).

### Consequences

**Positive**

- Engine-friendly: Spark, BigQuery external tables, and Delta Lake all
  recognise Hive partitioning natively.
- Predicate pushdown on year/month filters works without code.
- Layer separation enables per-layer IAM policies and lifecycle rules
  if needed later.
- Adding a new taxi type (e.g. `green_taxi`) does not change the layout.

**Negative / accepted trade-offs**

- The layout is opinionated. If the project later needs streaming ingest
  (where micro-batches do not align to monthly partitions), the layout
  would need extension (e.g., adding `day=DD` or `hour=HH`).
- No ingestion timestamp in the path. Audit trail of "when was each
  partition ingested" lives in Airflow logs and (later) a metadata table,
  not in the path itself. Acceptable for a batch portfolio project.

---

## ADR-005 — Use `gcloud storage` subprocess for GCS uploads instead of google-cloud-storage Python client

**Date:** 2026-05-18
**Status:** Accepted

### Context

The `ingest_to_gcs.py` script initially used the `google-cloud-storage` Python
client (v2.18.2) for all interactions with GCS. Under WSL2, every metadata
operation against `storage.googleapis.com` (e.g., `blob.exists()`,
`blob.reload()`) consistently hung until timeout, even after:

- Forcing IPv4 resolution via `socket.getaddrinfo` monkey-patch
- Setting explicit short timeouts (30s) and retry policies
- Verifying with curl that the same endpoint responds in under 2 seconds
- Verifying that `gcloud storage` commands complete in seconds

Network diagnostics (DNS, ping, TLS handshake, HTTP/2 negotiation) all
succeeded. The root cause appears to be a hang in the requests/urllib3 layer
that the Python client uses, specific to WSL2; the issue could not be
reproduced from native Linux or from inside Docker.

### Decision

Replace direct use of `google-cloud-storage` in the ingestor with
`subprocess` calls to the `gcloud storage` CLI:

- `gcloud storage cp <local> <gs://...>` for upload
- `gcloud storage objects describe <gs://...> --format=json` for metadata
- All MD5 and size verification logic is preserved

The script remains idempotent and produces identical observable outcomes.

### Consequences

**Positive**
- Works reliably on the current WSL2 dev environment.
- `gcloud storage` is well-maintained, supports resumable uploads natively,
  and benefits from Google's own transport optimisations (parallel composite
  uploads for large files).
- Reduces a Python dependency surface — the script's only required
  external dependency is the gcloud CLI, which the project already requires.

**Negative / accepted trade-offs**
- Adds a binary dependency: `gcloud` must be installed on the host running
  the ingestor. In Cloud Composer or Cloud Run this is already true. In
  any future CI/CD runner, the runner must install gcloud.
- Subprocess overhead per operation (~200ms per gcloud invocation) is
  negligible at our scale (hundreds of monthly partitions) but would be
  unacceptable for thousands of small files. If the project ever ingests
  many small objects per run, revisit and either move to a Spark-based
  ingestor or revisit the Python client (potentially from a different
  environment).
- Loss of streaming/in-memory upload capability — we can no longer upload
  a Python in-memory buffer; we must always go through a local file. Not
  currently a constraint.
