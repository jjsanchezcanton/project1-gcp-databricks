# Claude Code context for Project 1 — GCP + Databricks Pipeline

## Project summary

End-to-end batch data pipeline on NYC TLC Yellow Taxi data.
Architecture: GCS (Bronze, raw) → Databricks Delta Lake (Silver, cleaned)
→ Databricks Delta Lake + BigQuery external tables (Gold, aggregated)
→ Looker Studio dashboard.

Orchestrated by Apache Airflow running locally in Docker.
Infrastructure provisioned by Terraform.
Author: Juan-Jose Sanchez (portfolio project, Day 4 of 12).

## Important files to consult before any change

- `docs/decisions.md` — Architecture Decision Records (ADR-001 through ADR-007).
  Every design decision in the project lives here. Always read before
  implementing transformations or changing infrastructure.
- `ingestion/ingest_to_gcs.py` — production-style ingestor pattern to follow.
- `terraform/main.tf` — the canonical names of buckets, datasets, resources.
- `README.md` — project status and structure.

## Conventions

- Python: 3.11, type hints required on function signatures, docstrings on all
  public functions, snake_case throughout.
- Logging: use the `logging` module, never bare `print()` in production code
  (notebooks for exploratory display are an exception).
- GCS paths: `gs://<bucket>/<layer>/<dataset>/year=YYYY/month=MM/<file>`.
- Databricks Volumes paths during development:
  `/Volumes/workspace/default/project1_<layer>/<dataset>/...`
- Delta tables registered in Unity Catalog as
  `workspace.default.<layer>_<dataset>` (e.g. `silver_yellow_taxi`).
- Errors: prefer `raise RuntimeError(<descriptive>)` over generic `Exception`.

## What NOT to do

- Do not commit `terraform.tfvars`, service account JSON keys, `.env`, or
  any data file (`data/` is gitignored).
- Do not invent column names or table schemas — refer to ADR-007 and to
  the existing Bronze parquet schema.
- Do not use the `google-cloud-storage` Python client for GCS uploads in
  this environment (see ADR-005); use `gcloud storage` subprocess instead.
- Do not execute `terraform apply` or modify infrastructure without explicit
  confirmation. Read-only inspection (`terraform plan`) is fine.

## Current focus (Day 4)

Implement the Silver layer transformation for Yellow Taxi following
ADR-007. Output is a Databricks notebook (Python source format) that runs
in Databricks Free Edition with serverless compute.
