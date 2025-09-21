# start_agent.py
import os
import time
import threading
import datetime
import argparse
import hashlib
import queue
from dataclasses import dataclass, asdict
from typing import Optional, List, Deque, Dict, Any
from collections import deque

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

API_KEY = os.getenv("SELF_API_KEY")
def _auth(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# Load env early
load_dotenv()

# -----------------------
# FastAPI app (single surface) + mount router from api_server
# -----------------------
app = FastAPI(title="Taobot Orchestrator", version="v1")

mounted = False
try:
    from api_server import router as api_router
    app.include_router(api_router)  # mounts /v1/*
    mounted = True
except Exception as e:
    print(f"[warn] Could not mount api_server router: {e}")

if not mounted:
    @app.get("/v1/health")
    def _fallback_health():
        return {"status": "ok", "components": {"api_router": "unmounted"}}
# Import the router from api_server and mount it


# -----------------------
# Optional: sanity check for OpenAI key
# -----------------------
if not os.getenv("OPENAI_API_KEY"):
    print("[warn] OPENAI_API_KEY not found; LLM calls may fail.")

try:
    from metrics import (
        contradiction_density as _cd, coherence_index as _ci,
        growth_index as _gi, summary as _ms,
        persist_review as _persist_review, persist_feedback as _persist_feedback,
    )
    contradiction_density, coherence_index, growth_index, metrics_summary_fn = _cd, _ci, _gi, _ms
    persist_review, persist_feedback = _persist_review, _persist_feedback
except Exception as e:
    print(f"[warn] metrics module unavailable: {e}")
    persist_review = lambda entry: None
    persist_feedback = lambda eid, vote, comment: None



# -----------------------
# Safe imports of your modules (with graceful fallbacks)
# -----------------------
def _safe_import(module_name, names):
    try:
        mod = __import__(module_name, fromlist=names)
        return tuple(getattr(mod, n) for n in names)
    except Exception as e:
        print(f"[warn] Could not import {module_name}: {e}")
        return (None,) * len(names)

(process_new_event,) = _safe_import("event_handler", ("process_new_event",))
(run_reflection_cycle,) = _safe_import("reflection_engine", ("run_reflection_cycle",))
(run_internal_dialogue,) = _safe_import("internal_dialogue", ("run_internal_dialogue",))
(build_context, generate_narrative, build_appendix, collect_reference_ids, persist_narrative) = _safe_import(
    "narrative_synthesis",
    ("build_context", "generate_narrative", "build_appendix", "collect_reference_ids", "persist_narrative")
)

# Metrics helpers
contradiction_density = coherence_index = growth_index = metrics_summary_fn = None
try:
    from metrics import contradiction_density as _cd, coherence_index as _ci, growth_index as _gi, summary as _ms
    contradiction_density, coherence_index, growth_index, metrics_summary_fn = _cd, _ci, _gi, _ms
except Exception as e:
    print(f"[warn] metrics module unavailable: {e}")

# -----------------------
# Orchestrator Config & State
# -----------------------
@dataclass
class OrchestratorConfig:
    # intervals in minutes
    reflection_every_min: int = int(os.getenv("REFLECTION_EVERY_MIN", "60"))
    narrative_every_min: int = int(os.getenv("NARRATIVE_EVERY_MIN", "180"))
    dialogue_on_reflection: bool = os.getenv("DIALOGUE_ON_REFLECTION", "true").lower() == "true"
    dialogue_rounds: int = int(os.getenv("DIALOGUE_ROUNDS", "2"))

    # narrative defaults
    narrative_window_days: int = int(os.getenv("NARRATIVE_WINDOW_DAYS", "7"))
    narrative_persist: bool = os.getenv("NARRATIVE_PERSIST", "true").lower() == "true"
    narrative_audience: str = os.getenv("NARRATIVE_AUDIENCE", "developer")
    narrative_length: str = os.getenv("NARRATIVE_LENGTH", "medium")
    narrative_tone: str = os.getenv("NARRATIVE_TONE", "neutral")

    # triggers
    batch_size: int = int(os.getenv("BATCH_SIZE", "10"))
    contradiction_density: float = float(os.getenv("CONTRADICTION_THRESH", "0.12"))

@dataclass
class OrchestratorState:
    started_at: str
    last_reflection_at: Optional[str] = None
    last_narrative_at: Optional[str] = None
    loop_running: bool = False
    last_errors: List[str] = None

    def to_dict(self):
        d = asdict(self)
        d["last_errors"] = self.last_errors or []
        return d

def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")

CONFIG = OrchestratorConfig()
STATE = OrchestratorState(started_at=now_iso(), last_errors=[])

# -----------------------
# Lightweight task queue + run registry
# -----------------------
task_q = queue.Queue()

class RunRegistry:
    """Deduplicate tasks like 'reflect.run:full' once per time bucket/focus."""
    def __init__(self):
        self.seen: dict[str, float] = {}

    def _key(self, name: str, mode: str | None, focus: list[str] | None, bucket: str = "day") -> str:
        focus = focus or []
        fhash = hashlib.md5("|".join(sorted(focus)).encode()).hexdigest()[:10] if focus else "none"
        if bucket == "day":
            day = datetime.date.today().isoformat()
            return f"{name}:{mode}:{fhash}:{day}"
        return f"{name}:{mode}:{fhash}"

    def once(self, name: str, mode: str | None, focus: list[str] | None, ttl_sec: int = 20 * 60) -> bool:
        k = self._key(name, mode, focus)
        now = time.time()
        last = self.seen.get(k)
        if last and (now - last) < ttl_sec:
            return False
        self.seen[k] = now
        return True

RUNS = RunRegistry()

def enqueue(name: str, payload: dict | None = None):
    task_q.put({"name": name, "payload": payload or {}, "ts": time.time()})

def enqueue_once(name: str, mode: str | None = None, focus: list[str] | None = None, payload: dict | None = None, ttl_sec: int = 20 * 60) -> bool:
    if RUNS.once(name, mode, focus, ttl_sec):
        p = payload or {}
        if mode is not None:
            p.setdefault("mode", mode)
        if focus is not None:
            p.setdefault("focus", focus)
        enqueue(name, p)
        return True
    return False

# -----------------------
# Review log (feedback loop) — in-memory ring buffer
# -----------------------
ReviewEntry = Dict[str, Any]
REVIEW_LOG: Deque[ReviewEntry] = deque(maxlen=200)
REVIEW_FEEDBACK: Dict[str, Dict[str, Any]] = {}

def add_review_entry(kind: str, summary: str, payload: Dict[str, Any] | None = None) -> str:
    eid = f"upd-{int(time.time()*1000)}-{kind}"
    entry = {
        "id": eid,
        "kind": kind,
        "time": now_iso(),
        "summary": summary,
        "payload": payload or {},
    }
    REVIEW_LOG.appendleft(entry)
    try:
        persist_review(entry)  # <-- NEW: write to Neo4j if configured
    except Exception as e:
        STATE.last_errors.append(f"[review-persist] {e}")
    return eid


# -----------------------
# Task runners used by the worker
# -----------------------
def run_reflection_task():
    if run_reflection_cycle is None:
        STATE.last_errors.append("[reflection] reflection_engine.run_reflection_cycle not available")
        return {"status": "missing_reflection_engine"}

    print("[reflection] cycle starting…")
    try:
        result = run_reflection_cycle()
        print("[reflection] cycle complete:", result)
        STATE.last_reflection_at = now_iso()

        add_review_entry("reflection", "Reflection cycle completed", {"result": result})

        if CONFIG.dialogue_on_reflection and run_internal_dialogue is not None:
            try:
                topic = "Resolve prominent tensions discovered in reflection"
                print("[dialogue] launching post-reflection dialogue…")
                dres = run_internal_dialogue(topic=topic, rounds=CONFIG.dialogue_rounds)
                add_review_entry("dialogue", "Dialogue after reflection", {"topic": topic, "result": dres})
            except Exception as e:
                msg = f"[dialogue] failed after reflection: {e}"
                print(msg)
                STATE.last_errors.append(msg)

        return {"status": "ok"}
    except Exception as e:
        msg = f"[reflection] failed: {e}"
        print(msg)
        STATE.last_errors.append(msg)
        add_review_entry("error", "Reflection failed", {"error": str(e)})
        return {"status": "error", "error": str(e)}

def run_narrative_task():
    if any(f is None for f in (build_context, generate_narrative, build_appendix, collect_reference_ids, persist_narrative)):
        STATE.last_errors.append("[narrative] narrative functions not available")
        return {"status": "missing_narrative_module"}

    print("[narrative] snapshot starting…")
    try:
        ctx = build_context(CONFIG.narrative_window_days)
        md = generate_narrative(ctx, length=CONFIG.narrative_length, audience=CONFIG.narrative_audience, tone=CONFIG.narrative_tone)
        appendix = build_appendix(ctx, {
            "window_days": CONFIG.narrative_window_days,
            "audience": CONFIG.narrative_audience,
            "length": CONFIG.narrative_length,
            "tone": CONFIG.narrative_tone,
        })
        ref_ids = collect_reference_ids(ctx)
        out = persist_narrative(md, appendix, ref_ids, save_node=CONFIG.narrative_persist)
        print("[narrative] snapshot saved:", out.get("file"))
        STATE.last_narrative_at = now_iso()
        add_review_entry("narrative", "Narrative snapshot saved", {"file": out.get("file"), "id": out.get("id")})
        return {"status": "ok", "file": out.get("file"), "id": out.get("id")}
    except Exception as e:
        msg = f"[narrative] failed: {e}"
        print(msg)
        STATE.last_errors.append(msg)
        add_review_entry("error", "Narrative failed", {"error": str(e)})
        return {"status": "error", "error": str(e)}

def run_dialogue_task(topic: str, rounds: int | None = None):
    if run_internal_dialogue is None:
        STATE.last_errors.append("[dialogue] internal_dialogue.run_internal_dialogue not available")
        return {"status": "missing_dialogue_module"}

    r = rounds if rounds is not None else CONFIG.dialogue_rounds
    print(f"[dialogue] topic='{topic}' rounds={r}")
    try:
        res = run_internal_dialogue(topic=topic, rounds=r)
        add_review_entry("dialogue", "Dialogue run", {"topic": topic, "result": res})
        return {"status": "ok", "result": res}
    except Exception as e:
        msg = f"[dialogue] failed: {e}"
        print(msg)
        STATE.last_errors.append(msg)
        add_review_entry("error", "Dialogue failed", {"error": str(e)})
        return {"status": "error", "error": str(e)}

def run_event_task(text: str):
    if process_new_event is None:
        STATE.last_errors.append("[event] event_handler.process_new_event not available")
        return {"status": "missing_event_module"}

    print(f"[event] {text[:80] + ('…' if len(text) > 80 else '')}")
    try:
        res = process_new_event(text)
        add_review_entry("event", "Event logged", {"text": text, "result": res})
        return {"status": "ok", "result": res}
    except Exception as e:
        msg = f"[event] failed: {e}"
        print(msg)
        STATE.last_errors.append(msg)
        add_review_entry("error", "Event failed", {"error": str(e)})
        return {"status": "error", "error": str(e)}

# -----------------------
# Worker loop
# -----------------------
def worker_loop():
    print("[worker] started")
    while True:
        item = task_q.get()
        try:
            name = item["name"]; p = item.get("payload", {})
            if name == "reflect.run":
                run_reflection_task()
            elif name == "dialogue.run":
                topic = p.get("topic") or "Resolve prominent tensions"
                rounds = p.get("rounds")
                run_dialogue_task(topic=topic, rounds=rounds)
            elif name == "narrative.build":
                run_narrative_task()
            elif name == "metrics.compute":
                compute_metrics_incremental()
        except Exception as e:
            msg = f"[worker] task '{name}' failed: {e}"
            print(msg); STATE.last_errors.append(msg)
        finally:
            task_q.task_done()

# -----------------------
# Metrics timeseries + incremental compute
# -----------------------
METRICS_TS: Deque[Dict[str, Any]] = deque(maxlen=1000)

def compute_metrics_incremental():
    try:
        if metrics_summary_fn is None:
            # best-effort fallback; return zeros/None
            entry = {
                "time": now_iso(),
                "contradiction_density": None,
                "coherence": None,
                "growth_index": None,
                "narrative_quality": None,
            }
        else:
            s = metrics_summary_fn(window_hours=24)
            entry = {"time": now_iso(), **s}
        METRICS_TS.append(entry)
        return entry
    except Exception as e:
        STATE.last_errors.append(f"[metrics] compute failed: {e}")
        return None

# -----------------------
# Event-driven rules (batch + contradiction density)
# -----------------------
EVENTS_SINCE_LAST_REFLECTION = 0

def get_contradiction_density_value() -> float:
    try:
        if contradiction_density is None:
            return 0.0
        v = contradiction_density()
        return float(v) if v is not None else 0.0
    except Exception as e:
        STATE.last_errors.append(f"[metrics] density error: {e}")
        return 0.0

def on_event_logged(ev_id: str, tags: list[str], priority: str | None = "low"):
    global EVENTS_SINCE_LAST_REFLECTION
    EVENTS_SINCE_LAST_REFLECTION += 1

    if any(t.lower() == "contradiction" for t in tags):
        enqueue_once("dialogue.run", mode="focused", focus=[f"event:{ev_id}"], payload={"topic": "Contradiction flagged"})

    if priority and priority.lower() == "high":
        enqueue_once("reflect.run", mode="mini", focus=[f"event:{ev_id}"])

    if EVENTS_SINCE_LAST_REFLECTION >= CONFIG.batch_size:
        if enqueue_once("reflect.run", mode="standard", focus=[]):
            EVENTS_SINCE_LAST_REFLECTION = 0

# -----------------------
# Simple scheduler/orchestrator loop
# -----------------------
def _minutes_since(ts: str | None) -> float:
    if not ts:
        return 1e9
    then = datetime.datetime.fromisoformat(ts)
    return (datetime.datetime.now() - then).total_seconds() / 60.0

def orchestrator_loop(poll_seconds: int = 15):
    STATE.loop_running = True
    print("[orchestrator] loop started")
    try:
        while True:
            try:
                # reflection task
                if _minutes_since(STATE.last_reflection_at) >= CONFIG.reflection_every_min:
                    enqueue_once("reflect.run", mode="full")

                # narrative task
                if _minutes_since(STATE.last_narrative_at) >= CONFIG.narrative_every_min:
                    enqueue_once("narrative.build", mode="daily")

                # every ~10 minutes, compute metrics
                if int(time.time()) % (10*60) < poll_seconds:
                    enqueue_once("metrics.compute", mode="inc", focus=["24h"])

                # crude hourly gate to check contradiction density
                if int(time.time()) % 3600 < poll_seconds:
                    if get_contradiction_density_value() > CONFIG.contradiction_density:
                        enqueue_once("dialogue.run", mode="systemic", focus=[], payload={"topic": "Systemic contradictions"})
            except Exception as e:
                msg = f"[orchestrator] tick failed: {e}"
                print(msg)
                STATE.last_errors.append(msg)

            time.sleep(poll_seconds)
    finally:
        STATE.loop_running = False
        print("[orchestrator] loop stopped")

# -----------------------
# Unified API additions (v1 schedule/metrics/events/reviews)
# -----------------------
class EventIn(BaseModel):
    text: str
    priority: Optional[str] = "low"
    tags: List[str] = []

SCHEDULE = {
    "hourly": ["metrics.compute:incremental"],
    "nightly": ["reflect.run:full", "narrative.build:daily"],
    "weekly": ["narrative.build:weekly"],
}
TRIGGERS = {
    "batch_size": CONFIG.batch_size,
    "contradiction_density": CONFIG.contradiction_density,
}

@app.get("/v1/schedule")
def get_schedule():
    return {"schedule": SCHEDULE, "triggers": TRIGGERS}

@app.put("/v1/schedule")
def put_schedule(payload: dict):
    global SCHEDULE, TRIGGERS, CONFIG
    if "schedule" in payload:
        SCHEDULE = payload["schedule"]
    if "triggers" in payload:
        TRIGGERS = payload["triggers"]
        CONFIG.batch_size = int(TRIGGERS.get("batch_size", CONFIG.batch_size))
        CONFIG.contradiction_density = float(TRIGGERS.get("contradiction_density", CONFIG.contradiction_density))
    return {"ok": True}

@app.get("/v1/metrics/summary")
def metrics_summary(window: str = "24h"):
    if metrics_summary_fn is None:
        return {
            "coherence": None,
            "contradiction_density": None,
            "narrative_quality": None,
            "growth_index": None,
            "window": window,
        }
    # parse hours from window (e.g., "24h" or "7d")
    hours = 24
    try:
        if window.endswith("h"):
            hours = int(window[:-1])
        elif window.endswith("d"):
            hours = int(window[:-1]) * 24
    except Exception:
        pass
    s = metrics_summary_fn(window_hours=hours)
    s["window"] = window
    return s

@app.get("/v1/metrics/timeseries")
def metrics_timeseries(metric: str = "contradiction_density", window: str = "7d") -> Dict[str, Any]:
    # filter METRICS_TS by window
    hours = 24*7
    try:
        if window.endswith("h"):
            hours = int(window[:-1])
        elif window.endswith("d"):
            hours = int(window[:-1]) * 24
    except Exception:
        pass
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=hours)
    out = []
    for row in list(METRICS_TS):
        try:
            ts = datetime.datetime.fromisoformat(row["time"])
            if ts >= cutoff and metric in row:
                out.append({"time": row["time"], "value": row.get(metric)})
        except Exception:
            continue
    return {"metric": metric, "window": window, "points": out}

@app.post("/v1/events")
def post_event(e: EventIn):
    res = run_event_task(e.text)  # boredom filter inside handler
    ev_id = (res.get("result") or {}).get("id", f"evt-{int(time.time())}")
    derived_tags = (res.get("result") or {}).get("tags", [])
    on_event_logged(ev_id, tags=list(set(e.tags + derived_tags)), priority=e.priority)
    return {"id": ev_id, "status": res.get("status", "ok")}




# ------- Reviews & feedback endpoints -------
@app.get("/v1/reviews/recent")
def recent_reviews(limit: int = 50):
    limit = max(1, min(200, limit))
    return list(list(REVIEW_LOG)[0:limit])

class FeedbackIn(BaseModel):
    vote: Optional[str] = None  # "up" | "down"
    comment: Optional[str] = None

@app.post("/v1/reviews/{entry_id}/feedback")
def review_feedback(entry_id: str, fb: FeedbackIn):
    REVIEW_FEEDBACK.setdefault(entry_id, {})
    if fb.vote:
        REVIEW_FEEDBACK[entry_id]["vote"] = fb.vote
    if fb.comment:
        REVIEW_FEEDBACK[entry_id]["comment"] = fb.comment
    try:
        persist_feedback(entry_id, fb.vote, fb.comment)  # <-- NEW
    except Exception as e:
        STATE.last_errors.append(f"[feedback-persist] {e}")
    return {"id": entry_id, "feedback": REVIEW_FEEDBACK[entry_id]}


# -----------------------
# CLI entry point
# -----------------------
def main():
    parser = argparse.ArgumentParser(description="Central controller for self-model system.")
    parser.add_argument("--mode", choices=["loop", "api", "both"], default="both",
                        help="loop: run scheduler; api: run HTTP API; both: run both")
    parser.add_argument("--api-port", type=int, default=int(os.getenv("API_PORT", "8000")))
    args = parser.parse_args()

    # Start worker regardless of mode (needed for queue)
    threading.Thread(target=worker_loop, daemon=True).start()

    if args.mode in ("loop", "both"):
        threading.Thread(target=orchestrator_loop, kwargs={"poll_seconds": 15}, daemon=True).start()

    if args.mode in ("api", "both"):
        try:
            import uvicorn
        except Exception:
            raise SystemExit("FastAPI requires uvicorn. Install with: pip install fastapi uvicorn")
        print(f"[api] serving on http://127.0.0.1:{args.api_port}")
        uvicorn.run(app, host="127.0.0.1", port=args.api_port)
    else:
        # loop only: keep main thread alive
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[orchestrator] shutting down…")

if __name__ == "__main__":
    main()
