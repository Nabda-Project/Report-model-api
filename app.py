import os
import json
import re
import logging
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from llama_cpp import Llama

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App & Auth ────────────────────────────────────────────────────────────────
app = FastAPI(title="Med Report API", version="1.0.0")

API_KEY = os.environ.get("API_KEY", "change-me-please")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key

# ── Load Model ────────────────────────────────────────────────────────────────
GGUF_PATH = os.environ.get("GGUF_PATH", "/app/model/qwen3-4b-doctor-assistant.Q4_K_M.gguf")

logger.info(f"Loading model from {GGUF_PATH} ...")
llm = Llama(
    model_path=GGUF_PATH,
    n_ctx=2048,
    n_threads=2,
    verbose=False
)
logger.info("Model loaded successfully.")

# ── Schemas ───────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str
    max_tokens: int = 512

class GenerateResponse(BaseModel):
    result: dict

# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_json(text: str) -> dict:
    """Extract the first valid JSON object from model output."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in model output:\n{text}")

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, key: str = Security(verify_api_key)):
    try:
        # Format input using the correct chat template
        prompt = f"<|im_start|>user\n{req.text}\n<|im_start|>assistant"

        output = llm(
            prompt,
            max_tokens=req.max_tokens,
            temperature=0.1,    # low = more deterministic, better for JSON
            echo=False          # don't repeat the prompt in the output
        )

        raw_output = output["choices"][0]["text"]
        logger.info(f"Raw model output: {raw_output[:200]}")

        result = extract_json(raw_output)
        return GenerateResponse(result=result)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")