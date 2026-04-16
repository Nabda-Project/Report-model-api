import os
import json
import re
import logging
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from llama_cpp import Llama, LlamaGrammar  # Added LlamaGrammar

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
GGUF_PATH = os.environ.get(
    "GGUF_PATH", "/app/model/qwen3-4b-doctor-assistant.Q4_K_M.gguf"
)

logger.info(f"Loading model from {GGUF_PATH} ...")
llm = Llama(model_path=GGUF_PATH, n_ctx=2048, n_threads=4, verbose=False)

# ── Grammar Setup ─────────────────────────────────────────────────────────────
# Define the expected JSON structure globally so it's only compiled once
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
                },
                "required": ["symptom", "severity"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["symptoms", "notes"],
}
# Pre-compile the grammar for speed
grammar = LlamaGrammar.from_json_schema(json.dumps(MED_SCHEMA))

logger.info("Model and Grammar loaded successfully.")


# ── Schemas ───────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str
    max_tokens: int = 512


class GenerateResponse(BaseModel):
    result: dict


# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_json(text: str) -> dict:
    """Extract the first valid JSON object from model output."""
    # Try direct parse first
    text_clean = text.strip()
    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        pass

    # Use NON-GREEDY match (.*?) to find the FIRST complete JSON object
    # This prevents grabbing multiple looped objects at once
    match = re.search(r"(\{.*?\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
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
        # 1. Improved prompt with a newline to trigger better generation
        prompt = f"<|im_start|>user\n{req.text}\n<|im_start|>assistant\n"

        # 2. Augmented LLM call
        output = llm(
            prompt,
            max_tokens=req.max_tokens,
            temperature=0.1,
            grammar=grammar,  # Forces valid JSON and stops loops
            echo=False,
        )

        raw_output = output["choices"][0]["text"]
        logger.info(f"Raw model output: {raw_output[:200]}")

        # 3. Process result
        result = extract_json(raw_output)
        return GenerateResponse(result=result)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
