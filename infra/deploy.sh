#!/usr/bin/env bash
# VaaniSetu - provisions and deploys everything on Google Cloud.
# Run from Google Cloud Shell (gcloud is pre-installed and signed in):
#   git clone https://github.com/17mohak/vaanisetu && cd vaanisetu && bash infra/deploy.sh
# Re-runnable. Optional: PROJECT=<existing-project-id> bash infra/deploy.sh
set -euo pipefail

REGION=asia-south1            # Mumbai: function, storage, Firestore
GW_REGION=asia-northeast1     # closest region where API Gateway is offered
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
TMP=$(mktemp -d)

# ------------------------------------------------------------------ project & billing
PROJECT=${PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  PROJECT="vaanisetu-$(date +%s | tail -c 7)"
  echo "== Creating project $PROJECT"
  gcloud projects create "$PROJECT" --name="VaaniSetu"
fi
gcloud config set project "$PROJECT" >/dev/null
if [ "$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)')" != "True" ]; then
  BILLING=$(gcloud billing accounts list --filter=open=true --format='value(name)' --limit=1)
  [ -n "$BILLING" ] || { echo "No open billing account. Start the free trial in the console first."; exit 1; }
  echo "== Linking billing account $BILLING"
  gcloud billing projects link "$PROJECT" --billing-account="$BILLING"
fi
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')

echo "== Enabling APIs"
gcloud services enable \
  cloudfunctions.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com storage.googleapis.com firestore.googleapis.com \
  vision.googleapis.com texttospeech.googleapis.com aiplatform.googleapis.com \
  apigateway.googleapis.com servicemanagement.googleapis.com servicecontrol.googleapis.com \
  iamcredentials.googleapis.com logging.googleapis.com billingbudgets.googleapis.com

MEDIA=vaanisetu-media-$PROJECT
WEB=vaanisetu-web-$PROJECT
FN=vaanisetu-api
FN_SA=vaanisetu-fn@$PROJECT.iam.gserviceaccount.com
GW_SA=vaanisetu-gateway@$PROJECT.iam.gserviceaccount.com
BUILD_SA=vaanisetu-build@$PROJECT.iam.gserviceaccount.com

# ------------------------------------------------------------------ storage
echo "== Cloud Storage"
gcloud storage buckets describe "gs://$MEDIA" >/dev/null 2>&1 || gcloud storage buckets create "gs://$MEDIA" \
  --location="$REGION" --uniform-bucket-level-access --public-access-prevention
cat > "$TMP/cors.json" <<'JSON'
[{"origin": ["*"], "method": ["PUT", "GET"], "responseHeader": ["Content-Type"], "maxAgeSeconds": 3000}]
JSON
cat > "$TMP/lifecycle.json" <<'JSON'
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 30, "matchesPrefix": ["uploads/"]}}]}
JSON
gcloud storage buckets update "gs://$MEDIA" --cors-file="$TMP/cors.json" --lifecycle-file="$TMP/lifecycle.json"

echo "== Firestore"
gcloud firestore databases describe --database='(default)' >/dev/null 2>&1 || \
  gcloud firestore databases create --location="$REGION" --type=firestore-native

# ------------------------------------------------------------------ IAM (least privilege)
echo "== Service accounts and roles"
for sa in vaanisetu-fn:"VaaniSetu function" vaanisetu-gateway:"VaaniSetu API Gateway" vaanisetu-build:"VaaniSetu function builds"; do
  id=${sa%%:*}; name=${sa#*:}
  gcloud iam service-accounts describe "$id@$PROJECT.iam.gserviceaccount.com" >/dev/null 2>&1 || \
    gcloud iam service-accounts create "$id" --display-name="$name"
done
sleep 5
for role in roles/datastore.user roles/aiplatform.user roles/serviceusage.serviceUsageConsumer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$FN_SA" --role="$role" \
    --condition=None >/dev/null
done
for role in roles/storage.objectCreator roles/storage.objectViewer; do
  gcloud storage buckets add-iam-policy-binding "gs://$MEDIA" --member="serviceAccount:$FN_SA" --role="$role" >/dev/null
done
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$BUILD_SA" \
  --role=roles/cloudbuild.builds.builder --condition=None >/dev/null
# lets the function sign Cloud Storage URLs with its own identity (IAM signBlob)
gcloud iam service-accounts add-iam-policy-binding "$FN_SA" --member="serviceAccount:$FN_SA" \
  --role=roles/iam.serviceAccountTokenCreator >/dev/null

# ------------------------------------------------------------------ Gemini model
echo "== Picking a Gemini model available to this project"
TOKEN=$(gcloud auth print-access-token)
MODEL_ID=""
# Flash-Lite first: in infra/bench_models.sh it was ~4x faster than Flash on this task
# with valid output, and it is the cheapest model.
for m in ${MODEL_ID_OVERRIDE:-gemini-3.5-flash-lite gemini-3.1-flash-lite gemini-3.5-flash gemini-2.5-flash-lite gemini-2.5-flash}; do
  code=$(curl -s -o "$TMP/probe.json" -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/global/publishers/google/models/$m:generateContent" \
    -d '{"contents":[{"role":"user","parts":[{"text":"Reply with OK"}]}],"generationConfig":{"maxOutputTokens":8}}')
  if [ "$code" = "200" ]; then MODEL_ID=$m; break; fi
  echo "   $m -> HTTP $code"
done
[ -n "$MODEL_ID" ] || { echo "No Gemini model reachable"; cat "$TMP/probe.json"; exit 1; }
echo "   using $MODEL_ID"

# ------------------------------------------------------------------ Cloud Run function
echo "== Cloud Run function"
gcloud functions deploy "$FN" --gen2 --region="$REGION" --runtime=python312 \
  --source="$ROOT/backend" --entry-point=api --trigger-http --no-allow-unauthenticated \
  --service-account="$FN_SA" --build-service-account="projects/$PROJECT/serviceAccounts/$BUILD_SA" --memory=512Mi --timeout=60s --min-instances=0 --max-instances=3 \
  --set-env-vars="MEDIA_BUCKET=$MEDIA,MODEL_ID=$MODEL_ID,MODEL_LOCATION=global" --quiet
FN_URL=$(gcloud functions describe "$FN" --gen2 --region="$REGION" --format='value(serviceConfig.uri)')
gcloud functions add-invoker-policy-binding "$FN" --gen2 --region="$REGION" \
  --member="serviceAccount:$GW_SA" >/dev/null

# ------------------------------------------------------------------ API Gateway
echo "== API Gateway"
sed "s#__FUNCTION_URL__#$FN_URL#" "$HERE/openapi.template.yaml" > "$TMP/openapi.yaml"
gcloud api-gateway apis describe vaanisetu-api >/dev/null 2>&1 || gcloud api-gateway apis create vaanisetu-api
CONFIG=vaanisetu-config-$(date +%Y%m%d%H%M%S)
gcloud api-gateway api-configs create "$CONFIG" --api=vaanisetu-api \
  --openapi-spec="$TMP/openapi.yaml" --backend-auth-service-account="$GW_SA"
if gcloud api-gateway gateways describe vaanisetu-gateway --location="$GW_REGION" >/dev/null 2>&1; then
  gcloud api-gateway gateways update vaanisetu-gateway --api=vaanisetu-api --api-config="$CONFIG" --location="$GW_REGION"
else
  gcloud api-gateway gateways create vaanisetu-gateway --api=vaanisetu-api --api-config="$CONFIG" --location="$GW_REGION"
fi
API_URL="https://$(gcloud api-gateway gateways describe vaanisetu-gateway --location="$GW_REGION" --format='value(defaultHostname)')"
echo "API: $API_URL"

# ------------------------------------------------------------------ frontend
echo "== Frontend -> Cloud Storage static hosting"
gcloud storage buckets describe "gs://$WEB" >/dev/null 2>&1 || gcloud storage buckets create "gs://$WEB" \
  --location="$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://$WEB" --web-main-page-suffix=index.html >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$WEB" --member=allUsers --role=roles/storage.objectViewer >/dev/null
sed "s#__API_URL__#$API_URL#" "$ROOT/frontend/config.template.js" > "$ROOT/frontend/config.js"
gcloud storage rsync "$ROOT/frontend" "gs://$WEB" --recursive --delete-unmatched-destination-objects \
  --exclude='config\.template\.js$' --cache-control="public, max-age=60"

# ------------------------------------------------------------------ budget guard
BILLING=$(gcloud billing projects describe "$PROJECT" --format='value(billingAccountName)' | sed 's#billingAccounts/##')
if ! gcloud billing budgets list --billing-account="$BILLING" --format='value(displayName)' 2>/dev/null | grep -qx vaanisetu; then
  # budgets must use the billing account's own currency (INR for Indian accounts)
  CURRENCY=$(gcloud billing accounts describe "$BILLING" --format='value(currencyCode)')
  if [ "$CURRENCY" = "INR" ]; then AMOUNT=400INR; else AMOUNT=5${CURRENCY:-USD}; fi
  gcloud billing budgets create --billing-account="$BILLING" --display-name=vaanisetu \
    --budget-amount="$AMOUNT" --filter-projects="projects/$PROJECT" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 >/dev/null \
    && echo "== Budget alert set at $AMOUNT" || echo "== (budget alert skipped)"
fi

echo
echo "Project: $PROJECT ($PROJECT_NUMBER)"
echo "API:     $API_URL"
echo "Site:    https://storage.googleapis.com/$WEB/index.html"
