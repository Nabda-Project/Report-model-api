# Med Report API

A production-ready REST API that serves a fine-tuned Qwen3 model on Azure.
Takes text input, returns a structured JSON medical report for doctors.
Auto-deploys on every GitHub push via GitHub Actions.

---

## File Structure

```
Report-model-api/
├── .github/
│   └── workflows/
│       └── deploy.yml      # CI/CD — auto deploys on push to main
├── app.py                  # FastAPI server
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
├── azure-setup.sh          # One-time Azure setup script
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
Azure Container Instance pulls and runs the image
        ↓
API is live at a public IP
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
http://<your-azure-ip>:8000
```
Find your IP in the Azure Portal → Container Instances → med-report-api → IP address.

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

**Response**
```json
{
  "result": {
    "patient_name": "...",
    "age": 45,
    "symptoms": ["..."],
    ...
  }
}
```

---

## Calling from JavaScript (Website / React Native)

```javascript
const generateReport = async (inputText) => {
  const response = await fetch("http://<your-azure-ip>:8000/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "your-secret-api-key"
    },
    body: JSON.stringify({ text: inputText })
  });

  if (!response.ok) throw new Error("API error");

  const data = await response.json();
  return data.result; // your JSON report
};
```

## Calling from Python

```python
import requests

response = requests.post(
    "http://<your-azure-ip>:8000/generate",
    headers={"X-API-Key": "your-secret-api-key"},
    json={"text": "Patient is a 45 year old male with chest pain..."}
)

report = response.json()["result"]
```

---

## Rolling Back to a Previous Version

Every deploy is tagged with its commit SHA. To roll back:

```bash
# Find the SHA of the version you want
git log --oneline

# Roll back to that version
az container create \
  --name med-report-api \
  --resource-group med-report-rg \
  --image ziadmo/med-report-api:<commit-sha> \
  --cpu 2 --memory 8 \
  --ports 8000 \
  --ip-address public \
  --environment-variables API_KEY="your-key" \
  --restart-policy Always
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `API_KEY` | Secret key to protect your endpoint |
| `MODEL_PATH` | Path to model inside container (default: `/app/model`) |