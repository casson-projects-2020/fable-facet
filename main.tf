terraform {
  required_version = ">= 1.0"
  backend "gcs" {
  }
}

variable "project_id"   {}
variable "region"       { default = "us-central1" }
variable "infra_bucket" {}

variable "central_url" {
  description = "URL da Cloud Function Central que processa os registros"
  type        = string
}

data "google_client_openid_userinfo" "me" {}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  sub           = data.google_client_openid_userinfo.me.sub 
  sub_hash      = substr( sha256("${local.sub}"), 0, 10 )
  cf_name       = "ffacet-user-${local.sub_hash}"
  central_api   = "https://api.fablefacet.com/register"
}

locals {
  services = [
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "run.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com", # Esta é a API da Vertex AI / Gemini
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.services)
  project  = var.project_id
  service  = each.key

  disable_on_destroy = false
}

data "google_project" "target" {
  project_id = var.project_id
}

resource "google_project_iam_member" "gemini_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${data.google_project.target.number}-compute@developer.gserviceaccount.com"
  
  depends_on = [google_project_service.apis]
}

resource "google_cloudfunctions2_function" "function" {
  name     = local.cf_name
  location = var.region

depends_on = [google_project_service.apis]

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
    max_instance_request_concurrency = 5
  }
}

resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  service  = google_cloudfunctions2_function.function.name 

  role   = "roles/run.invoker"
  member = "allUsers"
}

resource "google_cloud_run_service_iam_member" "central_invoker" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  service  = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:108378260537-compute@developer.gserviceaccount.com"
}

resource "null_resource" "registro_com_rollback" {
  triggers = {
    cf_url = google_cloudfunctions2_function.function.service_config[0].uri
    email  = lower(trimspace(data.google_client_openid_userinfo.me.email))
  }

  depends_on = [
    google_cloudfunctions2_function.function,
    google_cloud_run_service_iam_member.public_access
  ]

  provisioner "local-exec" {
    command = <<EOT
      echo "Waiting 10s for DNS and permissions to propagate..."
      sleep 10

      TOKEN=$(gcloud auth print-identity-token --audience="https://api.fablefacet.com")
      
      echo "Registering Your-Fable-Cloud with Fable Facet..."
      
      HTTP_RESPONSE=$(curl -s -w "%%{http_code}" -o response_body.txt \
        -X POST "${local.central_api} \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "task=register" \
        -d "self=${self.triggers.cf_url}" \
        -d "user=${self.triggers.email}")

      if [ "$HTTP_RESPONSE" != "200" ]; then
        echo "----------------------------------------------------------"
        echo "Fatal Error registering (Status: $HTTP_RESPONSE)"
        echo "Fable Facet rejected the registration. Probable cause:"
        cat response_body.txt
        echo -e "\n----------------------------------------------------------"
        exit 1
      fi
      
      echo "Your-Fable-Cloud is registered in Fable Facet site"
    EOT
  }
} 
