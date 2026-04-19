# Gewily Changes — 19 April 2026

> **Local branch:** `main` @ `d4192ec`  
> **GitHub (origin/main):** `d4192ec`  
> **Status:** Local is at the same commit as GitHub, but has **uncommitted working-tree changes** and **new untracked files**.

---

## Summary

The local copy contains significant architectural changes that have **not yet been committed or pushed** to GitHub. The main theme is migrating the API from a **synchronous, Azure-hosted** design to an **asynchronous job-queue, AWS EC2-hosted** design.

---

## Changed Files

### 1. `app.py` (Modified)

| Area | GitHub (Last Committed) | Local (Current) |
|---|---|---|
| **API Version** | `1.0.0` | `2.0.0` |
| **Architecture** | Synchronous — `POST /generate` blocks until inference completes and returns the result directly | Asynchronous job queue — `POST /generate` returns a `job_id` immediately; client polls `GET /result/{job_id}` |
| **New imports** | — | `uuid`, `time`, `threading`, `queue` |
| **Job system** | Not present | In-memory `jobs` dict + `queue.Queue` + background worker thread |
| **Job cleanup** | Not present | Auto-expires jobs older than 1 hour (`JOB_TTL_SECONDS = 3600`) |
| **`/health` endpoint** | Returns `{"status": "ok"}` | Returns `{"status": "ok", "queue_size": N, "total_jobs": N}` |
| **`/generate` endpoint** | Runs inference inline, returns `GenerateResponse(result=...)` | Queues a job, returns `{"job_id": "...", "status": "queued", "poll_url": "/result/..."}` |
| **`/result/{job_id}`** | Not present | New endpoint — returns job status (`queued` / `processing` / `completed` / `failed`) and result or error |
| **`/jobs`** | Not present | New endpoint — lists all active jobs (for debugging) |
| **Error handling** | `HTTPException` raised inline (422, 500) | Errors captured per-job and stored in `job["error"]` |
| **Code cleanup** | Had inline comments explaining grammar and regex | Comments removed; code is cleaner |

#### New Endpoints (Local Only)

| Method | Path | Description |
|---|---|---|
| `GET` | `/result/{job_id}` | Poll for inference result |
| `GET` | `/jobs` | List all active jobs |

---

### 2. `README.md` (Modified)

| Area | GitHub | Local |
|---|---|---|
| **Hosting target** | Azure Container Instances | AWS EC2 with Elastic IP |
| **Deployment script** | References `azure-setup.sh` | References `deploy.sh` |
| **API usage flow** | Single request-response | Async: submit → poll → result |
| **JS example** | Single `fetch` call | Submit + poll loop (2s interval) |
| **Python example** | Single `requests.post` | Submit + poll loop (2s interval) |
| **Rollback section** | Present (Azure CLI `az container create`) | Removed |
| **Environment variables** | `API_KEY`, `MODEL_PATH` | `HF_TOKEN`, `HF_REPO_ID`, `API_KEY` |
| **New section** | — | `.env.example` reference added |
| **New section** | — | "Async Flow" explaining the queue lifecycle |

---

## New Files (Untracked)

### 3. `deploy.sh` (New)

A Bash deployment script designed to be run **on an EC2 instance** after SSH-ing in. It performs:

1. **Docker installation** — Auto-detects Ubuntu (`apt-get`) or Amazon Linux (`yum`)
2. **Docker image build** — Validates `HF_TOKEN` and `HF_REPO_ID` env vars, builds image with build args
3. **Container launch** — Stops old container, runs new one on port `8000` with `API_KEY`
4. **Health check** — Polls `localhost:8000/health` for up to 60 seconds, then prints the live URLs

---

### 4. `forbidden_stuff/` (New — Untracked)

Contains sensitive credentials that **must not** be committed to GitHub:

| File | Description |
|---|---|
| `med-report-key.ppk` | PuTTY private key file (likely the EC2 SSH key) |

> ⚠️ **This folder has been added to `.gitignore` to prevent accidental commits.**

---

## `.gitignore` Update

The following entry was added to `.gitignore`:

```diff
 .DS_Store
+forbidden_stuff/
```

---

## Action Items

- [ ] Stage and commit the changes (`app.py`, `README.md`, `deploy.sh`, `.gitignore`)
- [ ] Push to `origin/main`
- [ ] Verify `forbidden_stuff/` is **not** tracked by Git
- [ ] Consider adding `.env.example` file referenced in the README
