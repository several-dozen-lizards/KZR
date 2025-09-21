import os, json, time
from collections import deque

CORE_PATH = "memory/core.json"

def _load_core():
    if os.path.exists(CORE_PATH): return json.load(open(CORE_PATH,"r",encoding="utf-8"))
    return {"pins": [], "mems": []}  # mems: {text, score}

def _save_core(core): json.dump(core, open(CORE_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def consolidate_day(episodic, diary_text):
    # Extract candidate facts/motifs/goals from the diary text (very simple; refine later in LLM)
    # For now: split into lines; seed score=1.0
    core = _load_core()
    for line in [l.strip() for l in diary_text.split("\n") if l.strip()]:
        core["mems"].append({"text": line, "score": 1.0, "ts": time.time()})
    _save_core(core)

def decay_and_prune(keep_top=50):
    core = _load_core()
    # decay scores
    for m in core["mems"]:
        m["score"] *= 0.92
    # keep pins + top mems
    pins = set(core["pins"])
    core["mems"].sort(key=lambda x: x["score"], reverse=True)
    kept = [m for m in core["mems"] if m["text"] in pins][:]  # keep pins regardless
    for m in core["mems"]:
        if len(kept) >= keep_top: break
        if m not in kept: kept.append(m)
    core["mems"] = kept
    _save_core(core)
