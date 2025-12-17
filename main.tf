terraform {
  required_version = ">= 1.0"
  backend "gcs" {
  }
}

variable "project_id" {}
variable "region" {}
variable "infra_bucket" {}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_cloudfunctions2_function" "function" {
  name     = "fable-facet-user"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "main" 
    source {
      storage_source {
        bucket = var.infra_bucket
        object = "source/fablefacet.zip"
      }
    }
  }
  service_config {
    max_instance_count = 1
    available_memory   = "256Mi"
  }
}

resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  service  = google_cloudfunctions2_function.function.name 

  role   = "roles/run.invoker"
  member = "allUsers"
}
