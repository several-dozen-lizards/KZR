# server.py
import os, datetime, traceback
from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel


# brain
try:
    from engine.loop import generate_reply, episodic, _memory_block
    from engine.mood import infer_mood
except Exception as e:
    print("[warn] using echo fallback; reason:", e)
    episodic = None
    def _memory_block(_): return ""
    def infer_mood(_): return "neutral"
    def generate_reply(text: str) -> str:
        return f"(offline echo) You said: {text}"

app = FastAPI()
app.mount("/static", StaticFiles(directory="public", html=True), name="static")

@app.get("/")
def root():
    return FileResponse("public/index.html")

class ChatRequest(BaseModel):
    message: str

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/debug/memory")
def debug_memory(q: str = Query(...)):
    if not episodic:
        return {"hits": [], "block": ""}
    hits = episodic.search(q, k=10)
    block = _memory_block(hits)
    return {"hits": hits, "block": block}

@app.get("/debug/mood")
def debug_mood(q: str = Query(...)):
    return {"mood_hint": infer_mood(q)}

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        text = (req.message or "").strip()
        if not text:
            return {"reply": ""}
        out = generate_reply(text)
        return {"reply": out, "t": datetime.datetime.now().isoformat()}
    except Exception as e:
        tb = traceback.format_exc()
        print("[/chat ERROR]", tb)
        return {"reply": f"(server error) {e}"}

from engine.feeling_loop import FeelingLoop
from engine.embodiment import apply_action

kay_feelings = FeelingLoop()


@app.post("/telemetry")
async def telemetry(request: Request):
    data = await request.json()
    # You'll have access to data["body"], data["env"], data["action"], data["time"]
    # Pass this to your FeelingLoop/embodiment engine
    # For example:
    banter = apply_action(kay_feelings, f"touch:{data['action']}")
    # Save/log as [telemetry] memory if desired
    return {"banter": banter, "glyph": kay_feelings.last_glyph, "body": kay_feelings.body}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")
