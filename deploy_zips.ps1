# ─────────────────────────────────────────────────────────────────
#  AyuGuard — Cloud Run PowerShell Zip-Based Deploy Script
#  Avoids Windows file locking issues in gcloud.
# ─────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

# Prepend gcloud bin directory to process-level PATH
$GCLOUD_BIN_DIR = "C:\Users\Shruti\google-cloud-sdk\google-cloud-sdk\bin"
$env:Path = "$GCLOUD_BIN_DIR;$env:Path"

$PROJECT_ID = "silken-dogfish-484814-g9"
$REGION = "asia-south1"              # Cloud Run infrastructure region
$VERTEX_LOCATION = "us-central1"     # Vertex AI Gemini model region
$REGISTRY = "${REGION}-docker.pkg.dev/${PROJECT_ID}/ayuguard"
$GCS_BUCKET = "ayuguard-uploads-${PROJECT_ID}"
$GCLOUD = "$GCLOUD_BIN_DIR\gcloud.cmd"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " 🚀 AyuGuard Cloud Run Zip-Based PowerShell Deployment" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "Project : $PROJECT_ID"
Write-Host "Region  : $REGION"
Write-Host "Registry: $REGISTRY"
Write-Host "Bucket  : gs://$GCS_BUCKET"
Write-Host "======================================================"

# ── 1. Set project ───────────────────────────────────────────────
Write-Host "→ Setting active project..." -ForegroundColor Yellow
& $GCLOUD config set project $PROJECT_ID

# ── 2. Build Agent Image in Cloud Build ───────────────────────────
Write-Host "→ Building Agent image in Google Cloud Build from project_agent.zip..." -ForegroundColor Yellow
& $GCLOUD builds submit --tag "${REGISTRY}/ayuguard-agent:latest" --region $REGION --quiet project_agent.zip

# ── 3. Build UI Image in Cloud Build ──────────────────────────────
Write-Host "→ Building UI image in Google Cloud Build from project_ui.zip..." -ForegroundColor Yellow
& $GCLOUD builds submit --tag "${REGISTRY}/ayuguard-ui:latest" --region $REGION --quiet project_ui.zip

# ── 4. Deploy Agent Service (Vertex AI backend — no API key needed) ──
Write-Host "→ Deploying ayuguard-agent (Vertex AI backend)..." -ForegroundColor Yellow
& $GCLOUD run deploy ayuguard-agent `
  --image "${REGISTRY}/ayuguard-agent:latest" `
  --platform managed `
  --region $REGION `
  --ingress all `
  --allow-unauthenticated `
  --memory 2Gi `
  --cpu 2 `
  --timeout 300 `
  --min-instances 0 `
  --max-instances 3 `
  --set-env-vars "GCS_BUCKET=${GCS_BUCKET},GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${VERTEX_LOCATION}" `
  --quiet

$AGENT_URL = (& $GCLOUD run services describe ayuguard-agent --region $REGION --format "value(status.url)").Trim()
Write-Host "  Agent URL: $AGENT_URL" -ForegroundColor Green

# ── 5. Deploy UI Service (publicly accessible) ──────────────────
Write-Host "→ Deploying ayuguard-ui (Public)..." -ForegroundColor Yellow
& $GCLOUD run deploy ayuguard-ui `
  --image "${REGISTRY}/ayuguard-ui:latest" `
  --platform managed `
  --region $REGION `
  --ingress all `
  --allow-unauthenticated `
  --memory 1Gi `
  --cpu 1 `
  --timeout 300 `
  --min-instances 0 `
  --max-instances 5 `
  --set-secrets "GOOGLE_API_KEY=ayuguard-gemini-key:latest" `
  --set-env-vars "ADK_BASE_URL=${AGENT_URL},GCS_BUCKET=${GCS_BUCKET},GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${VERTEX_LOCATION}" `
  --quiet

$UI_URL = (& $GCLOUD run services describe ayuguard-ui --region $REGION --format "value(status.url)").Trim()

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  ✅ AyuGuard Deployed Successfully on Cloud Run!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  🌐  UI URL  : $UI_URL" -ForegroundColor Green
Write-Host "  🤖  Agent   : $AGENT_URL (internal)" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
