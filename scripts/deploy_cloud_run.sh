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
#   PLATFORM                      - container platform (default: linux/amd64)
#   BUILD_STRATEGY                - local or cloud (default: local)
#   ALLOW_QEMU                    - keep local cross-arch build on Apple Silicon (default: false)
#   CLEANUP_AFTER_DEPLOY          - delete pushed image from Artifact Registry and local cache (default: false)
#   SET_TELEGRAM_WEBHOOK          - call Telegram setWebhook after deploy (default: false)
#   STARTUP_CPU_BOOST             - enable startup CPU boost (default: false)

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
PLATFORM="${PLATFORM:-linux/amd64}"
BUILD_STRATEGY="${BUILD_STRATEGY:-local}"
ALLOW_QEMU="${ALLOW_QEMU:-false}"
CLEANUP_AFTER_DEPLOY="${CLEANUP_AFTER_DEPLOY:-false}"
SET_TELEGRAM_WEBHOOK="${SET_TELEGRAM_WEBHOOK:-false}"
STARTUP_CPU_BOOST="${STARTUP_CPU_BOOST:-false}"
APP_ENV_KEYS=(
  APP_NAME
  APP_VERSION
  DEBUG
  LOG_LEVEL
  GCP_PROJECT_ID
  GCP_REGION
  GOOGLE_CREDENTIALS_PATH
  TELEGRAM_BOT_TOKEN
  TELEGRAM_BOT_TOKEN_DEBUG
  TELEGRAM_WEBHOOK_URL
  TELEGRAM_WEBHOOK_URL_DEBUG
  TELEGRAM_WEBHOOK_SECRET
  REMINDERS_DISPATCH_URL
  REMINDERS_DISPATCH_URL_DEBUG
  REMINDERS_QUEUE_NAME
  REMINDERS_DISPATCH_SECRET
  OPENROUTER_API_KEY
  OPENROUTER_BASE_URL
  LLM_MODEL
  LLM_TEMPERATURE
  LLM_MAX_TOKENS
  OPENAI_API_KEY
  WHISPER_MODEL
  FIRESTORE_COLLECTION_USERS
  FIRESTORE_COLLECTION_SESSIONS
  SESSION_TTL_MINUTES
  RATE_LIMIT_REQUESTS_PER_MINUTE
)

if [[ "${BUILD_STRATEGY}" == "local" && "${PLATFORM}" == "linux/amd64" ]]; then
  HOST_ARCH="$(uname -m)"
  case "${HOST_ARCH}" in
    arm64|aarch64)
      if [[ "${ALLOW_QEMU}" != "true" ]]; then
        echo "Host arch ${HOST_ARCH} with ${PLATFORM} detected; switching BUILD_STRATEGY=cloud to avoid QEMU instability."
        BUILD_STRATEGY="cloud"
      fi
      ;;
  esac
fi

case "${BUILD_STRATEGY}" in
  local|cloud) ;;
  *)
    echo "Unsupported BUILD_STRATEGY '${BUILD_STRATEGY}'. Use local or cloud."
    exit 1
    ;;
esac

case "${CONTAINER_TOOL}" in
  docker|podman) ;;
  *)
    if [[ "${BUILD_STRATEGY}" == "local" ]]; then
      echo "Unsupported CONTAINER_TOOL '${CONTAINER_TOOL}'. Use docker or podman."
      exit 1
    fi
    ;;
esac

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "Using image: ${IMAGE}"
echo "Build strategy: ${BUILD_STRATEGY}"
if [[ "${BUILD_STRATEGY}" == "local" ]]; then
  echo "Container tool: ${CONTAINER_TOOL}"
  echo "Platform: ${PLATFORM}"
fi
echo "Ensure the Artifact Registry repo '${REPO}' exists in region '${REGION}'."
echo "Build context: ${ROOT_DIR}"

if [[ "${BUILD_STRATEGY}" == "local" ]]; then
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
  "${CONTAINER_TOOL}" build --platform "${PLATFORM}" -t "${IMAGE}" "${ROOT_DIR}"

  echo "Pushing image..."
  "${CONTAINER_TOOL}" push "${IMAGE}"
else
  echo "Building and pushing with Cloud Build..."
  gcloud builds submit "${ROOT_DIR}" --tag "${IMAGE}" --project "${PROJECT_ID}"
fi

DEPLOY_ENV_ARGS=()
ENV_ARGS=()
for key in "${APP_ENV_KEYS[@]}"; do
  val="${!key-}"
  if [[ -n "${val}" ]]; then
    ENV_ARGS+=("${key}=${val}")
  fi
done
if [[ ${#ENV_ARGS[@]} -gt 0 ]]; then
  DEPLOY_ENV_ARGS=(--set-env-vars "$(IFS=,; echo "${ENV_ARGS[*]}")")
fi
CPU_BOOST_ARGS=()
if [[ "${STARTUP_CPU_BOOST}" == "true" ]]; then
  CPU_BOOST_ARGS=(--cpu-boost)
fi

echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 0 \
  --max-instances 1 \
  "${CPU_BOOST_ARGS[@]}" \
  "${DEPLOY_ENV_ARGS[@]}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')"

if [[ "${SET_TELEGRAM_WEBHOOK}" == "true" ]]; then
  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    echo "SET_TELEGRAM_WEBHOOK is true but TELEGRAM_BOT_TOKEN is not set; skipping webhook registration."
  else
    WEBHOOK_URL="${TELEGRAM_WEBHOOK_URL:-${SERVICE_URL}/telegram/webhook}"
    echo "Setting Telegram webhook to ${WEBHOOK_URL}"
    if [[ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]]; then
      curl -sSf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
        -d "url=${WEBHOOK_URL}" \
        -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
    else
      curl -sSf -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
        -d "url=${WEBHOOK_URL}"
    fi
    echo "Telegram webhook set."
  fi
fi

if [[ "${CLEANUP_AFTER_DEPLOY}" == "true" ]]; then
  echo "Cleaning up Artifact Registry image ${IMAGE}..."
  # Delete tag and image in Artifact Registry to limit storage costs.
  gcloud artifacts docker images delete "${IMAGE}" \
    --quiet \
    --delete-tags \
    --project "${PROJECT_ID}"

  if [[ "${BUILD_STRATEGY}" == "local" ]]; then
    echo "Removing local image cache..."
    "${CONTAINER_TOOL}" rmi -f "${IMAGE}" || true
  fi
fi

echo "Done."
if [[ -n "${SERVICE_URL}" ]]; then
  echo "Service URL: ${SERVICE_URL}"
else
  echo "Check service URL via: gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format='value(status.url)'"
fi
