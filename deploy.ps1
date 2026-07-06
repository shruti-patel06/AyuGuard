# ─────────────────────────────────────────────────────────────────
#  AyuGuard — Cloud Run PowerShell Deploy Script
#  Requires: gcloud CLI authenticated, Docker running
# ─────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

# Prepend gcloud bin directory to process-level PATH so docker push can find docker-credential-gcloud helper
$GCLOUD_BIN_DIR = "C:\Users\Shruti\google-cloud-sdk\google-cloud-sdk\bin"
$env:Path = "$GCLOUD_BIN_DIR;$env:Path"

$PROJECT_ID = "silken-dogfish-484814-g9"
$REGION = "asia-south1"
$REGISTRY = "${REGION}-docker.pkg.dev/${PROJECT_ID}/ayuguard"
$GCS_BUCKET = "ayuguard-uploads-${PROJECT_ID}"
$GCLOUD = "$GCLOUD_BIN_DIR\gcloud.cmd"
$GSUTIL = "$GCLOUD_BIN_DIR\gsutil.cmd"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " 🚀 AyuGuard Cloud Run PowerShell Deployment" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "Project : $PROJECT_ID"
Write-Host "Region  : $REGION"
Write-Host "Registry: $REGISTRY"
Write-Host "Bucket  : gs://$GCS_BUCKET"
Write-Host "PATH    : (Successfully appended gcloud bin)"
Write-Host "======================================================"

# ── 1. Set project ───────────────────────────────────────────────
Write-Host "→ Setting active project..." -ForegroundColor Yellow
& $GCLOUD config set project $PROJECT_ID

# ── 2. Enable required APIs ──────────────────────────────────────
Write-Host "→ Enabling required GCP APIs..." -ForegroundColor Yellow
& $GCLOUD services enable `
  run.googleapis.com `
  artifactregistry.googleapis.com `
  storage.googleapis.com `
  secretmanager.googleapis.com `
  cloudbuild.googleapis.com `
  --quiet

# ── 3. Create Artifact Registry repo (idempotent) ───────────────
Write-Host "→ Checking if Artifact Registry repository exists..." -ForegroundColor Yellow
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$null = & $GCLOUD artifacts repositories describe ayuguard --location=$REGION --quiet 2>$null
$repoExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $oldEAP

if (-not $repoExists) {
    Write-Host "  Creating Artifact Registry repository..." -ForegroundColor Yellow
    & $GCLOUD artifacts repositories create ayuguard `
      --repository-format=docker `
      --location=$REGION `
      --description="AyuGuard container images" `
      --quiet
    Write-Host "  Repository created successfully." -ForegroundColor Green
} else {
    Write-Host "  (repository already exists)" -ForegroundColor Gray
}

# ── 4. Create GCS bucket (idempotent) ───────────────────────────
Write-Host "→ Checking if GCS Bucket exists..." -ForegroundColor Yellow
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$null = & $GSUTIL ls "gs://$GCS_BUCKET" 2>$null
$bucketExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $oldEAP

if (-not $bucketExists) {
    Write-Host "  Creating GCS Bucket..." -ForegroundColor Yellow
    & $GSUTIL mb -p $PROJECT_ID -l $REGION "gs://$GCS_BUCKET"
    Write-Host "  Bucket created successfully." -ForegroundColor Green
} else {
    Write-Host "  (bucket already exists)" -ForegroundColor Gray
}

# ── 5. Retrieve GOOGLE_API_KEY from .env ────────────────────────
Write-Host "→ Extracting GOOGLE_API_KEY from .env file..." -ForegroundColor Yellow
$apiKey = $null
$envFile = "ayuguard\.env"
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    foreach ($line in $envContent) {
        if ($line -match "^GOOGLE_API_KEY=(.+)$") {
            $apiKey = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
}

if (-not $apiKey) {
    Write-Error "❌ GOOGLE_API_KEY was not found in $envFile! Please set it before deploying."
    exit 1
}

Write-Host "  API Key extracted successfully: $($apiKey.Substring(0, 8))..." -ForegroundColor Green

# ── 6. Store GOOGLE_API_KEY in Secret Manager ──────────────────
Write-Host "→ Checking if secret 'ayuguard-gemini-key' exists..." -ForegroundColor Yellow
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$null = & $GCLOUD secrets describe ayuguard-gemini-key --quiet 2>$null
$secretExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $oldEAP

if (-not $secretExists) {
    Write-Host "  Creating new secret 'ayuguard-gemini-key'..." -ForegroundColor Yellow
    & $GCLOUD secrets create ayuguard-gemini-key --replication-policy=automatic --quiet
}

Write-Host "  Adding secret version..."
# Pass the API key securely to gcloud secrets versions add via stdin
$utf8Key = [System.Text.Encoding]::UTF8.GetBytes($apiKey)
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = $GCLOUD
$processInfo.Arguments = "secrets versions add ayuguard-gemini-key --data-file=- --quiet"
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardInput = $true
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true

$process = [System.Diagnostics.Process]::Start($processInfo)
$process.StandardInput.BaseStream.Write($utf8Key, 0, $utf8Key.Length)
$process.StandardInput.Close()
$output = $process.StandardOutput.ReadToEnd()
$errorOutput = $process.StandardError.ReadToEnd()
$process.WaitForExit()

if ($process.ExitCode -ne 0) {
    Write-Error "❌ Failed to store secret: $errorOutput"
    exit 1
}
Write-Host "  Secret stored successfully." -ForegroundColor Green

# ── 6b. Grant Secret Accessor role to Compute Service Account ───
Write-Host "→ Granting Secret Accessor role to Compute Service Account..." -ForegroundColor Yellow
$PROJECT_NUMBER = (& $GCLOUD projects describe $PROJECT_ID --format="value(projectNumber)").Trim()
& $GCLOUD projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$($PROJECT_NUMBER)-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor" `
  --quiet
Write-Host "  Secret Accessor role granted successfully." -ForegroundColor Green

# ── 7. Configure Docker Auth ────────────────────────────────────
Write-Host "→ Configuring Docker authentication for Artifact Registry..." -ForegroundColor Yellow
& $GCLOUD auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── 8. Build & Push Agent Image (Cloud Build) ───────────────────
Write-Host "→ Building Agent image in Google Cloud Build..." -ForegroundColor Yellow
Rename-Item -Path Dockerfile.agent -NewName Dockerfile
try {
    & $GCLOUD builds submit --tag "${REGISTRY}/ayuguard-agent:latest" --region $REGION --quiet .
} finally {
    Rename-Item -Path Dockerfile -NewName Dockerfile.agent
}

# ── 9. Build & Push UI Image (Cloud Build) ──────────────────────
Write-Host "→ Building UI image in Google Cloud Build..." -ForegroundColor Yellow
Rename-Item -Path Dockerfile.ui -NewName Dockerfile
try {
    & $GCLOUD builds submit --tag "${REGISTRY}/ayuguard-ui:latest" --region $REGION --quiet .
} finally {
    Rename-Item -Path Dockerfile -NewName Dockerfile.ui
}

# ── 10. Deploy Agent Service ────────────────────
Write-Host "→ Deploying ayuguard-agent..." -ForegroundColor Yellow
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
  --set-secrets "GOOGLE_API_KEY=ayuguard-gemini-key:latest" `
  --set-env-vars "GCS_BUCKET=${GCS_BUCKET},GOOGLE_GENAI_USE_VERTEXAI=FALSE" `
  --quiet

# Get Agent internal URL
$AGENT_URL = (& $GCLOUD run services describe ayuguard-agent --region $REGION --format "value(status.url)").Trim()
Write-Host "  Agent URL: $AGENT_URL" -ForegroundColor Green

# ── 11. Deploy UI Service (publicly accessible) ──────────────────
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
  --set-env-vars "ADK_BASE_URL=${AGENT_URL},GCS_BUCKET=${GCS_BUCKET},GOOGLE_GENAI_USE_VERTEXAI=FALSE" `
  --quiet

# Get UI public URL
$UI_URL = (& $GCLOUD run services describe ayuguard-ui --region $REGION --format "value(status.url)").Trim()

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  ✅ AyuGuard Deployed Successfully on Cloud Run!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  🌐  UI URL  : $UI_URL" -ForegroundColor Green
Write-Host "  🤖  Agent   : $AGENT_URL (internal)" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
