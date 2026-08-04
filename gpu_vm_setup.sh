#!/bin/bash
# ============================================================
# AyuGuard — GPU VM Quick Setup (pip-based, CUDA 12.x / L4)
# ============================================================
set -e

VM_ZONE="asia-southeast1-b"
REPO="https://github.com/shruti-patel06/AyuGuard.git"
APP_DIR="$HOME/ayuguard-care-platform"

echo "=================================================="
echo "  AyuGuard GPU Analytics — Quick Setup (L4/pip)"
echo "=================================================="

# 1 — Verify GPU
echo "[1/6] Verifying NVIDIA GPU..."
nvidia-smi || { echo "ERROR: nvidia-smi not found. Use a Deep Learning VM image."; exit 1; }
echo "   ✅ GPU detected."

# 2 — Install Python deps via pip (fast, no conda needed)
echo "[2/6] Installing dependencies via pip..."
pip install --quiet --upgrade pip
pip install --quiet \
    "cudf-cu12==24.12.*" \
    --extra-index-url=https://pypi.nvidia.com \
    || echo "   ⚠️  cudf-cu12 install failed — will use CPU fallback"
pip install --quiet fastapi uvicorn[standard] httpx numpy pandas

echo "   ✅ Dependencies installed."

# 3 — Clone / update repo
echo "[3/6] Cloning AyuGuard repository..."
if [ -d "$APP_DIR" ]; then
    echo "   Repo exists — pulling latest..."
    cd "$APP_DIR" && git pull origin main
else
    git clone "$REPO" "$APP_DIR"
fi
echo "   ✅ Repo ready at $APP_DIR."

# 4 — Create systemd service
echo "[4/6] Creating systemd service..."
PYTHON_BIN=$(which python3)
sudo tee /etc/systemd/system/ayuguard-analytics.service > /dev/null <<EOF
[Unit]
Description=AyuGuard NVIDIA RAPIDS Analytics Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PYTHONPATH=$APP_DIR"
ExecStart=$PYTHON_BIN -m uvicorn ayuguard.analytics.benchmark_server:app --host 0.0.0.0 --port 8080 --workers 1
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ayuguard-analytics
sudo systemctl restart ayuguard-analytics
echo "   ✅ Service started."

# 5 — Wait and health check
echo "[5/6] Waiting for service to be ready..."
sleep 5
for i in {1..10}; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health || true)
    if [ "$STATUS" = "200" ]; then
        echo "   ✅ Service is healthy!"
        break
    fi
    echo "   Waiting ($i/10)..."
    sleep 3
done

# 6 — Print summary
EXTERNAL_IP=$(curl -s -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)

echo ""
echo "=================================================="
echo "  ✅ AyuGuard GPU Analytics Setup Complete!"
echo ""
echo "  External IP : $EXTERNAL_IP"
echo "  Health:       curl http://$EXTERNAL_IP:8080/health"
echo "  Benchmark:    curl http://$EXTERNAL_IP:8080/benchmark"
echo ""
echo "  ⚠️  Now update server.py GPU_VM_URL to:"
echo "      http://$EXTERNAL_IP:8080"
echo "=================================================="
echo ""
echo "  ⚠️  STOP VM WHEN DONE (saves ~\$0.70/hr):"
echo "  gcloud compute instances stop ayuguard-gpu-vm-sg --zone=$VM_ZONE"
echo "=================================================="
