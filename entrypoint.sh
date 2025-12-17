#!/bin/bash

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
BUCKET_NAME="${PROJECT_ID}-tfstate-fable"

echo "🚀 Iniciando instalação no projeto: $PROJECT_ID"

if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    echo "✅ Bucket already exists."
else
    echo "📦 Criating bucket..."
    gsutil mb -l ${REGION} gs://${BUCKET_NAME}
    gsutil versioning set on gs://${BUCKET_NAME}
fi

gcloud services enable cloudfunctions.googleapis.com cloudbuild.googleapis.com run.googleapis.com

echo "🛠️ Initing Terraform..."
terraform init -backend-config="bucket=${BUCKET_NAME}"

terraform apply -auto-approve -var="project_id=${PROJECT_ID}" -var="region=${REGION}"
