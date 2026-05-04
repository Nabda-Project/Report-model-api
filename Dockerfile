FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including cmake and build tools for llama-cpp-python
RUN apt-get update && apt-get install -y \
    git \
    curl \
    cmake \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download model from HuggingFace at build time
ARG HF_TOKEN
ARG HF_REPO_ID

RUN python -c "\
from huggingface_hub import snapshot_download; \
import os; \
snapshot_download( \
    repo_id=os.environ.get('HF_REPO_ID', '${HF_REPO_ID}'), \
    local_dir='/app/model', \
    token=os.environ.get('HF_TOKEN', '${HF_TOKEN}'), \
    revision='q4_k_m-gguf' \
)"

# Copy app code
COPY app.py .

# Environment variables (overridden at runtime via Azure secrets)
ENV MODEL_PATH=/app/model
ENV API_KEY=change-me-please

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]