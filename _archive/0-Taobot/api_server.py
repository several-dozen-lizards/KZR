# api_server.py
import os
from typing import Optional, Dict, List, Literal
from fastapi import APIRouter, HTTPException, Header, FastAPI
from pydantic import BaseModel, Field

# ---- Your modules ----
from self_vectors import fuzzy_search
from reflection_engine import run_reflection_cycle
from internal_dialogue import run_internal_dialogue
from narrative_synthesis import (
    build_context, generate_narrative, build_appendix,
    collect_reference_ids, persist_narrative
)
from self_helpers import summarize_nodes
from event_handler import log_event
from self_llm_interface import llm_chat, apply_updates_json, extract_updates 

API_KEY = os.getenv("SELF_API_KEY")  # optional
router = APIRouter(prefix="/v1", tags=["self-model"])
app = FastAPI(title="Self-Model API", version="v1")

# ---------- NEW: simple root health (no API key, no prefix) ----------
@app.get("/health")
def health_root():
    return {"status": "ok", "components": {"api": "ready"}}

# ---------- Models ----------
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Text to retrieve relevant self nodes")
    n_results: int = Field(6, ge=1, le=20)

class DebateRequest(BaseModel):
    topic: str = Field(..., description="Topic / question for internal debate")
    rounds: int = Field(2, ge=1, le=6)

class NarrativeRequest(BaseModel):
    window_days: int = Field(7, ge=1, le=365)
    length: Literal["short", "medium", "long"] = "medium"
    audience: Literal["developer", "user", "researcher"] = "developer"
    tone: Literal["neutral", "supportive", "analytical"] = "neutral"
    persist: bool = True
    diff: bool = False

class ChatIn(BaseModel):
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = None
    max_context_items: int = 5
    temperature: float = 0.6
    model: str = "gpt-4.1"

class ChatOut(BaseModel):
    reply: str
    context_ids: List[str] = []
    updates_applied: int = 0

class HealthResponse(BaseModel):
    status: str
    components: Dict[str, str]

# ---------- Auth (very light) ----------
def require_api_key(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# ---------- Routes (versioned) ----------
@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        components={
            "vectors": "ready",
            "reflection": "ready",
            "dialogue": "ready",
            "narrative": "ready",
        },
    )

@router.post("/query-self")
def query_self(req: QueryRequest, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    try:
        ids = fuzzy_search(req.query, n_results=req.n_results) or []
        return {"query": req.query, "node_ids": ids}
    except Exception as e:
        raise HTTPException(500, f"query-self failed: {e}")

@router.post("/reflect")
def reflect(x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    try:
        result = run_reflection_cycle()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(500, f"reflection failed: {e}")

@router.post("/debate")
def debate(req: DebateRequest, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    try:
        applied = run_internal_dialogue(topic=req.topic, rounds=req.rounds)
        return {"status": "ok", "applied": applied}
    except Exception as e:
        raise HTTPException(500, f"debate failed: {e}")

@router.post("/narrative")
def narrative(req: NarrativeRequest, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)
    try:
        ctx = build_context(req.window_days)
        body = generate_narrative(ctx, req.length, req.audience, req.tone)
        appendix = build_appendix(ctx, req.dict())
        refs = collect_reference_ids(ctx)

        saved = {}
        if req.persist:
            saved = persist_narrative(body, appendix, refs, save_node=True)

        return {"status": "ok", "markdown": body, "saved": saved or None}
    except Exception as e:
        raise HTTPException(500, f"narrative failed: {e}")

@router.post("/chat", response_model=ChatOut)
def chat_endpoint(ci: ChatIn, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)

    # 1) log the user message as an event
    event_id = log_event(ci.message, metadata={"role": "user", "session_id": ci.session_id})

    # 2) retrieve context (vectors → node ids → brief summaries)
    hits = fuzzy_search(ci.message, n_results=ci.max_context_items)
    ctx_nodes = hits.get("node_ids") if isinstance(hits, dict) else hits or []
    ctx_text = summarize_nodes(ctx_nodes)

    # 3) call the LLM with self-context
    prompt = f"""You are a helpful assistant with access to a self-model.
Use ONLY the context below to stay consistent with prior beliefs/values.
If context is missing, say what you need.

# SELF CONTEXT
{ctx_text}

# USER
{ci.message}
"""
    reply, raw_updates = llm_chat(
        prompt=prompt,
        model=ci.model,
        temperature=ci.temperature,
        expect_updates_json=True
    )

    updates = extract_updates(reply) or raw_updates

    # 4) feed assistant reply back into the self-model
    log_event(reply, metadata={"role": "assistant", "session_id": ci.session_id, "reply_to": event_id})

    # 5) apply optional structured updates (if the model returned JSON actions)
    applied = apply_updates_json(updates) if updates else 0

    return ChatOut(reply=reply, context_ids=ctx_nodes, updates_applied=applied)

# ---------- NEW: print routes on startup to verify what's mounted ----------
@app.on_event("startup")
async def _show_routes():
    try:
        print("[routes]", *[getattr(r, 'path', str(r)) for r in app.routes], sep="\n  ")
    except Exception:
        pass

# ---------- MOVED: include the router at the very end ----------
app.include_router(router)
