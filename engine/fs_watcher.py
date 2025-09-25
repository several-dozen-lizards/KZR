
# engine/fs_watcher.py
import os, json, hashlib, difflib
from typing import Dict, List

STATE_FILE = ".fs_state.json"
DEFAULT_WATCH = ["engine", "integrations", "main.py", "ethics.yml", "user_prefs.yml"]

def _hash_file(path: str):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None

def snapshot(paths=None):
    paths = paths or DEFAULT_WATCH
    out = {}
    for p in paths:
        if os.path.isfile(p):
            out[p] = {"h": _hash_file(p), "s": os.path.getsize(p), "m": os.path.getmtime(p)}
        elif os.path.isdir(p):
            for root,_,files in os.walk(p):
                for fn in files:
                    fp = os.path.join(root, fn)
                    out[fp] = {"h": _hash_file(fp), "s": os.path.getsize(fp), "m": os.path.getmtime(fp)}
    return out

def load_state(state_file=STATE_FILE):
    try:
        with open(state_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state, state_file=STATE_FILE):
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

def compute_changes(prev: Dict, now: Dict) -> List[Dict]:
    prev_keys = set(prev.keys())
    now_keys = set(now.keys())
    added = now_keys - prev_keys
    removed = prev_keys - now_keys
    common = prev_keys & now_keys

    events = []
    for p in added:
        events.append({"path": p, "type": "added", "now": now[p]})
    for p in removed:
        events.append({"path": p, "type": "deleted", "prev": prev[p]})
    for p in common:
        if prev[p].get("h") != now[p].get("h"):
            events.append({"path": p, "type": "modified", "prev": prev[p], "now": now[p]})
    return events

def _read_text(path, max_bytes=200*1024):
    try:
        if os.path.getsize(path) > max_bytes:
            return None
    except Exception:
        return None
    try:
        with open(path, "r", errors="replace") as f:
            return f.read().splitlines()
    except Exception:
        return None

def diff_text(prev_path, now_path):
    a = _read_text(prev_path) or []
    b = _read_text(now_path) or []
    ud = list(difflib.unified_diff(a, b, fromfile=prev_path, tofile=now_path, lineterm=""))
    joined = "\n".join(ud)
    if len(joined) > 5000:
        return "\n".join(ud[:200])
    return joined

class FileSystemWatcher:
    def __init__(self, watch_paths=None, state_file=STATE_FILE):
        self.watch_paths = watch_paths or DEFAULT_WATCH
        self.state_file = state_file
        self.prev = load_state(self.state_file)

    def poll(self):
        now = snapshot(self.watch_paths)
        events = compute_changes(self.prev, now)
        # Save diffs for small text files
        for ev in events:
            p = ev["path"]
            if ev["type"] == "modified":
                try:
                    os.makedirs(".fs_snapshots", exist_ok=True)
                    ud = diff_text(p, p)
                    if ud:
                        name = hashlib.sha256(p.encode()).hexdigest()[:8] + "-" + os.path.basename(p) + ".diff"
                        outp = os.path.join(".fs_snapshots", name)
                        with open(outp, "w") as f:
                            f.write(ud)
                        ev["diff_file"] = outp
                except Exception:
                    pass
        save_state(now, self.state_file)
        self.prev = now
        return events
