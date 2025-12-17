terraform {
  required_version = ">= 1.0"
  backend "gcs" {
    # O script entrypoint.sh preencherá o bucket via -backend-config
    prefix = "terraform/state"
  }
}

variable "project_id" {}
variable "region" {}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Exemplo simplificado da Cloud Run Function (v2)
resource "google_cloudfunctions2_function" "function" {
  name        = "fable-facet-function"
  location    = var.region
  description = "Minha Cloud Run Function v2"

  build_config {
    runtime     = "python" 
    entry_point = "main"
    source {
      storage_source {
        bucket = "NOME_DO_BUCKET_COM_SEU_CODIGO"
        object = "source.zip"
      }
    }
  }

  service_config {
    max_instance_count = 1
    available_memory   = "256Mi"
  }
}
