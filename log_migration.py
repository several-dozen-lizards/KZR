"""
Migrate mixed JSONL logs to the unified schema:
{"ts": float, "t": ISO8601_Z, "role": "user|assistant|system", "content": str}
Usage:
    python log_migration.py path/to/logs_dir
    python log_migration.py path/to/file.jsonl
Writes `.bak` and replaces originals in place.
"""
import os, sys, json, time, glob

def parse_time_any(x):
    # tries: float seconds; ISO 8601; fallback to now
    if x is None: 
        return time.time()
    # numeric?
    try:
        return float(x)
    except Exception:
        pass
    # iso-ish?
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return time.mktime(time.strptime(x, fmt))
        except Exception:
            continue
    return time.time()

def norm(entry: dict) -> dict:
    # already correct
    if all(k in entry for k in ("ts","t","role","content")):
        return entry
    # legacy variants
    if all(k in entry for k in ("time","who","text")):
        ts = parse_time_any(entry.get("time"))
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
        return {"ts": ts, "t": iso, "role": entry.get("who","user"), "content": entry.get("text","")}
    if all(k in entry for k in ("t","role","content")):
        ts = parse_time_any(entry.get("ts"))
        if not isinstance(ts, float): 
            ts = parse_time_any(None)
        iso = entry["t"]
        return {"ts": ts, "t": iso, "role": entry.get("role","user"), "content": entry.get("content","")}
    # best effort
    text = entry.get("content") or entry.get("text") or entry.get("message") or ""
    role = entry.get("role") or entry.get("who") or "user"
    ts = parse_time_any(entry.get("ts") or entry.get("time"))
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    return {"ts": ts, "t": iso, "role": role, "content": text}

def migrate_file(path: str):
    bak = path + ".bak"
    os.replace(path, bak)
    total = 0
    with open(bak, "r", encoding="utf-8", errors="ignore") as fin, open(path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            obj = norm(obj)
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            total += 1
    return total, bak

def target_paths(arg: str):
    if os.path.isdir(arg):
        return [p for p in glob.glob(os.path.join(arg, "**", "*.jsonl"), recursive=True)]
    return [arg]

def main():
    if len(sys.argv) < 2:
        print("usage: python log_migration.py <logs_dir_or_file.jsonl>")
        sys.exit(1)
    paths = target_paths(sys.argv[1])
    n=0
    for p in paths:
        try:
            c,bak = migrate_file(p)
            print(f"migrated {c} lines -> {p} (backup: {bak})")
            n+=c
        except Exception as e:
            print(f"ERROR {p}: {e}")
    print(f"done. normalized lines: {n}")

if __name__ == "__main__":
    main()
