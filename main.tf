terraform {
  required_version = ">= 1.0"
  backend "gcs" {
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
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
    "generativelanguage.googleapis.com",
    "people.googleapis.com",
    "apikeys.googleapis.com",
    "oslogin.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
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

data "http" "cloudflare_ips" {
  url = "https://api.cloudflare.com/client/v4/ips"

  request_headers = {
    Accept = "application/json"
  }
}

locals {
  cloudflare_json = jsondecode(data.http.cloudflare_ips.response_body)
  
  # Listas limpas de CIDRs prontas para uso
  cf_ipv4_blocks = local.cloudflare_json.result.ipv4_cidrs
  cf_ipv6_blocks = local.cloudflare_json.result.ipv6_cidrs
}

resource "google_compute_network" "vpc_network" {
  name                    = "app-ff-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "vpc_subnet" {
  name          = "app-ff-subnet"
  ip_cidr_range = "10.10.1.0/24"
  region        = "us-central1"
  network       = google_compute_network.vpc_network.id
}

resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal-traffic"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["8080"] 
  }

  target_tags = ["websocket-server"]

  source_ranges = ["10.10.1.0/24"]
}

resource "google_compute_firewall" "allow_cloudflare_websocket" {
  name    = "allow-cloudflare-websocket-traffic"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["8080"] 
  }

  target_tags = ["websocket-server"]

  source_ranges = local.cf_ipv4_blocks
}

resource "google_service_account" "vm_isolated_sa" {
  account_id   = "fable-facet-vm-sa"
  display_name = "Isolated Service Account for Fable Facet VM"

  depends_on = [google_project_service.apis]
}

resource "google_compute_instance" "vm_free_tier" {
  name         = "app-ff-backend-vm"
  machine_type = "e2-micro" # Free Tier
  zone         = "us-central1-a"

  tags = ["websocket-server"]

  metadata = {
    enable-oslogin = "TRUE"
  }
  
  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      type  = "pd-standard"
      size  = 30
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vpc_subnet.id
    access_config {}
  } 

  service_account {
    email  = google_service_account.vm_isolated_sa.email
    scopes = ["cloud-platform"] 
  }

  depends_on = [
    google_project_service.apis,
    google_service_account.vm_isolated_sa
  ]

  metadata_startup_script = templatefile("${path.module}/startup_vm.sh", {
    PYTHON_CODE = file("${path.module}/websocket_server_vm.py")
  })
}

resource "google_service_account" "function_sa" {
  account_id   = "fable-facet-user"
  display_name = "Service Account to Your-Fable-Cloud function"
}

resource "google_service_account_iam_member" "allow_openid_impersonation" {
  service_account_id = google_service_account.function_sa.name
  role               = "roles/iam.serviceAccountOpenIdTokenCreator"
  member             = "user:${local.email}"
}

resource "google_service_account_iam_member" "allow_openid_impersonation_sa" {
  service_account_id = google_service_account.function_sa.name
  role               = "roles/iam.serviceAccountOpenIdTokenCreator"
  member             = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_service_account_iam_member" "allow_token_creation" {
  service_account_id = google_service_account.function_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:${local.email}" 
}

resource "google_project_iam_member" "monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_service_account_iam_member" "allow_token_creation_sa" {
  service_account_id = google_service_account.function_sa.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.function_sa.email}" 
}

resource "google_storage_bucket_iam_member" "function_storage_access" {
  bucket = "${var.project_id}-fable-data"
  role   = "roles/storage.objectUser" 
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_custom_role" "api_key_ops" {
  role_id     = "api_key_string_ops"
  title       = "API Key String ops"
  description = "allow API keys operations, without adding admin rights"
  stage       = "GA"

  permissions = [
    "apikeys.keys.list",
    "apikeys.keys.get",
    "apikeys.keys.update",
    "apikeys.keys.getKeyString"
  ]
}

resource "google_project_iam_custom_role" "vm_starter_role" {
  role_id     = "compute.instanceStarterMinimal"
  title       = "Compute Instance Starter Minimal"
  description = "Check VM status and restart it if needed"
  
  permissions = [
    "compute.instances.start",
    "compute.instances.get"
  ]
}

resource "google_project_iam_member" "cf_role_binding" {
  project = var.project_id
  role    = google_project_iam_custom_role.api_key_ops.id
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_compute_instance_iam_member" "specific_vm_binding" {
  project       = var.project_id
  zone          = "us-central1-a"
  instance_name = "app-ff-backend-vm"
  role          = google_project_iam_custom_role.vm_starter_role.id
  member        = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_apikeys_key" "meta_key" {
  name = "fable-facet-meta-key"
  display_name = "Fable Facet key - don't erase"

  restrictions {
    api_targets {
      service = "people.googleapis.com"  # dummy restriction for security reasons
      methods = ["GET*"]
    }

    browser_key_restrictions {
      allowed_referrers = ["https://fablefacet.com*"]
    }
  }
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
      GCP_PROJECT = "${var.project_id}"
      GCP_PROJECT_NAME = data.google_project.project.name
    }
  }
}

resource "google_project_service_identity" "iap_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "iap.googleapis.com"
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project = var.project_id
  location = var.region
  name = google_cloudfunctions2_function.function.name
  role   = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap_sa.email}"

  depends_on = [google_project_service.iap_api]
}

resource "local_file" "iap_policy_json" {
  filename = "/tmp/iap_policy_yfc.json"
  content  = <<EOT
{
  "bindings": [
    {
      "role": "roles/iap.httpsResourceAccessor",
      "members": [
        "user:${local.email}",
    # this line allows the service account from Fable Facet GCP account to call the
    # cloud function created here through IAP - if your account is not a personal one,
    # this will fail and YFC will never work. There are also other policies from GCP
    # that can block this - please contact us if you can't make it work
        "serviceAccount:ffacet-functions@fable-facet-481518.iam.gserviceaccount.com"
      ]
    }
  ]
}
EOT
}

data "google_service_account_id_token" "cf_jwt" {
    provider               = google
    target_service_account = google_service_account.function_sa.email
    delegates              = []
    target_audience        = "${google_cloudfunctions2_function.function.service_config[0].uri};${local.email};${local.sub}"
    include_email          = true
}

resource "null_resource" "registro_com_rollback" {
  triggers = {
    cf_url = google_cloudfunctions2_function.function.service_config[0].uri
  }

  depends_on = [ google_cloudfunctions2_function.function,
      google_service_account_iam_member.allow_openid_impersonation,
      google_service_account_iam_member.allow_token_creation
  ]

  provisioner "local-exec" {
    command = <<EOT
      gcloud run services update ${local.cf_name} \
        --region="us-central1" \
        --iap \
        --project=${var.project_id}

      gcloud iap web set-iam-policy ${local_file.iap_policy_json.filename} \
        --region="us-central1" \
        --resource-type=cloud-run \
        --service=${google_cloudfunctions2_function.function.name} \
        --project=${var.project_id}

      export cf_url="${self.triggers.cf_url}"

      echo "Registering Your-Fable-Cloud with Fable Facet..."

      for i in {1..3}; do
          echo "Register attempt $i..."

        HTTP_RESPONSE=$(curl -s -w "%%{http_code}" -o response_body.txt \
          -X POST "https://api.fablefacet.com" \
          -H "Content-Type: application/x-www-form-urlencoded" \
          -d "task=register" \
          -d "jwt=${data.google_service_account_id_token.cf_jwt.id_token}" )

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
