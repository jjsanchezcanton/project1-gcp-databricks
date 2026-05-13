# ============================================================
# GCS bucket — Bronze landing zone for NYC TLC raw data
# ============================================================
resource "google_storage_bucket" "data_lake" {
  name     = var.gcs_bucket_name
  location = var.region

  # Standard storage — appropriate for active development data.
  storage_class = "STANDARD"

  # Uniform bucket-level access disables ACLs in favour of IAM-only.
  # Recommended best practice for new buckets.
  uniform_bucket_level_access = true

  # Public access prevention: enforced (no public reads/writes possible).
  public_access_prevention = "enforced"

  # Versioning off for the Bronze landing zone — raw data is reproducible
  # from source. Versioning would double storage cost without real benefit here.
  versioning {
    enabled = false
  }

  # Lifecycle: auto-delete objects older than 90 days to keep cost bounded.
  # Re-ingest from public dataset if needed.
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = var.labels
}

# ============================================================
# BigQuery dataset — Gold layer + external tables over GCS
# ============================================================
resource "google_bigquery_dataset" "analytics" {
  dataset_id  = var.bigquery_dataset_id
  location    = var.bigquery_location
  description = "Analytics layer for NYC TLC pipeline. External tables read from GCS Gold; native tables hold curated aggregates."

  # Default table expiration: 30 days. Forces explicit thinking about which
  # tables are meant to be permanent vs experimental.
  default_table_expiration_ms = 30 * 24 * 60 * 60 * 1000  # 30 days in ms

  # Delete contents on dataset destroy — important for a portfolio project
  # where teardown should be clean. NEVER set this to true in production.
  delete_contents_on_destroy = true

  labels = var.labels
}
