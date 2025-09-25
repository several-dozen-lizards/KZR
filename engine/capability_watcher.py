# engine/capability_watcher.py
import os, hashlib, json, time

WATCH = ["integrations/", "engine/plugins/", ".env"]  # tweak
STATE = ".cap_state.json"

def _hash_file(p):
    try:
        with open(p,"rb") as f: return hashlib.sha256(f.read()).hexdigest()
    except Exception: return None

def snapshot():
    snaps = {}
    for root in WATCH:
        if os.path.isdir(root):
            for dirpath,_,files in os.walk(root):
                for fn in files:
                    p = os.path.join(dirpath, fn)
                    snaps[p] = _hash_file(p)
        elif os.path.isfile(root):
            snaps[root] = _hash_file(root)
    return snaps

def load_state(): 
    try: return json.load(open(STATE,"r"))
    except Exception: return {}

def save_state(s): json.dump(s, open(STATE,"w"), indent=2)

def detect_changes():
    prev = load_state()
    now  = snapshot()
    added   = [p for p in now.keys() - prev.keys()]
    removed = [p for p in prev.keys() - now.keys()]
    changed = [p for p in now.keys() & prev.keys() if prev[p] != now[p]]
    save_state(now)
    return added, removed, changed

def auto_inquiry(added, changed):
    qs = []
    for p in added + changed:
        qs.append({
            "capability": p,
            "risk": "high" if any(k in p for k in ["write","exec","webhook"]) else "medium",
            "questions": [
                "What categories of operations are forbidden?",
                "Is consent needed for use cases touching personal data?",
                "May I run 3 zero-side-effect probes to map failure/latency?",
            ]
        })
    return qs
