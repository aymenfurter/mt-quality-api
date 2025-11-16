#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

show_usage() {
  cat <<'USAGE'
Usage: ./scripts/deploy.sh [env-file]

Provision Azure resources (Azure SQL Database, ACR, Container Apps) and deploy
this API. Requires an existing Azure OpenAI endpoint and deployment; supply their
details via environment variables. Azure CLI access with the correct subscription
must be available.

Environment variables (can be exported or provided via the optional env-file):
  AZURE_SUBSCRIPTION_ID   Subscription to target
  RESOURCE_GROUP          Resource group name
  AZURE_LOCATION          Primary Azure region (e.g., eastus)
  AZURE_OPENAI_ENDPOINT   Fully-qualified Azure OpenAI endpoint URL
  AZURE_OPENAI_API_KEY    Azure OpenAI API key
  AZURE_OPENAI_API_VERSION Azure OpenAI API version (e.g., 2024-08-01-preview)
  AZURE_OPENAI_DEPLOYMENT Azure OpenAI deployment name (e.g., gpt4o)
  DEFAULT_LLM_MODEL       Default model identifier for the application
  AZURE_SQL_SERVER        SQL server name (global unique, no domain)
  AZURE_SQL_DB            SQL database name
  AZURE_SQL_ADMIN         SQL admin username
  AZURE_SQL_PASSWORD      SQL admin password
  ACR_NAME                Azure Container Registry name (global unique)
  ACA_ENVIRONMENT         Container Apps environment name
  ACA_APP_NAME            Container App name

Optional overrides (defaults shown):
  ACR_SKU                 Basic
  IMAGE_NAME              gemba-score-api
  IMAGE_TAG               git rev-parse --short HEAD (fallback: timestamp)
  CONTAINER_MIN_REPLICAS  1
  CONTAINER_MAX_REPLICAS  3

If an env-file path is supplied, it will be sourced before validation. A file named
".env.deploy" is automatically loaded when present.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  show_usage
  exit 0
fi

DEFAULT_ENV_FILE=".env.deploy"
CUSTOM_ENV_FILE="${1:-}"

if [[ -n "$CUSTOM_ENV_FILE" ]]; then
  if [[ ! -f "$CUSTOM_ENV_FILE" ]]; then
    echo "[deploy] Env file '$CUSTOM_ENV_FILE' not found" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$CUSTOM_ENV_FILE"
elif [[ -f "$DEFAULT_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$DEFAULT_ENV_FILE"
fi

command -v az >/dev/null 2>&1 || { echo "Azure CLI (az) is required" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }

require_env() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "[deploy] Missing required environment variable: $var_name" >&2
    exit 1
  fi
}

for required in \
  AZURE_SUBSCRIPTION_ID \
  RESOURCE_GROUP \
  AZURE_LOCATION \
  AZURE_OPENAI_ENDPOINT \
  AZURE_OPENAI_API_KEY \
  AZURE_OPENAI_API_VERSION \
  AZURE_OPENAI_DEPLOYMENT \
  DEFAULT_LLM_MODEL \
  AZURE_SQL_SERVER \
  AZURE_SQL_DB \
  AZURE_SQL_ADMIN \
  AZURE_SQL_PASSWORD \
  ACR_NAME \
  ACA_ENVIRONMENT \
  ACA_APP_NAME; do
  require_env "$required"
done

ACR_SKU="${ACR_SKU:-Basic}"
IMAGE_NAME="${IMAGE_NAME:-gemba-score-api}"
CONTAINER_MIN_REPLICAS="${CONTAINER_MIN_REPLICAS:-1}"
CONTAINER_MAX_REPLICAS="${CONTAINER_MAX_REPLICAS:-3}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
AZURE_SQL_LOCATION="${AZURE_SQL_LOCATION:-$AZURE_LOCATION}"

az account set --subscription "$AZURE_SUBSCRIPTION_ID"

echo "[deploy] Ensuring Azure resource providers are registered"
register_provider() {
  local namespace="$1"
  local state
  state=$(az provider show --namespace "$namespace" --query "registrationState" -o tsv || echo "NotRegistered")
  if [[ "$state" != "Registered" ]]; then
    az provider register --namespace "$namespace" --wait >/dev/null
  fi
}

register_provider "Microsoft.App"
register_provider "Microsoft.OperationalInsights"
register_provider "Microsoft.ContainerRegistry"
register_provider "Microsoft.Sql"

az extension add --name containerapp --upgrade >/dev/null
az extension add --name log-analytics --upgrade >/dev/null

az group create --name "$RESOURCE_GROUP" --location "$AZURE_LOCATION" >/dev/null

echo "[deploy] Using supplied Azure OpenAI configuration"
AZURE_OPENAI_KEY="$AZURE_OPENAI_API_KEY"

echo "[deploy] Creating / updating Azure SQL Server"
if ! az sql server show --name "$AZURE_SQL_SERVER" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az sql server create \
    --name "$AZURE_SQL_SERVER" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$AZURE_SQL_LOCATION" \
    --admin-user "$AZURE_SQL_ADMIN" \
    --admin-password "$AZURE_SQL_PASSWORD" \
    --enable-public-network true \
    --tags SecurityControl=Ignore >/dev/null
else
  az sql server update \
    --name "$AZURE_SQL_SERVER" \
    --resource-group "$RESOURCE_GROUP" \
    --set tags.SecurityControl=Ignore >/dev/null
fi
az sql server firewall-rule create \
  --resource-group "$RESOURCE_GROUP" \
  --server "$AZURE_SQL_SERVER" \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0 >/dev/null 2>&1 || true

if ! az sql db show --name "$AZURE_SQL_DB" --server "$AZURE_SQL_SERVER" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az sql db create \
    --name "$AZURE_SQL_DB" \
    --server "$AZURE_SQL_SERVER" \
    --resource-group "$RESOURCE_GROUP" \
    --tier GeneralPurpose \
    --family Gen5 \
    --capacity 2 \
    --compute-model Serverless \
    --auto-pause-delay 60 >/dev/null
fi

urlencode() {
  python3 - <<'PY' "$1"
import sys
from urllib.parse import quote_plus
print(quote_plus(sys.argv[1]))
PY
}

ENCODED_SQL_PASSWORD=$(urlencode "$AZURE_SQL_PASSWORD")
DATABASE_URL="mssql+aioodbc://${AZURE_SQL_ADMIN}:${ENCODED_SQL_PASSWORD}@${AZURE_SQL_SERVER}.database.windows.net:1433/${AZURE_SQL_DB}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"

echo "[deploy] Creating / updating Azure Container Registry"
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az acr create \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --sku "$ACR_SKU" \
    --location "$AZURE_LOCATION" \
    --admin-enabled true >/dev/null
else
  az acr update \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --admin-enabled true >/dev/null
fi

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "passwords[0].value" -o tsv)

IMAGE_REF="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "[deploy] Building container image ${IMAGE_REF} via ACR"
az acr build \
  --registry "$ACR_NAME" \
  --image "${IMAGE_NAME}:${IMAGE_TAG}" \
  --file Dockerfile \
  "$ROOT_DIR" >/dev/null

echo "[deploy] Ensuring Container Apps environment"
if ! az containerapp env show --name "$ACA_ENVIRONMENT" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp env create \
    --name "$ACA_ENVIRONMENT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$AZURE_LOCATION" \
    --logs-destination none >/dev/null
fi

ENV_VARS=(
  "AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}"
  "AZURE_OPENAI_API_KEY=secretref:azure-openai-key"
  "AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}"
  "AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}"
  "DEFAULT_LLM_MODEL=${DEFAULT_LLM_MODEL}"
  "DATABASE_URL=secretref:database-url"
  "APP_ENV=production"
  "LOG_LEVEL=INFO"
)

APP_EXISTS=true
if ! az containerapp show --name "$ACA_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
  APP_EXISTS=false
fi

if [[ "$APP_EXISTS" == false ]]; then
  echo "[deploy] Creating Container App ${ACA_APP_NAME}"
  az containerapp create \
    --name "$ACA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ACA_ENVIRONMENT" \
    --image "$IMAGE_REF" \
    --target-port 8000 \
    --ingress external \
    --min-replicas "$CONTAINER_MIN_REPLICAS" \
    --max-replicas "$CONTAINER_MAX_REPLICAS" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --secrets "azure-openai-key=$AZURE_OPENAI_KEY" "database-url=$DATABASE_URL" \
    --env-vars "${ENV_VARS[@]}" >/dev/null
else
  echo "[deploy] Updating Container App ${ACA_APP_NAME}"
  az containerapp secret set \
    --name "$ACA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --secrets "azure-openai-key=$AZURE_OPENAI_KEY" "database-url=$DATABASE_URL" >/dev/null

  az containerapp update \
    --name "$ACA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$IMAGE_REF" \
    --set-env-vars "${ENV_VARS[@]}" \
    --min-replicas "$CONTAINER_MIN_REPLICAS" \
    --max-replicas "$CONTAINER_MAX_REPLICAS" >/dev/null
  ACTIVE_REVISION=$(az containerapp revision list \
    --name "$ACA_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?properties.active==\`true\`].name | [0]" -o tsv 2>/dev/null || true)
  if [[ -n "$ACTIVE_REVISION" ]]; then
    az containerapp revision restart \
      --name "$ACA_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --revision "$ACTIVE_REVISION" >/dev/null
  fi
fi

APP_FQDN=$(az containerapp show --name "$ACA_APP_NAME" --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)

cat <<SUMMARY
------------------------------------------------------------
Deployment complete 
------------------------------------------------------------
Resource Group      : $RESOURCE_GROUP
Region              : $AZURE_LOCATION
Container App URL   : https://$APP_FQDN
Container Image     : $IMAGE_REF
Azure OpenAI Deploy : $AZURE_OPENAI_DEPLOYMENT @ $AZURE_OPENAI_ENDPOINT
SQL Database        : $AZURE_SQL_DB on $AZURE_SQL_SERVER
------------------------------------------------------------
SUMMARY
