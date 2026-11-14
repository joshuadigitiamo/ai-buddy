#!/usr/bin/env bash
# One-time Google Cloud setup for the Cloud Run deployment (INFRA-04, D-03, D-05, D-11, D-12).
#
# It prepares an EXISTING project: it never creates one. The project id and number reach this
# script only as environment variables and are never written to the repository (the repo is public).
# Run it once, with the owner present, from the Docker image that ships gcloud (README, "Bootstrap").
# It prints resource names only, never a secret value, and it never enables shell tracing.
#
# Required environment (no defaults, no committed values):
#   PROJECT_ID        id of the existing project
#   PROJECT_NUMBER    its numeric project number (checked against the project)
#   GITHUB_REPO_ID    numeric id of the GitHub repository allowed to deploy (not its name)
#   OWNER_EMAIL       the owner's Google account, who publishes the index and the videos
# Optional:
#   REGION                  defaults to europe-west8 (D-03); any other value is refused unless
#                           ALLOW_REGION_FALLBACK names that same region, set only after asking Joshua
#
# Most steps are idempotent (describe, then create). The Firestore database location cannot be
# changed once created, so that step asks for a typed confirmation at a terminal.

set -euo pipefail

DEFAULT_REGION="europe-west8"
REGION="${REGION:-${DEFAULT_REGION}}"
REPOSITORY="ai-buddy"
WIF_POOL="github"
WIF_PROVIDER="monorepo"

log() { echo "[bootstrap] $*"; }
die() { echo "[bootstrap] ERROR: $*" >&2; exit 1; }

require() {
  local name
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || die "environment variable ${name} is required"
  done
}

require PROJECT_ID PROJECT_NUMBER GITHUB_REPO_ID OWNER_EMAIL
[[ "${PROJECT_NUMBER}" =~ ^[0-9]+$ ]] || die "PROJECT_NUMBER must be numeric"
[[ "${GITHUB_REPO_ID}" =~ ^[0-9]+$ ]] || die "GITHUB_REPO_ID must be the numeric repository id"
[[ "${OWNER_EMAIL}" == *@* ]] || die "OWNER_EMAIL must be an email address"
command -v gcloud >/dev/null 2>&1 || die "gcloud is required (README: run this script in the cloud-sdk image)"

if [[ "${REGION}" != "${DEFAULT_REGION}" && "${ALLOW_REGION_FALLBACK:-}" != "${REGION}" ]]; then
  die "REGION must be ${DEFAULT_REGION} (D-03); a fallback needs ALLOW_REGION_FALLBACK=${REGION} after asking Joshua"
fi

# Names (RESEARCH, "Roles" and Runtime State Inventory).
INDEX_BUCKET="${PROJECT_ID}-ai-buddy-index"
VIDEOS_BUCKET="${PROJECT_ID}-ai-buddy-videos"
CLAUDE_BUCKET="${PROJECT_ID}-ai-buddy-claude"
SA_MCP="sa-mcp-server"
SA_BOT="sa-chat-bot"
SA_CI="ci-deployer"
SA_MCP_EMAIL="${SA_MCP}@${PROJECT_ID}.iam.gserviceaccount.com"
SA_BOT_EMAIL="${SA_BOT}@${PROJECT_ID}.iam.gserviceaccount.com"
SA_CI_EMAIL="${SA_CI}@${PROJECT_ID}.iam.gserviceaccount.com"
MCP_SECRETS=(google-client-secret oauth-jwt-signing-key oauth-storage-encryption-key)
BOT_SECRETS=(allowed-users thread-key-secret meridian-api-key)

# gcloud with the project fixed on every call, so the operator's default project is never used.
gc() { gcloud --project="${PROJECT_ID}" "$@"; }

# Grant a role without echoing the resulting policy (it lists member emails).
bind_project() { gc projects add-iam-policy-binding "${PROJECT_ID}" --member="$1" --role="$2" --condition=None --quiet >/dev/null; }
bind_bucket() { gc storage buckets add-iam-policy-binding "gs://$1" --member="$2" --role="$3" --quiet >/dev/null; }
bind_secret() { gc secrets add-iam-policy-binding "$1" --member="$2" --role="$3" --quiet >/dev/null; }
bind_sa() { gc iam service-accounts add-iam-policy-binding "$1" --member="$2" --role="$3" --quiet >/dev/null; }

# 0. The project must already exist and carry the expected number.
log "checking the existing project (this script never creates one)"
actual_number="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')" \
  || die "cannot describe the project: check PROJECT_ID, your login and the Cloud Resource Manager API"
[[ "${actual_number}" == "${PROJECT_NUMBER}" ]] || die "PROJECT_NUMBER does not match the project"

# 1. APIs.
log "enabling APIs"
gc services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  storage.googleapis.com \
  chat.googleapis.com

# 2. Firestore (default) database. The location is one-way (D-03): typed confirmation first.
log "Firestore (default) database"
if existing_location="$(gc firestore databases describe --database='(default)' --format='value(locationId)' 2>/dev/null)"; then
  [[ "${existing_location}" == "${REGION}" ]] || die "the (default) database exists in another location than ${REGION}"
  log "  exists in ${REGION}"
else
  [[ -t 0 ]] || die "creating the Firestore database needs a terminal (typed confirmation); run with docker run -it"
  echo "[bootstrap] The Firestore database location cannot be changed after creation."
  read -r -p "[bootstrap] Type the region (${REGION}) to create the database there: " typed
  [[ "${typed}" == "${REGION}" ]] || die "confirmation did not match; nothing created"
  gc firestore databases create --database='(default)' --location="${REGION}" --type=firestore-native
  log "  created in ${REGION}"
fi

# 3. Firestore TTL on expire_at (D-05). Applies within about a day; checked live in 04-13.
log "Firestore TTL policies"
gc firestore fields ttls update expire_at --collection-group=gaps --enable-ttl --async
gc firestore fields ttls update expire_at --collection-group=thread_memory --enable-ttl --async

# 4. Artifact Registry repository with a cleanup policy (keep the 3 most recent versions per image).
log "Artifact Registry repository ${REPOSITORY}"
if ! gc artifacts repositories describe "${REPOSITORY}" --location="${REGION}" >/dev/null 2>&1; then
  gc artifacts repositories create "${REPOSITORY}" --repository-format=docker --location="${REGION}" \
    --description="AI Buddy service images"
fi
policy_file="$(mktemp)"
trap 'rm -f "${policy_file}"' EXIT
printf '%s\n' '[' \
  '  {"name": "delete-old", "action": {"type": "Delete"}, "condition": {"tagState": "any"}},' \
  '  {"name": "keep-recent", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}}' \
  ']' > "${policy_file}"
gc artifacts repositories set-cleanup-policies "${REPOSITORY}" --location="${REGION}" \
  --policy="${policy_file}" --no-dry-run

# 5. Three private buckets: uniform bucket-level access, public access prevention enforced.
log "buckets"
for bucket in "${INDEX_BUCKET}" "${VIDEOS_BUCKET}" "${CLAUDE_BUCKET}"; do
  if ! gc storage buckets describe "gs://${bucket}" >/dev/null 2>&1; then
    gc storage buckets create "gs://${bucket}" --location="${REGION}" \
      --uniform-bucket-level-access --public-access-prevention
  else
    gc storage buckets update "gs://${bucket}" --uniform-bucket-level-access --public-access-prevention
  fi
  log "  ${bucket}"
done
# No age-based delete rule on the index bucket: a lifecycle age rule would also remove the build the
# pointer names after a month without a new sync, and the server would fail to start (README).

# 6. Service accounts.
log "service accounts"
for account in "${SA_MCP}" "${SA_BOT}" "${SA_CI}"; do
  if ! gc iam service-accounts describe "${account}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gc iam service-accounts create "${account}" --display-name="${account}"
  fi
  log "  ${account}"
done

# 7. Secrets: created empty. Values are added later from stdin, never by this script.
log "secrets (empty, no version)"
for secret in "${MCP_SECRETS[@]}" "${BOT_SECRETS[@]}"; do
  if ! gc secrets describe "${secret}" >/dev/null 2>&1; then
    gc secrets create "${secret}" --replication-policy=automatic
  fi
  log "  ${secret}"
done

# 8. Roles, least privilege (RESEARCH "Roles").
log "role bindings"
# ci-deployer: pushes images, deploys services, acts as the two runtime accounts. The services do not
# exist before the first deploy, so run.developer is bound on the project.
gc artifacts repositories add-iam-policy-binding "${REPOSITORY}" --location="${REGION}" \
  --member="serviceAccount:${SA_CI_EMAIL}" --role=roles/artifactregistry.writer --quiet >/dev/null
bind_project "serviceAccount:${SA_CI_EMAIL}" roles/run.developer
bind_sa "${SA_MCP_EMAIL}" "serviceAccount:${SA_CI_EMAIL}" roles/iam.serviceAccountUser
bind_sa "${SA_BOT_EMAIL}" "serviceAccount:${SA_CI_EMAIL}" roles/iam.serviceAccountUser
# sa-mcp-server: Firestore (OAuth state, gap log), the index bucket (read), its three secrets.
bind_project "serviceAccount:${SA_MCP_EMAIL}" roles/datastore.user
bind_bucket "${INDEX_BUCKET}" "serviceAccount:${SA_MCP_EMAIL}" roles/storage.objectViewer
for secret in "${MCP_SECRETS[@]}"; do
  bind_secret "${secret}" "serviceAccount:${SA_MCP_EMAIL}" roles/secretmanager.secretAccessor
done
# sa-chat-bot: Firestore (thread memory), the credentials bucket (read-write, FUSE), its three secrets.
bind_project "serviceAccount:${SA_BOT_EMAIL}" roles/datastore.user
bind_bucket "${CLAUDE_BUCKET}" "serviceAccount:${SA_BOT_EMAIL}" roles/storage.objectUser
for secret in "${BOT_SECRETS[@]}"; do
  bind_secret "${secret}" "serviceAccount:${SA_BOT_EMAIL}" roles/secretmanager.secretAccessor
done
# The owner: reads videos, publishes the index and videos, forces a new revision after a publish.
bind_bucket "${VIDEOS_BUCKET}" "user:${OWNER_EMAIL}" roles/storage.objectViewer
bind_bucket "${VIDEOS_BUCKET}" "user:${OWNER_EMAIL}" roles/storage.objectAdmin
bind_bucket "${INDEX_BUCKET}" "user:${OWNER_EMAIL}" roles/storage.objectAdmin
bind_project "user:${OWNER_EMAIL}" roles/run.developer

# 9. Workload Identity Federation for GitHub Actions: keyless, limited to one repository id and main.
log "Workload Identity Federation"
if ! gc iam workload-identity-pools describe "${WIF_POOL}" --location=global >/dev/null 2>&1; then
  gc iam workload-identity-pools create "${WIF_POOL}" --location=global --display-name="GitHub Actions"
fi
attribute_condition="assertion.repository_id == '${GITHUB_REPO_ID}' && assertion.ref == 'refs/heads/main'"
attribute_mapping="google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.ref=assertion.ref"
if ! gc iam workload-identity-pools providers describe "${WIF_PROVIDER}" \
    --location=global --workload-identity-pool="${WIF_POOL}" >/dev/null 2>&1; then
  gc iam workload-identity-pools providers create-oidc "${WIF_PROVIDER}" \
    --location=global --workload-identity-pool="${WIF_POOL}" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="${attribute_mapping}" \
    --attribute-condition="${attribute_condition}"
else
  gc iam workload-identity-pools providers update-oidc "${WIF_PROVIDER}" \
    --location=global --workload-identity-pool="${WIF_POOL}" \
    --attribute-mapping="${attribute_mapping}" \
    --attribute-condition="${attribute_condition}"
fi
bind_sa "${SA_CI_EMAIL}" \
  "principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository_id/${GITHUB_REPO_ID}" \
  roles/iam.workloadIdentityUser

# 10. What to do next. Names and non-secret values only.
log "done. Add these GitHub repository variables (Settings, Secrets and variables, Actions, Variables):"
echo "  GCP_PROJECT_ID          = ${PROJECT_ID}"
echo "  GCP_PROJECT_NUMBER      = ${PROJECT_NUMBER}"
echo "  GCP_WIF_PROVIDER        = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"
echo "  GCP_DEPLOYER_SA         = ${SA_CI_EMAIL}"
echo "  GCP_OAUTH_CLIENT_ID     = (the OAuth client id of the MCP server, from the Google Auth platform)"
echo "  GUIDES_WEB_BASE         = (https base URL of the Guides repository)"
echo "  CHAT_JWT_ISSUER_EMAIL   = (the account that signs Chat requests, see the Chat app format)"
echo "  VIDEO_THUMBNAIL_URL     = (https URL of the card thumbnail)"
echo "  HELP_COMMAND_ID         = (the Chat app help command id)"
log "Add secret values from stdin, never on a command line, for example:"
echo "  gcloud secrets versions add <name> --project=\"\$PROJECT_ID\" --data-file=-"
echo "  secrets: ${MCP_SECRETS[*]} ${BOT_SECRETS[*]}"
log "Seed the credentials bucket ${CLAUDE_BUCKET} as the README describes (04-01 token_chain (b))."
