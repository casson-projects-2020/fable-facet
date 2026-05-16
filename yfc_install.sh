#!/bin/bash

set -e
touch /tmp/yfc_install.flag
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)

USER_EMAIL=$(gcloud config get-value account)

echo "📧 user: $USER_EMAIL"
echo

REGION="us-central1"
BUCKET_NAME="${PROJECT_ID}-fable-data"

echo "🚀 Starting install on project: $PROJECT_ID"

if gcloud storage buckets describe gs://${BUCKET_NAME} >/dev/null 2>&1; then
    echo "✅ Bucket already exists."
else
    echo "📦 Criating bucket..."
    if gcloud storage buckets create gs://${BUCKET_NAME} --location=${REGION}; then
        gcloud storage buckets update gs://${BUCKET_NAME} --versioning
    else
        echo "❌ Fatal Error: cannot install Your-Fable-Cloud."
        echo
        echo "If the error appears to be temporaty you may try to install again."
        echo "Close the browser tab and Google Cloud Shell and return to Fable Facet site."
        echo
        echo "Please contact us."

        exit 1
    fi
fi

cd function_code
zip -r ../fablefacet.zip .
cd ..
gcloud storage cp fablefacet.zip gs://${BUCKET_NAME}/source/fablefacet.zip
    
echo "🛠️ Initing Terraform..."
TOKEN=$(gcloud auth print-identity-token)
export TF_IN_AUTOMATION=true
export TF_INPUT=0
export TF_CLI_ARGS="-no-color"

terraform init -reconfigure -backend-config="bucket=${BUCKET_NAME}" -backend-config="prefix=terraform/state"

# check if terraform succeeded
rm -f /tmp/tf_failed.flag
terraform apply -auto-approve -var="project_id=${PROJECT_ID}" \
            -var="region=${REGION}" -var="token=${TOKEN}" 2>&1 | tee /tmp/tf_apply.log
TF_EXIT_CODE=$?

if [ $TF_EXIT_CODE -ne 0 ] || [ -f /tmp/tf_failed.flag ]; then
    terraform destroy -auto-approve -var="project_id=${PROJECT_ID}" \
                -var="region=${REGION}" -var="token=${TOKEN}" 2>&1 | tee /tmp/tf_dest.log

    echo "❌ Fatal Error: cannot install Your-Fable-Cloud."
    echo
    echo "If the error appears to be temporaty you may try to install again."
    echo "Close the browser tab and Google Cloud Shell and return to Fable Facet site."
    echo
    echo "Please contact us."

    exit 1
else
    echo "✅ Success - Your-Fable-Cloud is installed. Get back to Fable Facet site to use it"
    echo
    echo "this script created one bucket on Cloud Storage, and one Cloud Run Function"
    echo "If you want to uninstall it, see instructions on Fable Facet site site:"
    echo "in Tech section, 'How to delete my account'"
    echo
    echo "You can now close the browser tab and Google Cloud Shell and return to Fable Facet site"
fi
