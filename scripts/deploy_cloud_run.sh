#!/usr/bin/env bash
set -euo pipefail

# Build the container locally, push to Artifact Registry, and deploy to Cloud Run.
# Required env vars (either name is accepted):
#   PROJECT_ID / GCP_PROJECT_ID   - GCP project id
# Optional env vars:
#   GCP_REGION / REGION           - Artifact Registry + Cloud Run region (default: us-central1)
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
#   USE_SECRET_MANAGER            - load sensitive keys from Secret Manager instead of env vars (default: true)
#                                   Secrets must exist in Secret Manager using the exact env var name as the secret id.
#                                   Example: gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=<(echo -n "value")
#   SERVICE_ACCOUNT               - service account email to run the Cloud Run service as (enables Workload Identity).
#                                   Defaults to tg-habits-bot@${PROJECT_ID}.iam.gserviceaccount.com when present.

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

# Prefer project/region values from .env over stale shell values from other
# setup steps. PROJECT_ID and REGION are common generic variable names.
PROJECT_ID="${GCP_PROJECT_ID:-${PROJECT_ID:-}}"
: "${PROJECT_ID:?Set PROJECT_ID or GCP_PROJECT_ID}"
REGION="${GCP_REGION:-${REGION:-us-central1}}"
GCP_PROJECT_ID="${GCP_PROJECT_ID:-${PROJECT_ID}}"
GCP_REGION="${GCP_REGION:-${REGION}}"
REPO="${REPO:-habits-bot}"
SERVICE_NAME="${SERVICE_NAME:-habits-diary-bot}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
CONTAINER_TOOL="${CONTAINER_TOOL:-docker}"
PLATFORM="${PLATFORM:-linux/amd64}"
BUILD_STRATEGY="${BUILD_STRATEGY:-local}"
ALLOW_QEMU="${ALLOW_QEMU:-false}"
CLEANUP_AFTER_DEPLOY="${CLEANUP_AFTER_DEPLOY:-true}"
SET_TELEGRAM_WEBHOOK="${SET_TELEGRAM_WEBHOOK:-false}"
STARTUP_CPU_BOOST="${STARTUP_CPU_BOOST:-false}"
USE_SECRET_MANAGER="${USE_SECRET_MANAGER:-true}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-tg-habits-bot@${PROJECT_ID}.iam.gserviceaccount.com}"

# Non-sensitive config — always passed as plain env vars.
CONFIG_APP_ENV_KEYS=(
  APP_NAME
  APP_VERSION
  DEBUG
  LOG_LEVEL
  GCP_PROJECT_ID
  GCP_REGION
  TELEGRAM_WEBHOOK_URL
  TELEGRAM_WEBHOOK_URL_DEBUG
  ADMIN_TELEGRAM_IDS
  REMINDERS_DISPATCH_URL
  REMINDERS_DISPATCH_URL_DEBUG
  REMINDERS_QUEUE_NAME
  OPENROUTER_BASE_URL
  LLM_MODEL
  LLM_TEMPERATURE
  LLM_MAX_TOKENS
  WHISPER_MODEL
  FIRESTORE_COLLECTION_USERS
  FIRESTORE_COLLECTION_SESSIONS
  FIRESTORE_COLLECTION_FEEDBACK
  FIRESTORE_COLLECTION_USAGE_EVENTS
  SESSION_TTL_MINUTES
  RATE_LIMIT_REQUESTS_PER_MINUTE
)

# Sensitive keys — loaded from Secret Manager when USE_SECRET_MANAGER=true,
# otherwise passed as plain env vars (legacy / local testing only).
# Secret Manager secret ids must match these names exactly.
# Create them once with:
#   printf '%s' "$VALUE" | gcloud secrets create KEY_NAME --data-file=- --project="${PROJECT_ID}"
SENSITIVE_APP_ENV_KEYS=(
  TELEGRAM_BOT_TOKEN
  TELEGRAM_BOT_TOKEN_DEBUG
  TELEGRAM_WEBHOOK_SECRET
  REMINDERS_DISPATCH_SECRET
  OPENROUTER_API_KEY
  OPENAI_API_KEY
)

# GOOGLE_CREDENTIALS_PATH is only needed for local dev (no Workload Identity).
# When SERVICE_ACCOUNT is set the container uses Workload Identity and needs no key file.
if [[ -z "${SERVICE_ACCOUNT}" ]]; then
  CONFIG_APP_ENV_KEYS+=(GOOGLE_CREDENTIALS_PATH)
  # src/secrets/ is excluded from Docker images (see .dockerignore), so any
  # GOOGLE_CREDENTIALS_PATH pointing inside src/secrets/ will not resolve in the container.
  # Fail fast here so the user doesn't silently deploy a broken service.
  if [[ -n "${GOOGLE_CREDENTIALS_PATH:-}" && "${GOOGLE_CREDENTIALS_PATH}" == src/secrets/* ]]; then
    cat >&2 <<EOF
ERROR: SERVICE_ACCOUNT is unset AND GOOGLE_CREDENTIALS_PATH points inside src/secrets/
       which is excluded from the Docker image. The deployed container will not
       have access to the key file and will fail to reach Firestore / Sheets.

       Fix: set SERVICE_ACCOUNT=<service-account-email> to use Workload Identity
            (recommended), e.g. SERVICE_ACCOUNT=tg-habits-bot@${PROJECT_ID}.iam.gserviceaccount.com
EOF
    exit 1
  fi
fi

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
for key in "${CONFIG_APP_ENV_KEYS[@]}"; do
  val="${!key-}"
  if [[ -n "${val}" ]]; then
    ENV_ARGS+=("${key}=${val}")
  fi
done

SECRET_ARGS=()
if [[ "${USE_SECRET_MANAGER}" == "true" ]]; then
  # Only wire up secrets whose value is present locally (proxy for "user actually uses this key").
  # This avoids failing when an optional secret like TELEGRAM_BOT_TOKEN_DEBUG doesn't exist in SM.
  for key in "${SENSITIVE_APP_ENV_KEYS[@]}"; do
    val="${!key-}"
    if [[ -n "${val}" ]]; then
      if gcloud secrets describe "${key}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
        SECRET_ARGS+=("${key}=${key}:latest")
      else
        echo "Secret Manager secret ${key} does not exist; skipping deploy secret binding."
      fi
    fi
  done
else
  echo "WARNING: USE_SECRET_MANAGER is false — sensitive keys passed as plain env vars." >&2
  echo "         Set USE_SECRET_MANAGER=true once secrets exist in Secret Manager." >&2
  for key in "${SENSITIVE_APP_ENV_KEYS[@]}"; do
    val="${!key-}"
    if [[ -n "${val}" ]]; then
      ENV_ARGS+=("${key}=${val}")
    fi
  done
fi

if [[ ${#ENV_ARGS[@]} -gt 0 ]]; then
  DEPLOY_ENV_ARGS+=(--set-env-vars "$(IFS=,; echo "${ENV_ARGS[*]}")")
fi
if [[ ${#SECRET_ARGS[@]} -gt 0 ]]; then
  DEPLOY_ENV_ARGS+=(--set-secrets "$(IFS=,; echo "${SECRET_ARGS[*]}")")
fi
CPU_BOOST_ARGS=()
if [[ "${STARTUP_CPU_BOOST}" == "true" ]]; then
  CPU_BOOST_ARGS=(--cpu-boost)
fi

SA_ARGS=()
if [[ -n "${SERVICE_ACCOUNT}" ]]; then
  SA_ARGS=(--service-account "${SERVICE_ACCOUNT}")
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
  "${SA_ARGS[@]}" \
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
