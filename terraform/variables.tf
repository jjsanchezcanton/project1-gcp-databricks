variable "project_id" {
  description = "GCP project ID where resources will be created."
  type        = string
}

variable "region" {
  description = "Default GCP region for regional resources."
  type        = string
  default     = "europe-west2"
}

variable "gcs_bucket_name" {
  description = "Globally unique name for the GCS bucket holding NYC TLC data."
  type        = string
}

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for analytics tables (Gold layer + external tables)."
  type        = string
  default     = "nyc_tlc_analytics"
}

variable "bigquery_location" {
  description = "Multi-region location for the BigQuery dataset (EU or US)."
  type        = string
  default     = "EU"
}

variable "labels" {
  description = "Common labels applied to all resources for cost tracking."
  type        = map(string)
  default = {
    project     = "project1-portfolio"
    owner       = "jjs"
    environment = "dev"
    managed_by  = "terraform"
  }
}
