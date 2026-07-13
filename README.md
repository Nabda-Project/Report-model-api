# 🩺 Med Report API

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python)](https://www.python.org)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?style=for-the-badge&logo=huggingface)](https://huggingface.co)

An asynchronous REST API serving a fine-tuned **Qwen3 (Qwen 1.5/2.5/3)** medical assistant model for clinical report generation. It accepts unstructured text inputs (like raw doctor notes or patient transcripts) and outputs a highly structured JSON medical report containing symptoms, diagnoses, medications, and clinical notes.

This API uses **llama.cpp** for high-performance GGUF inference, constrained by **JSON Schema Grammar** to guarantee that the output always matches the expected schema. It uses an **in-memory background job queue** so that heavy LLM inference does not block incoming requests.

---

## 🏗️ Architecture & How It Works

To support high concurrency and prevent blocking, the API employs a non-blocking background queue model:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Frontend Client
    participant API as FastAPI Gateway
    participant Queue as Memory Job Queue
    participant Worker as Background Worker
    participant LLM as llama.cpp Engine

    Client->>API: POST /generate (Unstructured text + API Key)
    Note over API: Verifies API Key
    API->>Queue: Push Job to Queue (UUID, status: "queued")
    API-->>Client: 200 OK (job_id, status: "queued", poll_url)
    
    loop Polling
        Client->>API: GET /result/{job_id} (API Key)
        API-->>Client: 200 OK (status: "queued" or "processing")
    end

    Queue->>Worker: Pull job from queue (FIFO)
    Worker->>LLM: Start generation with Pydantic JSON Grammar
    Note over LLM: Generation constrained to JSON schema
    LLM-->>Worker: Constrained JSON text
    Note over Worker: Extracts & validates structured JSON
    Worker->>API: Update job in-memory cache (status: "completed")

    Client->>API: GET /result/{job_id} (API Key)
    API-->>Client: 200 OK (status: "completed", result: { ... })
```

---

## 🛠️ Tech Stack & Core Libraries

- **Inference Engine**: [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) for lightning-fast GGUF model execution.
- **REST Framework**: [FastAPI](https://fastapi.tiangolo.com/) with asynchronous endpoint support.
- **Data Validation & Grammar**: [Pydantic](https://docs.pydantic.dev/) & `LlamaGrammar` to enforce JSON schema.
- **Task Management**: Built-in Python `queue.Queue` with a daemon worker thread.
- **Packaging**: Container-compatible runtime using a multi-stage Docker build.
- **Automation**: GitHub Actions checks for repeatable builds.

---

## 📁 Repository Structure

Below are the main files in this repository:

- [app.py](./app.py): The main FastAPI application including authentication, grammar schemas, job queue, and background worker threads.
- [Dockerfile](./Dockerfile): Optimized container build file that pulls the model from Hugging Face during build.
- [requirements.txt](./requirements.txt): Python dependencies for the runtime environment.
- [.env.example](./.env.example): Required environment variables template.
- [.gitignore](./.gitignore): Configured to prevent tracking model files, environment files, local secrets, and keys.

---

## 🔐 Secrets & Security Management

Security is a primary concern. The codebase is configured to avoid exposing sensitive keys and credentials.

### Ignored Sensitive Files
The [.gitignore](./.gitignore) file explicitly ignores the following items to prevent credential leaks:
* **Environment Files**: `.env` and `.env.*` (use [.env.example](./.env.example) to share variable templates).
* **SSH Keys & Private Credentials**: All `.pem`, `.key`, and `.ppk` files.
* **Credentials Folders**: The `forbidden_stuff/` directory for any local-only private credentials.
* **Security Scans**: `gitleaks-report.json` containing local security scan reports.
* **Model Artifacts**: `.gguf`, `.bin`, `.safetensors`, and the `/model` directory.

## 📋 Environment Configuration

Create a `.env` file in the root directory based on the [.env.example](./.env.example) template:

```env
HF_TOKEN=your-huggingface-token
HF_REPO_ID=your-username/qwen3-doctor
API_KEY=your-secret-api-key
```

### Configuration Variables

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | Yes (Build-time) | HuggingFace Access Token used to download the fine-tuned model. |
| `HF_REPO_ID` | Yes (Build-time) | HuggingFace Repository ID where your GGUF model is stored (e.g. `ziadmo/qwen3-doctor`). |
| `API_KEY` | Yes (Runtime) | Secret key checked in the HTTP headers (`X-API-Key`) to authenticate client requests. |
| `GGUF_PATH` | No | Overrides the local path to the `.gguf` file inside the docker container. |

---

## 📡 API Reference & Integration

### Base URL
```
http://localhost:8000
```

### Headers
Every request except the `/health` check requires the API key header:
```http
X-API-Key: <your-secret-api-key>
```

---

### Endpoints

#### 1. Submit Generation Job
Submit raw text to initiate model processing.

- **Method**: `POST`
- **Path**: `/generate`
- **Request Body**:
  ```json
  {
    "text": "Patient is a 45-year-old male presenting with acute substernal chest pain radiating down the left arm, starting 2 hours ago. Accompanied by mild dyspnea and diaphoresis. Prior history of hypertension managed on lisinopril. Currently taking no other medications.",
    "max_tokens": 512
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "job_id": "8f828a21-9dbb-4fc6-b8b8-67503fa6f212",
    "status": "queued",
    "poll_url": "/result/8f828a21-9dbb-4fc6-b8b8-67503fa6f212"
  }
  ```

#### 2. Get Job Status and Result
Poll for status and fetch the completed structured medical report.

- **Method**: `GET`
- **Path**: `/result/{job_id}`
- **Response (Processing)**:
  ```json
  {
    "job_id": "8f828a21-9dbb-4fc6-b8b8-67503fa6f212",
    "status": "processing"
  }
  ```
- **Response (Completed)**:
  ```json
  {
    "job_id": "8f828a21-9dbb-4fc6-b8b8-67503fa6f212",
    "status": "completed",
    "result": {
      "symptoms": [
        {
          "symptom": "substernal chest pain",
          "severity": "acute",
          "duration": "2 hours"
        },
        {
          "symptom": "dyspnea",
          "severity": "mild",
          "duration": "2 hours"
        },
        {
          "symptom": "diaphoresis",
          "severity": "moderate",
          "duration": "2 hours"
        }
      ],
      "old_diagnosis": [
        "hypertension"
      ],
      "medication": [
        {
          "name": "lisinopril",
          "dosage": null,
          "frequency": null
        }
      ],
      "notes": "Patient presents with symptoms highly suggestive of acute coronary syndrome. Immediate ECG and cardiac enzymes recommended."
    }
  }
  ```
- **Response (Failed)**:
  ```json
  {
    "job_id": "8f828a21-9dbb-4fc6-b8b8-67503fa6f212",
    "status": "failed",
    "error": "Timeout occurred during inference"
  }
  ```

#### 3. Health Check
Check queue status and system load instantly.

- **Method**: `GET`
- **Path**: `/health`
- **Response (200 OK)**:
  ```json
  {
    "status": "ok",
    "queue_size": 0,
    "total_jobs": 0
  }
  ```

---

## 💻 Client Code Examples

### JavaScript (Async Polling Example)

```javascript
const generateMedicalReport = async (inputText) => {
  const BASE_URL = "http://localhost:8000";
  const HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": "your-secret-api-key"
  };

  // 1. Submit the job
  const response = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify({ text: inputText, max_tokens: 512 })
  });

  if (!response.ok) {
    throw new Error(`Submission failed: ${response.statusText}`);
  }

  const { job_id } = await response.json();

  // 2. Poll until completion
  while (true) {
    const pollResponse = await fetch(`${BASE_URL}/result/${job_id}`, {
      headers: { "X-API-Key": "your-secret-api-key" }
    });
    const jobData = await pollResponse.json();

    if (jobData.status === "completed") {
      return jobData.result;
    } else if (jobData.status === "failed") {
      throw new Error(`Model generation failed: ${jobData.error}`);
    }

    // Wait 2 seconds before polling again
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
};
```

### Python (Async Polling Example)

```python
import requests
import time

def generate_medical_report(input_text: str):
    base_url = "http://localhost:8000"
    headers = {"X-API-Key": "your-secret-api-key"}
    
    # 1. Submit the job
    res = requests.post(
        f"{base_url}/generate",
        headers=headers,
        json={"text": input_text, "max_tokens": 512}
    )
    res.raise_for_status()
    job_id = res.json()["job_id"]
    
    # 2. Poll until completion
    while True:
        status_res = requests.get(f"{base_url}/result/{job_id}", headers=headers).json()
        status = status_res["status"]
        
        if status == "completed":
            return status_res["result"]
        elif status == "failed":
            raise RuntimeError(f"Job failed: {status_res.get('error')}")
            
        time.sleep(2)
```
