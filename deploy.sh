#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  AyuGuard — Cloud Run Deploy Script
#  Usage: bash deploy.sh
#  Requires: gcloud CLI authenticated, Docker running
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="silken-dogfish-484814-g9"
REGION="asia-south1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/ayuguard"
GCS_BUCKET="ayuguard-uploads-${PROJECT_ID}"

echo "=== AyuGuard Cloud Run Deployment ==="
echo "Project : $PROJECT_ID"
echo "Region  : $REGION"
echo "Registry: $REGISTRY"

# ── 1. Set project ───────────────────────────────────────────────
gcloud config set project "$PROJECT_ID"

# ── 2. Enable required APIs ──────────────────────────────────────
echo "→ Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  --quiet

# ── 3. Create Artifact Registry repo (idempotent) ───────────────
echo "→ Creating Artifact Registry repo..."
gcloud artifacts repositories create ayuguard \
  --repository-format=docker \
  --location="$REGION" \
  --description="AyuGuard container images" \
  --quiet 2>/dev/null || echo "  (repo already exists)"

# ── 4. Create GCS bucket (idempotent) ───────────────────────────
echo "→ Creating GCS bucket..."
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${GCS_BUCKET}" 2>/dev/null \
  || echo "  (bucket already exists)"

# ── 5. Store GOOGLE_API_KEY secret ──────────────────────────────
if [ -z "${GOOGLE_API_KEY:-}" ]; then
  echo "⚠️  GOOGLE_API_KEY env var not set. Set it before running deploy.sh"
  echo "   export GOOGLE_API_KEY=your_key_here"
  exit 1
fi
echo "→ Storing GOOGLE_API_KEY in Secret Manager..."
echo -n "$GOOGLE_API_KEY" | gcloud secrets create ayuguard-gemini-key \
  --data-file=- --quiet 2>/dev/null \
  || echo -n "$GOOGLE_API_KEY" | gcloud secrets versions add ayuguard-gemini-key \
  --data-file=- --quiet

# ── 6. Configure Docker auth ─────────────────────────────────────
echo "→ Configuring Docker auth for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── 7. Build & push agent image (Cloud Build) ────────────────────
echo "→ Building agent image in Google Cloud Build..."
mv Dockerfile.agent Dockerfile
if gcloud builds submit --tag "${REGISTRY}/ayuguard-agent:latest" --region "$REGION" --quiet .; then
  mv Dockerfile Dockerfile.agent
else
  mv Dockerfile Dockerfile.agent
  exit 1
fi

# ── 8. Build & push UI image (Cloud Build) ───────────────────────
echo "→ Building UI image in Google Cloud Build..."
mv Dockerfile.ui Dockerfile
if gcloud builds submit --tag "${REGISTRY}/ayuguard-ui:latest" --region "$REGION" --quiet .; then
  mv Dockerfile Dockerfile.ui
else
  mv Dockerfile Dockerfile.ui
  exit 1
fi

# ── 9. Deploy agent service (internal) ──────────────────────────
echo "→ Deploying ayuguard-agent..."
gcloud run deploy ayuguard-agent \
  --image "${REGISTRY}/ayuguard-agent:latest" \
  --platform managed \
  --region "$REGION" \
  --ingress all \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 3 \
  --set-secrets "GOOGLE_API_KEY=ayuguard-gemini-key:latest" \
  --set-env-vars "GCS_BUCKET=${GCS_BUCKET},GOOGLE_GENAI_USE_VERTEXAI=FALSE" \
  --quiet

AGENT_URL=$(gcloud run services describe ayuguard-agent \
  --region "$REGION" --format "value(status.url)")
echo "  Agent URL: $AGENT_URL"

# ── 10. Deploy UI service (public) ──────────────────────────────
echo "→ Deploying ayuguard-ui..."
gcloud run deploy ayuguard-ui \
  --image "${REGISTRY}/ayuguard-ui:latest" \
  --platform managed \
  --region "$REGION" \
  --ingress all \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --min-instances 0 \
  --max-instances 5 \
  --set-secrets "GOOGLE_API_KEY=ayuguard-gemini-key:latest" \
  --set-env-vars "ADK_BASE_URL=${AGENT_URL},GCS_BUCKET=${GCS_BUCKET},GOOGLE_GENAI_USE_VERTEXAI=FALSE" \
  --quiet

UI_URL=$(gcloud run services describe ayuguard-ui \
  --region "$REGION" --format "value(status.url)")

echo ""
echo "======================================================"
echo "  ✅  AyuGuard deployed successfully!"
echo "======================================================"
echo "  🌐  UI URL  : $UI_URL"
echo "  🤖  Agent   : $AGENT_URL (internal)"
echo "======================================================"
