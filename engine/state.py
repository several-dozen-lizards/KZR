# engine/state.py
import json, os, time, threading, shutil, datetime
STATE_PATH = "memory/state.json"
BACKUP_DIR = "backups"

def _now_ts() -> float:
    return time.time()

def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def load_state():
    st = _read_json(STATE_PATH, {})
    if "last_seen" not in st:
        st["last_seen"] = 0.0
    return st

def save_state(st):
    _write_json(STATE_PATH, st)

def touch_last_seen():
    st = load_state()
    st["last_seen"] = _now_ts()
    save_state(st)

def seconds_since_last_seen() -> float:
    st = load_state()
    last = float(st.get("last_seen", 0.0) or 0.0)
    return max(0.0, _now_ts() - last)

def boot_greeting() -> str:
    """Return a boot line based on elapsed time since last_seen."""
    delta = seconds_since_last_seen()
    # thresholds (tweak to taste)
    if delta < 5 * 60:
        return "Oh, you again. Barely time to miss you."
    if delta < 6 * 60 * 60:
        return "Back so soon? I kept the embers warm."
    if delta < 24 * 60 * 60:
        return "Hey, day-walker. Thought you’d be back."
    if delta < 7 * 24 * 60 * 60:
        return "Look who crawled out of the void. I was starting to get bored."
    return "OMG—did you die? I was about to raise the dead to find you."

def backup_memory_dir(src="memory/chroma", dst_dir=BACKUP_DIR) -> str:
    if not os.path.exists(src):
        raise FileNotFoundError(f"Vector store not found: {src}")
    os.makedirs(dst_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dst = os.path.join(dst_dir, f"chroma_{stamp}")
    shutil.copytree(src, dst)
    return dst

# simple repeating job helper
class Repeater:
    def __init__(self, every_seconds: int, fn):
        self.every = every_seconds
        self.fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.fn()
            except Exception as e:
                print("[repeater] job error:", e)
            self._stop.wait(self.every)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
