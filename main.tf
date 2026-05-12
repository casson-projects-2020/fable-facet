terraform {
  required_version = ">= 1.0"
  backend "gcs" {
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0" # Força o uso da versão 5.x
    }
  }
}

variable "project_id"   {}
variable "region"       { default = "us-central1" }
variable "token" {
  type      = string
  sensitive = true
}

data "google_client_openid_userinfo" "me" {}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "project" {
  project_id = var.project_id
}

locals {
  payload_raw   = split( ".", var.token )[ 1 ]
  padding_len   = ( 4 - ( length( local.payload_raw ) % 4 )) % 4
  padding       = substr( "==", 0, local.padding_len )
  payload_ready = "${local.payload_raw}${local.padding}"
  decoded       = jsondecode( base64decode( local.payload_ready ))
  sub           = local.decoded.sub 
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
    "generativelanguage.googleapis.com"
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.services)
  project  = var.project_id
  service  = each.key

  disable_on_destroy = false
}

resource "google_service_account" "function_sa" {
  account_id   = "user-instance-sa"
  display_name = "Service Account to Your-Fable-Cloud function"
}

resource "google_storage_bucket_iam_member" "function_storage_access" {
  bucket = google_storage_bucket.user_config.name
  role   = "roles/storage.objectUser" 
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_cloudfunctions2_function" "function" {
  name     = local.cf_name
  location = var.region

depends_on = [
  google_storage_bucket_iam_member.function_storage_access,
  google_project_service.apis
]

  build_config {
    runtime     = "python312"
    entry_point = "main" 
    source {
      storage_source {
        bucket = google_storage_bucket.user_config.name
        object = "source/fablefacet.zip"
      }
    }
  }
  service_config {
    ingress_settings = "ALLOW_ALL"
    max_instance_count = 1
    available_memory   = "256Mi"
    max_instance_request_concurrency = 1
    timeout_seconds = 60

    service_account_email = google_service_account.function_sa.email

    environment_variables = {
      SUB = lower(trimspace(data.google_client_openid_userinfo.me.sub))
      EMAIL = lower(trimspace(data.google_client_openid_userinfo.me.email))
      CONFIG_BUCKET = google_storage_bucket.user_config.name
    }
  }
}

resource "google_project_service" "iap_api" {
  project = var.project_id
  service = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project = google_cloud_run_v2_service.default.project
  location = google_cloud_run_v2_service.default.location
  name = google_cloud_run_v2_service.default.name
  role   = "roles/run.invoker"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com"

  depends_on = [google_project_service.iap_api]
}

resource "null_resource" "registro_com_rollback" {
  triggers = {
    cf_url = google_cloudfunctions2_function.function.service_config[0].uri
    email  = lower(trimspace(data.google_client_openid_userinfo.me.email))
  }

  depends_on = [ google_cloudfunctions2_function.function ]

  provisioner "local-exec" {
    command = <<EOT
      echo "Waiting 10s for DNS and permissions to propagate..."
      sleep 10

      gcloud run services update ${local.cf_name} \
      --no-invoker-iam-check \
      --region=${var.region} \
      --quiet

      TOKEN=$(gcloud auth print-identity-token)
      
      echo "Registering Your-Fable-Cloud with Fable Facet..."

      for i in {1..3}; do
          echo "Register attempt $i..."

        HTTP_RESPONSE=$(curl -s -w "%%{http_code}" -o response_body.txt \
            --max-time 30 \
            -X POST "${self.triggers.cf_url}" \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -d "task=register" \
            -d "self=${self.triggers.cf_url}" \
            -d "user=${self.triggers.email}" \
            -d "token=$TOKEN" )

        if [ "$HTTP_RESPONSE" == "200" ]; then
            echo "Your-Fable-Cloud successfuly registered in Fable Facet API"
            break
        else
            echo "Register failure (HTTP $HTTP_RESPONSE). Retrying in $((i * 5))s..."
            sleep $((i * 5))
        fi
        
        if [ "$i" == "3" ]; then
          echo "Fatal: Can't register after 3 attempts."
        fi
      done

      gcloud run services update ${local.cf_name} \
      --iap=enabled \
      --no-invoker-iam-check \
      --region=${var.region} \
      --quiet

      if [ "$HTTP_RESPONSE" != "200" ]; then
        echo "----------------------------------------------------------"
        echo "Fatal Error registering \(Status: $HTTP_RESPONSE\)"
        echo "Uninstall and Reinstall Your-Fable-Cloud."
        echo "Probable cause:"
        cat response_body.txt
        echo -e "\n----------------------------------------------------------"
        exit 1
      fi
      
      echo "Your-Fable-Cloud is registered in Fable Facet site"
    EOT
  }
} 

