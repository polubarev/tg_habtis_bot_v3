#!/usr/bin/env bash
set -euo pipefail

# Build the container locally, push to Artifact Registry, and deploy to Cloud Run.
# Required env vars:
#   PROJECT_ID   - GCP project id
# Optional env vars:
#   REGION       - Artifact Registry + Cloud Run region (default: us-central1)
#   REPO         - Artifact Registry repo name (default: habits-bot)
#   SERVICE_NAME - Cloud Run service name (default: habits-diary-bot)
#   IMAGE_TAG    - Image tag (default: latest)

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-habits-bot}"
SERVICE_NAME="${SERVICE_NAME:-habits-diary-bot}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Using image: ${IMAGE}"
echo "Ensure the Artifact Registry repo '${REPO}' exists in region '${REGION}'."

# Authenticate Docker to Artifact Registry (safe to re-run).
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "Building container..."
docker build -t "${IMAGE}" .

echo "Pushing image..."
docker push "${IMAGE}"

echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 0 \
  --max-instances 1

echo "Done. Check service URL via: gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format='value(status.url)'"
