#!/bin/bash

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
BUCKET_NAME="${PROJECT_ID}-fable-data"

echo "🚀 Starting install on project: $PROJECT_ID"

if gsutil ls -b "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    echo "✅ Bucket already exists."
else
    echo "📦 Criating bucket..."
    gsutil mb -l ${REGION} gs://${BUCKET_NAME}
    gsutil versioning set on gs://${BUCKET_NAME}
fi

cd function_code
zip -r ../fablefacet.zip .
cd ..
gsutil cp fablefacet.zip gs://${BUCKET_NAME}/source/fablefacet.zip

gcloud services enable \
    cloudresourcemanager.googleapis.com \
    compute.googleapis.com \
    run.googleapis.com \
    cloudfunctions.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com
    
echo "🛠️ Initing Terraform..."
terraform init -reconfigure -backend-config="bucket=${BUCKET_NAME}" -backend-config="prefix=terraform/state"

terraform apply -auto-approve -var="project_id=${PROJECT_ID}" -var="region=${REGION}" -var="infra_bucket=${BUCKET_NAME}"

echo "✅ All done - Your-Fable-Cloud is installed. Get back to Fable Facet site to use it"
