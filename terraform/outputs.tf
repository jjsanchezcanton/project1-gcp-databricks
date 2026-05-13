output "gcs_bucket_name" {
  description = "Name of the GCS data lake bucket."
  value       = google_storage_bucket.data_lake.name
}

output "gcs_bucket_url" {
  description = "gs:// URL of the bucket — use for gsutil/gcloud storage commands."
  value       = google_storage_bucket.data_lake.url
}

output "gcs_bucket_console_url" {
  description = "Web console URL of the bucket."
  value       = "https://console.cloud.google.com/storage/browser/${google_storage_bucket.data_lake.name}"
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID."
  value       = google_bigquery_dataset.analytics.dataset_id
}

output "bigquery_dataset_console_url" {
  description = "Web console URL of the BigQuery dataset."
  value       = "https://console.cloud.google.com/bigquery?project=${var.project_id}&d=${google_bigquery_dataset.analytics.dataset_id}"
}
