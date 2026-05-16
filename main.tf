terraform {
  required_version = ">= 1.0"
  backend "gcs" {
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0" # Força o uso da versão 5.x
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0" # Isso garante estabilidade
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

variable "project_id"   {
  type = string
}
variable "region"       { 
  type = string
  default = "us-central1" 
}
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
  email         = local.decoded.email
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

resource "google_project_service" "iap_api" {
  project  = var.project_id
  service  = "iap.googleapis.com"

  disable_on_destroy = false
}

resource "google_service_account" "function_sa" {
  account_id   = "fable-facet-user"
  display_name = "Service Account to Your-Fable-Cloud function"
}

resource "google_service_account_iam_member" "allow_impersonation" {
  service_account_id = google_service_account.function_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:${local.email}" 
}

resource "google_storage_bucket_iam_member" "function_storage_access" {
  bucket = "${var.project_id}-fable-data"
  role   = "roles/storage.objectUser" 
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "random_id" "suffix" {
  byte_length = 5
}

locals {
  cf_name = "ffacet-user-${random_id.suffix.hex}"
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
        bucket = "${var.project_id}-fable-data"
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
      SUB = lower(trimspace(local.sub))
      EMAIL = lower(trimspace(local.email))
      CONFIG_BUCKET = "${var.project_id}-fable-data"
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project = var.project_id
  location = var.region
  name = google_cloudfunctions2_function.function.name
  role   = "roles/run.invoker"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com"

  depends_on = [google_project_service.iap_api]
}

resource "null_resource" "registro_com_rollback" {
  triggers = {
    cf_url = google_cloudfunctions2_function.function.service_config[0].uri
  }

  depends_on = [ google_cloudfunctions2_function.function ]

  provisioner "local-exec" {
    command = <<EOT
      gcloud run services update ${local.cf_name} \
        --region="us-central1" \
        --iap \
        --project=${var.project_id}

      export cf_url=${self.triggers.cf_url}

      SA_ACCESS_TOKEN=$(gcloud auth print-access-token \
                        --impersonate-service-account="${google_service_account.function_sa.email}")

      #TOKEN=$(gcloud auth print-identity-token \
      #          --impersonate-service-account="${google_service_account.function_sa.email}" \
      #          --audiences="${self.triggers.cf_url}")

      TOKEN=$(curl -s -X POST "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${google_service_account.function_sa.email}:generateIdToken" \
      -H "Authorization: Bearer $SA_ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{
        \"audience\": \"${self.triggers.cf_url}\",
        \"includeEmail\": true
      }" | grep -o '"idToken": "[^"]*' | grep -o '[^"]*$')

      echo $TOKEN
      echo "Registering Your-Fable-Cloud with Fable Facet..."

      for i in {1..3}; do
          echo "Register attempt $i..."

        HTTP_RESPONSE=$(curl -s -w "%%{http_code}" -o response_body.txt \
          -X POST "https://api.fablefacet.com" \
          -H "Content-Type: application/x-www-form-urlencoded" \
          -d "task=register" \
          -d "jwt=$TOKEN" )

        if [ "$HTTP_RESPONSE" == "200" ]; then
            echo "Your-Fable-Cloud successfuly registered in Fable Facet API"
            break
        else
            echo "Register failure (HTTP $HTTP_RESPONSE). Retrying in $((i * 5))s..."
            if [ "$i" != "3" ]; then
                sleep $((i * 5))
            fi
        fi
        
        if [ "$i" == "3" ]; then
          echo "Fatal: Can't register after 3 attempts."
        fi
      done

      if [ "$HTTP_RESPONSE" != "200" ]; then
        echo "----------------------------------------------------------"
        echo "Fatal Error registering \(Status: $HTTP_RESPONSE\)"
        echo "If the error appear to be temporary, reinstall Your-Fable-Cloud."
        echo "Please contact us."
        echo "Probable cause:"
        cat response_body.txt
        echo -e "\n----------------------------------------------------------"
        touch /tmp/tf_failed.flag
        sleep 2
        exit 1
      fi

      echo "Your-Fable-Cloud is installed in your account and registered in Fable Facet site"
    EOT

    on_failure = continue
  }
} 

