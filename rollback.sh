PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
BUCKET_NAME="${PROJECT_ID}-fable-data"
TOKEN=$(gcloud auth print-identity-token)
curl -O https://raw.githubusercontent.com/casson-projects-2020/fable-facet/refs/heads/main/main.tf
terraform init -reconfigure \
  -backend-config="bucket=${BUCKET_NAME}" \
  -backend-config="prefix=terraform/state"
terraform destroy \
  -auto-approve \
  -var="region=us-central1" \
  -var="project_id=${PROJECT_ID}" \
  -var="token=${TOKEN}"
# delete the bucket after cloud function removal
gcloud storage rm -r "gs://${BUCKET_NAME}"
