$ErrorActionPreference = "Stop"

$installerUrl = "https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe"
$installerPath = "$env:TEMP\GoogleCloudSDKInstaller.exe"
$gcloudFolder = "$env:USERPROFILE\google-cloud-sdk"
$gcloudBin = "$gcloudFolder\bin\gcloud.cmd"

if (Test-Path $gcloudBin) {
    Write-Host "Google Cloud CLI is already installed at: $gcloudBin"
    & $gcloudBin --version
    exit 0
}

Write-Host "Starting Google Cloud CLI download and silent installation..."

# 1. Download installer
if (Test-Path $installerPath) {
    Write-Host "Using existing downloaded installer at $installerPath..."
} else {
    Write-Host "Downloading Google Cloud SDK installer..."
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UserAgent "Mozilla/5.0"
    Write-Host "Download complete."
}

# 2. Run installer silently
Write-Host "Installing silently to: $gcloudFolder"
if (Test-Path $gcloudFolder) {
    Write-Host "Removing existing partial install folder..."
    Remove-Item -Path $gcloudFolder -Recurse -Force -ErrorAction SilentlyContinue
}

# Note: /D must be the last argument and should NOT be quoted
$argList = @("/S", "/D=$gcloudFolder")
Write-Host "Running: Start-Process -FilePath $installerPath -ArgumentList `"/S`, `"/D=$gcloudFolder`" -Wait"
Start-Process -FilePath $installerPath -ArgumentList $argList -Wait -NoNewWindow
Write-Host "Installation process exited."

# 3. Verify
if (Test-Path $gcloudBin) {
    Write-Host "✅ Google Cloud CLI successfully installed!"
    & $gcloudBin --version | Select-Object -First 3
} else {
    # Check if maybe it installed in the default location
    $defaultGcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    if (Test-Path $defaultGcloud) {
        Write-Host "✅ Google Cloud CLI successfully installed in default location: $defaultGcloud"
        & $defaultGcloud --version | Select-Object -First 3
    } else {
        Write-Error "❌ gcloud.cmd was not found after installation at $gcloudBin or $defaultGcloud"
        exit 1
    }
}
