import os, json, time, traceback
from engine.rag_feeder import get_condensed_rag_feed, cache_feed_to_file

TASK_DIR = "rag_tasks"
OUT_DIR = "rag_out"

os.makedirs(TASK_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

def process_task(task_path):
    with open(task_path, "r", encoding="utf-8") as f:
        task = json.load(f)
    query = task.get("query","")
    out_file = task.get("out_file","rag_feed.json")
    feed = get_condensed_rag_feed(query)
    out_path = os.path.join(OUT_DIR, out_file)
    cache_feed_to_file(feed, out_path)
    return out_path

def main():
    print("[Sidecar RAG] watching for tasks...")
    while True:
        for name in os.listdir(TASK_DIR):
            if not name.endswith(".json"): 
                continue
            path = os.path.join(TASK_DIR, name)
            try:
                out = process_task(path)
                print(f"[Sidecar RAG] wrote {out}")
            except Exception as e:
                print("[Sidecar RAG] error:", e)
                traceback.print_exc()
            finally:
                # consume task
                try:
                    os.remove(path)
                except Exception:
                    pass
        time.sleep(0.5)

if __name__ == "__main__":
    main()
