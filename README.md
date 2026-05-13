# Project 1 — GCP + Databricks Retail/Taxi Analytics Pipeline

End-to-end batch data pipeline on GCP using NYC TLC trip data.
Medallion architecture (Bronze/Silver/Gold) on Delta Lake, orchestrated with Airflow,
served through BigQuery and visualised in Looker Studio.

## Status

🚧 In progress — Day 2 / Week 1 of build.

**Done so far:**

- Local dev environment: WSL2 + Docker + Python 3.11 + Terraform + gcloud CLI + Claude Code
- Apache Airflow 2.10 running locally on Docker, `hello_world` DAG executed
- Databricks Free Edition workspace provisioned and Delta Lake validated
- GCP project `jjs-project-1-de-portfolio` created, billing linked, budget alerts at $5/$20/$50
- 7 GCP APIs enabled (Cloud Storage, BigQuery, IAM, IAM Credentials, Cloud Resource Manager, Service Usage, BigQuery Storage)
- Terraform-managed infrastructure: GCS data lake bucket + BigQuery dataset, least-privilege service account
- Python smoke test: round-trip upload/download to GCS via the Terraform service account

## Stack

- **Cloud:** GCP (GCS, BigQuery)
- **Lakehouse:** Databricks Free Edition + Delta Lake (Databricks-on-GCP trial reserved for end-to-end recording)
- **Orchestration:** Apache Airflow 2.10 (local, Docker)
- **IaC:** Terraform (Google provider 5.x)
- **Data Quality:** Great Expectations (to be added)
- **Languages:** Python 3.11 (PySpark), SQL
- **BI:** Looker Studio

## Architecture

(diagram coming — see `/diagrams/architecture.png`)

## Repository structure
.
├── airflow/              # Local Airflow setup (docker-compose + DAGs)
├── databricks/           # Databricks notebooks and job definitions
├── data_quality/         # Great Expectations checks
├── diagrams/             # Architecture diagrams
├── docs/                 # ADRs and design notes
├── ingestion/            # Python ingestion scripts
├── sql/                  # BigQuery views and analytical queries
└── terraform/            # IaC for GCP resources

## How to run (so far)

### Prerequisites

- WSL2 Ubuntu 22.04 (or any Linux), Docker, Python 3.11, Terraform 1.5+, gcloud CLI
- A GCP project with billing enabled
- A service account JSON key with `roles/storage.admin`, `roles/bigquery.admin`, `roles/iam.serviceAccountUser`,
  stored at `~/.config/gcloud-keys/terraform-sa-<project>.json`

### Provision GCP infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # then edit with your project values
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcloud-keys/terraform-sa-<project>.json"
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### Run the GCS smoke test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ingestion/smoke_test_gcs.py
```

### Start local Airflow

```bash
cd airflow
docker compose up airflow-init   # first run only
docker compose up -d
# UI at http://localhost:8080  (admin / admin)
```

## Trade-offs and architecture decisions

See `docs/decisions.md` for the architecture decision log.

---

Author: Juan-Jose Sanchez · [LinkedIn](https://www.linkedin.com/in/juan-jose-sanchez-6185328/)
