#!/bin/bash
# ============================================================
# AyuGuard — Google Cloud GPU VM Setup Script
# NVIDIA T4 GPU + NVIDIA RAPIDS cuDF
# ============================================================
# Run this ONCE on the GPU VM after it is created.
# Usage:
#   chmod +x gpu_vm_setup.sh
#   ./gpu_vm_setup.sh
# ============================================================

set -e
echo "=================================================="
echo "  AyuGuard GPU VM Setup — NVIDIA RAPIDS cuDF"
echo "=================================================="

# Step 1: Update system
echo "[1/7] Updating system packages..."
sudo apt-get update -q && sudo apt-get upgrade -yq

# Step 2: Install CUDA Toolkit (if not present)
echo "[2/7] Checking NVIDIA CUDA..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "   nvidia-smi not found. Please use a Deep Learning VM image with CUDA pre-installed."
    echo "   Recommended: 'pytorch-latest-gpu' or 'common-cu121' image family."
    exit 1
fi
nvidia-smi
echo "   ✅ CUDA/GPU detected."

# Step 3: Install Miniconda (if not present)
echo "[3/7] Setting up Conda..."
if ! command -v conda &> /dev/null; then
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p $HOME/miniconda3
    eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
    conda init bash
    source ~/.bashrc
fi
echo "   ✅ Conda ready."

# Step 4: Create RAPIDS conda environment
echo "[4/7] Creating RAPIDS conda environment..."
conda create -n rapids -c rapidsai -c conda-forge -c nvidia \
    rapids=24.12 python=3.11 cuda-version=12.1 \
    fastapi uvicorn httpx numpy -y
echo "   ✅ RAPIDS environment created."

# Step 5: Clone the AyuGuard repo
echo "[5/7] Cloning AyuGuard repository..."
if [ -d "ayuguard-care-platform" ]; then
    echo "   Repo already exists — pulling latest..."
    cd ayuguard-care-platform && git pull origin main && cd ..
else
    git clone https://github.com/shruti-patel06/AyuGuard.git ayuguard-care-platform
fi
echo "   ✅ AyuGuard repo ready."

# Step 6: Create systemd service for the analytics endpoint
echo "[6/7] Creating systemd service for AyuGuard Analytics..."
sudo tee /etc/systemd/system/ayuguard-analytics.service > /dev/null <<EOF
[Unit]
Description=AyuGuard NVIDIA RAPIDS Analytics Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/ayuguard-care-platform
Environment="PATH=$HOME/miniconda3/envs/rapids/bin:$PATH"
ExecStart=$HOME/miniconda3/envs/rapids/bin/python -m uvicorn ayuguard.analytics.benchmark_server:app --host 0.0.0.0 --port 8080 --workers 1
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ayuguard-analytics
sudo systemctl start ayuguard-analytics
echo "   ✅ Analytics service started on port 8080."

# Step 7: Open firewall port 8080 (if using gcloud)
echo "[7/7] Opening firewall port 8080..."
gcloud compute firewall-rules create ayuguard-analytics-port \
    --allow tcp:8080 \
    --source-ranges 0.0.0.0/0 \
    --description "AyuGuard RAPIDS Analytics Service" 2>/dev/null || \
    echo "   (Firewall rule already exists or gcloud not configured — skip)"

echo ""
echo "=================================================="
echo "  ✅ AyuGuard GPU Analytics Setup Complete!"
echo "  Test it: curl http://$(curl -s ifconfig.me):8080/health"
echo "  Benchmark: curl http://$(curl -s ifconfig.me):8080/benchmark"
echo "=================================================="
echo ""
echo "  ⚠️  IMPORTANT: Stop this VM when not in use!"
echo "  Command: gcloud compute instances stop INSTANCE_NAME --zone=ZONE"
echo "=================================================="
