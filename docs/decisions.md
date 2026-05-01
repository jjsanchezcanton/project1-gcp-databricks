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
