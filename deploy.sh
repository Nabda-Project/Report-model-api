#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# Med Report API — EC2 Deployment Script
# Run this ON the EC2 instance after SSH-ing in
# ═══════════════════════════════════════════════════════════════════════

# ── Step 0: What you need BEFORE running this ─────────────────────────
# 1. Launch an EC2 instance from the AWS Console:
#    - AMI: Amazon Linux 2023 or Ubuntu 24.04
#    - Instance type: t3.xlarge (4 vCPU, 16 GB RAM) — needed for the model
#    - Storage: 30 GB gp3
#    - Security group: allow inbound TCP 8000 from anywhere (0.0.0.0/0)
#    - Key pair: your existing key or create a new one
#    - Elastic IP: allocate one and associate it (so the IP never changes)
#
# 2. SSH into the instance:
#    ssh -i your-key.pem ec2-user@<your-elastic-ip>    # Amazon Linux
#    ssh -i your-key.pem ubuntu@<your-elastic-ip>       # Ubuntu
#
# 3. Copy this script to the instance and run it:
#    chmod +x deploy.sh
#    ./deploy.sh

set -e

echo "══════════════════════════════════════════════"
echo "  Med Report API — EC2 Setup"
echo "══════════════════════════════════════════════"

# ── Step 1: Install Docker ────────────────────────────────────────────
echo "[1/4] Installing Docker..."

if command -v apt-get &> /dev/null; then
    # Ubuntu
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
elif command -v yum &> /dev/null; then
    # Amazon Linux
    sudo yum update -y
    sudo yum install -y docker
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker $USER
fi

echo "Docker installed."

# ── Step 2: Build the image ───────────────────────────────────────────
echo "[2/4] Building Docker image..."

# Validate required environment variables
MISSING=""
[ -z "$HF_TOKEN" ]   && MISSING="$MISSING HF_TOKEN"
[ -z "$HF_REPO_ID" ] && MISSING="$MISSING HF_REPO_ID"

if [ -n "$MISSING" ]; then
    echo "❌ Error: required environment variable(s) not set:$MISSING"
    echo "   Export them before running this script:"
    echo "     export HF_TOKEN=your_token"
    echo "     export HF_REPO_ID=your-username/qwen3-doctor"
    exit 1
fi

# Clone your repo or copy files — adjust this to your repo URL
# git clone https://github.com/your-username/Report-model-api.git
# cd Report-model-api

sudo docker build \
    --build-arg HF_TOKEN="$HF_TOKEN" \
    --build-arg HF_REPO_ID="$HF_REPO_ID" \
    -t med-report-api:latest .

echo "Image built successfully."

# ── Step 3: Run the container ─────────────────────────────────────────
echo "[3/4] Starting container..."

# Validate required environment variable
if [ -z "$API_KEY" ]; then
    echo "❌ Error: required environment variable API_KEY is not set."
    echo "   Export it before running this script:"
    echo "     export API_KEY=your_secret_key"
    exit 1
fi

# Stop old container if running
sudo docker stop med-report-api 2>/dev/null || true
sudo docker rm med-report-api 2>/dev/null || true

sudo docker run -d \
    --name med-report-api \
    --restart unless-stopped \
    -p 8000:8000 \
    -e API_KEY="$API_KEY" \
    med-report-api:latest

echo "Container started."

# ── Step 4: Verify ────────────────────────────────────────────────────
echo "[4/4] Waiting for model to load (this takes 30-60 seconds)..."
sleep 10

for i in {1..12}; do
    if curl -s http://localhost:8000/health | grep -q "ok"; then
        echo ""
        echo "══════════════════════════════════════════════"
        echo "  ✅ API is live!"
        echo ""
        echo "  Health:   http://$(curl -s ifconfig.me):8000/health"
        echo "  Generate: POST http://$(curl -s ifconfig.me):8000/generate"
        echo "  Result:   GET  http://$(curl -s ifconfig.me):8000/result/{job_id}"
        echo "══════════════════════════════════════════════"
        exit 0
    fi
    echo "  Still loading... ($((i*5))s)"
    sleep 5
done

echo "⚠️  API didn't respond in 60s. Check logs with: docker logs med-report-api"
