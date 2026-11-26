import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from utils.mock_llm import ask as llm_ask
from .auth import verify_api_key
from .config import settings
from .cost_guard import answer_with_budget
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        r.close()


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        logger.info(json.dumps({"event": "request", "method": request.method,
                                "path": request.url.path, "status": status,
                                "ms": round((time.monotonic() - start) * 1000, 1)}))


@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    return JSONResponse({"detail": "Redis unavailable"}, status_code=503)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(503, "Redis unavailable")
    return {"ready": True}


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, pattern=r"\S")


@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    answer = answer_with_budget(body.question, llm_ask)
    return {"question": body.question, "answer": answer}
