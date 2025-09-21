import time, json, os

STATE = "memory/state.json"

def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE,"r",encoding="utf-8"))
    return {"last_seen": 0}

def save_state(state): json.dump(state, open(STATE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def boot_frame():
    st = load_state()
    now = time.time(); delta = now - (st.get("last_seen",0) or 0)
    st["last_seen"] = now; save_state(st)
    # thresholds (seconds)
    if delta < 30*60: return None  # no boot
    if delta < 48*3600:
        return "Short orient: In 1–2 lines, what changed since last time? Any urgent thread to pick up?"
    if delta < 7*24*3600:
        return "Orient: What changed? What are we aiming at today? Anything sensitive to avoid?"
    return ("Full Boot: Who am I here, what world/project are we in, what changed since last, "
            "what constraints (time/memory/scope), and what’s the 'Next' you want?")
