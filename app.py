import os
import json
import re
import logging
import uuid
import threading
import queue
import time
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from llama_cpp import Llama, LlamaGrammar

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App & Auth ────────────────────────────────────────────────────────────────
app = FastAPI(title="Med Report API", version="2.0.0")

API_KEY = os.environ.get("API_KEY", "change-me-please")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key


# ── Load Model ────────────────────────────────────────────────────────────────
GGUF_PATH = os.environ.get("GGUF_PATH", "/app/model/qwen3-4b-dr-assistant.Q4_K_M.gguf")

logger.info(f"Loading model from {GGUF_PATH} ...")
llm = Llama(model_path=GGUF_PATH, n_ctx=2048, n_threads=4, verbose=False)

# ── Grammar Setup ─────────────────────────────────────────────────────────────
MED_SCHEMA = {
    "type": "object",
    "properties": {
        "symptoms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symptom": {"type": "string"},
                    "severity": {"type": ["string", "null"]},
                    "duration": {"type": ["string", "null"]},
                },
                "required": ["symptom", "severity", "duration"],
            },
        },
        "old_diagnosis": {
            "type": "array",
            "items": {"type": "string"},
        },
        "medication": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dosage": {"type": ["string", "null"]},
                    "frequency": {"type": ["string", "null"]},
                },
                "required": ["name", "dosage", "frequency"],
            },
        },
        "notes": {"type": ["string", "null"]},
    },
    "required": ["symptoms", "old_diagnosis", "medication", "notes"],
}
grammar = LlamaGrammar.from_json_schema(json.dumps(MED_SCHEMA))
logger.info("Model and Grammar loaded successfully.")


# ── Job Queue System ──────────────────────────────────────────────────────────
jobs: dict = {}
job_queue: queue.Queue = queue.Queue()
JOB_TTL_SECONDS = 3600  # auto-cleanup after 1 hour


def cleanup_old_jobs():
    now = time.time()
    expired = [
        jid for jid, job in jobs.items() if now - job["created_at"] > JOB_TTL_SECONDS
    ]
    for jid in expired:
        del jobs[jid]
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired jobs")


def worker():
    """Background worker — processes one job at a time."""
    while True:
        job_id = job_queue.get()

        if job_id not in jobs:
            continue

        job = jobs[job_id]
        job["status"] = "processing"
        logger.info(f"[{job_id}] Processing...")

        try:
            prompt = f"<|im_start|>user\n{job['text']}\n<|im_start|>assistant\n"

            output = llm(
                prompt,
                max_tokens=job["max_tokens"],
                temperature=0.1,
                grammar=grammar,
                echo=False,
            )

            raw_output = output["choices"][0]["text"]
            logger.info(f"[{job_id}] Raw output: {raw_output[:200]}")

            result = extract_json(raw_output)
            job["status"] = "completed"
            job["result"] = result
            logger.info(f"[{job_id}] Completed successfully")

        except Exception as e:
            logger.error(f"[{job_id}] Failed: {e}")
            job["status"] = "failed"
            job["error"] = str(e)

        cleanup_old_jobs()
        job_queue.task_done()


worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()
logger.info("Background worker started.")


# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_json(text: str) -> dict:
    text_clean = text.strip()
    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*?\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in model output:\n{text}")


# ── Schemas ───────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str
    max_tokens: int = 512


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Always responds instantly — never blocked by inference."""
    return {
        "status": "ok",
        "queue_size": job_queue.qsize(),
        "total_jobs": len(jobs),
    }


@app.post("/generate")
def generate(req: GenerateRequest, key: str = Security(verify_api_key)):
    """
    Submit a job — returns immediately with a job_id.
    Client polls GET /result/{job_id} for the answer.
    """
    job_id = str(uuid.uuid4())

    jobs[job_id] = {
        "status": "queued",
        "text": req.text,
        "max_tokens": req.max_tokens,
        "result": None,
        "error": None,
        "created_at": time.time(),
    }

    job_queue.put(job_id)
    logger.info(f"[{job_id}] Job queued (queue size: {job_queue.qsize()})")

    return {
        "job_id": job_id,
        "status": "queued",
        "poll_url": f"/result/{job_id}",
    }


@app.get("/result/{job_id}")
def get_result(job_id: str, key: str = Security(verify_api_key)):
    """
    Poll for result.
    Returns status: queued | processing | completed | failed
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    response = {"job_id": job_id, "status": job["status"]}

    if job["status"] == "completed":
        response["result"] = job["result"]
    elif job["status"] == "failed":
        response["error"] = job["error"]
    elif job["status"] == "queued":
        response["position"] = job_queue.qsize()

    return response


@app.get("/jobs")
def list_jobs(key: str = Security(verify_api_key)):
    """List all active jobs — useful for debugging."""
    return {
        "total": len(jobs),
        "queue_size": job_queue.qsize(),
        "jobs": {
            jid: {"status": j["status"], "created_at": j["created_at"]}
            for jid, j in jobs.items()
        },
    }
