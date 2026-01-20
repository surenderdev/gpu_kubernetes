from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import logging
import jwt

# -----------------------------
# Config
# -----------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.1:latest")
JWT_SECRET = os.getenv("JWT_OLLAMA_SECRET")
JWT_ISSUER = os.getenv("JWT_ISSUER")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ollama LLaMA 3.1 API", version="1.0")

# -----------------------------
# JWT Auth Middleware
# -----------------------------
@app.middleware("http")
async def jwt_auth(request: Request, call_next):
    public_paths = ["/health", "/docs", "/openapi.json"]
    if request.url.path in public_paths:
        return await call_next(request)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing token"})

    token = auth.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=JWT_ISSUER
        )
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=401, content={"detail": "Token expired"})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=403, content={"detail": "Invalid token"})

    request.state.user = payload["sub"]
    request.state.scopes = payload.get("scope", [])
    request.state.jti = payload.get("jti")
    return await call_next(request)

# -----------------------------
# Scope Enforcement
# -----------------------------
def require_scope(request: Request, scope: str):
    if scope not in request.state.scopes:
        raise HTTPException(status_code=403, detail="Insufficient scope")

# -----------------------------
# Models
# -----------------------------
class PromptRequest(BaseModel):
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 256

class PromptResponse(BaseModel):
    model: str
    prompt: str
    response: str

# -----------------------------
# Health (public)
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------------
# Test Endpoint (admin)
# -----------------------------
@app.get("/test")
def test_model(request: Request):
    require_scope(request, "ollama:test")
    return _run_test_prompt()

# -----------------------------
# Generation Endpoint (users)
# -----------------------------
@app.post("/generate", response_model=PromptResponse)
def generate(req: PromptRequest, request: Request):
    require_scope(request, "ollama:generate")

    payload = {
        "model": MODEL_NAME,
        "prompt": req.prompt,
        "stream": False,
        "options": {
            "temperature": req.temperature,
            "num_predict": req.max_tokens
        }
    }

    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=300)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

    data = r.json()

    logger.info(
        "User=%s | Model=%s | Tokens=%s | JTI=%s",
        request.state.user,
        MODEL_NAME,
        req.max_tokens,
        request.state.jti
    )

    return PromptResponse(
        model=MODEL_NAME,
        prompt=req.prompt,
        response=data.get("response", "").strip()
    )

# -----------------------------
# Internal Test Logic
# -----------------------------
def _run_test_prompt():
    test_question = "What is the capital of France?"

    payload = {
        "model": MODEL_NAME,
        "prompt": test_question,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 32
        }
    }

    try:
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        response = r.json().get("response", "").strip()
    except Exception as e:
        logger.error("Model test failed: %s", e)
        return {
            "success": False,
            "question": test_question,
            "error": str(e)
        }

    return {
        "success": True,
        "model": MODEL_NAME,
        "question": test_question,
        "answer": response
    }
