#!/usr/bin/env bash
set -euo pipefail

# Build the container locally, push to Artifact Registry, and deploy to Cloud Run.
# Required env vars (either name is accepted):
#   PROJECT_ID / GCP_PROJECT_ID   - GCP project id
# Optional env vars (either name accepted for region):
#   REGION / GCP_REGION           - Artifact Registry + Cloud Run region (default: us-central1)
#   REPO                          - Artifact Registry repo name (default: habits-bot)
#   SERVICE_NAME                  - Cloud Run service name (default: habits-diary-bot)
#   IMAGE_TAG                     - Image tag (default: latest)
#   CONTAINER_TOOL                - docker or podman (default: docker)
#   CLEANUP_AFTER_DEPLOY          - delete pushed image from Artifact Registry and local cache (default: false)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_CANDIDATES=(".env" "${SCRIPT_DIR}/../.env" "${SCRIPT_DIR}/.env")
for env_file in "${ENV_CANDIDATES[@]}"; do
  if [[ -f "${env_file}" ]]; then
    echo "Loading environment variables from ${env_file}"
    set -a
    # shellcheck disable=SC1091
    source "${env_file}"
    set +a
    break
  fi
done

: "${PROJECT_ID:=${GCP_PROJECT_ID:-}}"
: "${PROJECT_ID:?Set PROJECT_ID or GCP_PROJECT_ID}"
REGION="${REGION:-${GCP_REGION:-us-central1}}"
REPO="${REPO:-habits-bot}"
SERVICE_NAME="${SERVICE_NAME:-habits-diary-bot}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_TOOL="${CONTAINER_TOOL:-docker}"
CLEANUP_AFTER_DEPLOY="${CLEANUP_AFTER_DEPLOY:-false}"

case "${CONTAINER_TOOL}" in
  docker|podman) ;;
  *)
    echo "Unsupported CONTAINER_TOOL '${CONTAINER_TOOL}'. Use docker or podman."
    exit 1
    ;;
esac

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Using image: ${IMAGE}"
echo "Container tool: ${CONTAINER_TOOL}"
echo "Ensure the Artifact Registry repo '${REPO}' exists in region '${REGION}'."
echo "Build context: ${ROOT_DIR}"

if [[ "${CONTAINER_TOOL}" == "docker" ]]; then
  echo "Authenticating Docker to Artifact Registry (safe to re-run)..."
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
else
  echo "Authenticating Podman to Artifact Registry..."
  ACCESS_TOKEN="$(gcloud auth print-access-token)"
  "${CONTAINER_TOOL}" login \
    --username oauth2accesstoken \
    --password "${ACCESS_TOKEN}" \
    "https://${REGION}-docker.pkg.dev"
fi

echo "Building container..."
"${CONTAINER_TOOL}" build -t "${IMAGE}" "${ROOT_DIR}"

echo "Pushing image..."
"${CONTAINER_TOOL}" push "${IMAGE}"

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

if [[ "${CLEANUP_AFTER_DEPLOY}" == "true" ]]; then
  echo "Cleaning up Artifact Registry image ${IMAGE}..."
  # Delete tag and image in Artifact Registry to limit storage costs.
  gcloud artifacts docker images delete "${IMAGE}" \
    --quiet \
    --delete-tags \
    --project "${PROJECT_ID}"

  echo "Removing local image cache..."
  "${CONTAINER_TOOL}" rmi -f "${IMAGE}" || true
fi

echo "Done. Check service URL via: gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format='value(status.url)'"
