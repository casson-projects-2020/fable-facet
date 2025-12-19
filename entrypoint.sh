#!/bin/bash

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

ORG_ID=$(gcloud projects get-ancestors $PROJECT_ID --format='value(id)' | tail -n 1)
ANCESTOR_TYPE=$(gcloud projects get-ancestors $PROJECT_ID --format='value(type)' | tail -n 1)

if [ "$ANCESTOR_TYPE" == "organization" ]; then
    echo "⚠️ This project belongs to an Organization - the installation will abort"
    echo "Fable Facet is licenced only to individual, personal GCP accounts"
    echo "⚠️ Caution: don't remove this - other parts of the code will fail in GCP accounts linked to Organizations"
    echo "------------------------------------------------------------"
    echo "Press [ENTER] on the terminal to close..."
    read -r  
    exit 1
fi

USER_EMAIL=$(gcloud config get-value account)

echo "📧 Detected user: $USER_EMAIL"
echo "⚠️ Attention: if this email is NOT the same used to login on Fable Facet site, Your-Fable-Cloud will not run"
echo
echo "security based on Federated Identity: no secrets are exchanged, just Google-signed OIDC tokens to verify ownership."
echo "Read more on Tech section, 'Security Model', on Fable Facet site" 
echo

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
    
echo "🛠️ Initing Terraform..."
terraform init -reconfigure -backend-config="bucket=${BUCKET_NAME}" -backend-config="prefix=terraform/state"

terraform apply -auto-approve -var="project_id=${PROJECT_ID}" -var="region=${REGION}" -var="infra_bucket=${BUCKET_NAME}" 

echo "✅ All done - Your-Fable-Cloud is installed. Get back to Fable Facet site to use it"
echo
echo "this script created one bucket on Cloud Storage, and one Cloud Run Function"
echo "If you want to uninstall it, just delete the resources, then use 'delete my account' on Fable Facet site"
echo "Read more on Tech section, 'How to delete my account', on Fable Facet site"
echo
echo "If you delete the cloud function by accident, you may also need to use 'delete my account' to recreate it"
echo "Read more on Tech section, 'I deleted the cloud function by accident', on Fable Facet site"
echo
echo




