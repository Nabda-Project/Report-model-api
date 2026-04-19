# Med Report API

A production-ready REST API that serves a fine-tuned Qwen3 model on AWS EC2.
Takes text input, returns a structured JSON medical report for doctors.
Async job queue — POST /generate returns a job_id, then poll GET /result/{job_id}.

---

## File Structure

```
Report-model-api/
├── .github/
│   └── workflows/
│       └── deploy.yml      # CI/CD — auto deploys on push to main
├── app.py                  # FastAPI server (async job queue)
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
├── deploy.sh               # EC2 deployment script
├── .env.example            # Required environment variables
├── .gitignore              # Keeps model files out of GitHub
└── README.md               # This file
```

---

## How It Works

```
You push to GitHub
        ↓
GitHub Actions builds Docker image
        ↓
Image pushed to Docker Hub (ziadmo/med-report-api)
        ↓
EC2 instance pulls and runs the image
        ↓
API is live at http://<your-ec2-elastic-ip>:8000
```

## Updating the Model

1. Push new model version to HuggingFace
2. Push any change to GitHub to trigger a rebuild
```bash
git commit --allow-empty -m "rebuild with new model"
git push origin main
```

---

## API Usage

### Base URL
```
http://<your-ec2-elastic-ip>:8000
```
Find your Elastic IP in the AWS Console → EC2 → Elastic IPs.

### Endpoints


#### Generate Report
```
POST /generate
```

**Headers**
```
Content-Type: application/json
X-API-Key: your-secret-api-key
```

**Request Body**
```json
{
  "text": "Patient is a 45 year old male with chest pain...",
  "max_tokens": 512
}
```

**Response** (returns immediately — the job runs in the background)
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "queued",
  "poll_url": "/result/a1b2c3d4-..."
}
```

#### Get Result
```
GET /result/{job_id}
```

**Headers**
```
X-API-Key: your-secret-api-key
```

**Response (still processing)**
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "processing"
}
```

**Response (completed)**
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "completed",
  "result": {
    "symptoms": [
      { "symptom": "chest pain", "severity": "moderate" }
    ],
    "notes": "..."
  }
}
```

**Response (failed)**
```json
{
  "job_id": "a1b2c3d4-...",
  "status": "failed",
  "error": "No valid JSON found in model output"
}
```

### Async Flow

The API uses an async job queue — inference can take several seconds, so the API never blocks:

1. **Submit** — `POST /generate` with your text. Returns a `job_id` immediately.
2. **Poll** — `GET /result/{job_id}` to check status. Repeat until status is `completed` or `failed`.
3. **Result** — Once `completed`, the response includes the full structured report.

Possible statuses: `queued` → `processing` → `completed` | `failed`

Jobs are automatically cleaned up after 1 hour.

---

## Calling from JavaScript (Website / React Native)

```javascript
const generateReport = async (inputText) => {
  const BASE = "http://<your-ec2-elastic-ip>:8000";

  // 1. Submit the job
  const res = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "your-secret-api-key"
    },
    body: JSON.stringify({ text: inputText })
  });

  if (!res.ok) throw new Error("API error");
  const { job_id } = await res.json();

  // 2. Poll until completed or failed
  while (true) {
    const poll = await fetch(`${BASE}/result/${job_id}`, {
      headers: { "X-API-Key": "your-secret-api-key" }
    });
    const data = await poll.json();

    if (data.status === "completed") return data.result;
    if (data.status === "failed") throw new Error(data.error);

    await new Promise((r) => setTimeout(r, 2000)); // wait 2s before next poll
  }
};
```

## Calling from Python

```python
import requests, time

BASE = "http://<your-ec2-elastic-ip>:8000"
HEADERS = {"X-API-Key": "your-secret-api-key"}

# 1. Submit the job
res = requests.post(
    f"{BASE}/generate",
    headers=HEADERS,
    json={"text": "Patient is a 45 year old male with chest pain..."}
)
job_id = res.json()["job_id"]

# 2. Poll until completed or failed
while True:
    result = requests.get(f"{BASE}/result/{job_id}", headers=HEADERS).json()
    if result["status"] == "completed":
        report = result["result"]
        break
    elif result["status"] == "failed":
        raise RuntimeError(result["error"])
    time.sleep(2)
```
```

---

## Environment Variables

Set these before running `deploy.sh`. See `.env.example` for a template.

| Variable | Description |
|---|---|
| `HF_TOKEN` | HuggingFace access token (to download the model) |
| `HF_REPO_ID` | HuggingFace repo ID, e.g. `your-username/qwen3-doctor` |
| `API_KEY` | Secret key to protect your endpoint |