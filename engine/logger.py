import os, time, json

LOG_FILE = os.environ.get("KAY_LOG_FILE", "logs/session.jsonl")

def _ensure_dir(path: str):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)

def log_message(role: str, content: str, ts: float | None = None, file: str | None = None) -> dict:
    """
    Append a single JSONL entry with the unified schema:
    {"ts": float, "t": ISO8601_Z, "role": "user|assistant|system", "content": str}
    """
    if file is None:
        file = LOG_FILE
    if ts is None:
        ts = time.time()
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    entry = {"ts": float(ts), "t": iso, "role": str(role), "content": str(content)}
    _ensure_dir(file)
    with open(file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry
