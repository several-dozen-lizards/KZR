import datetime as dt, os, json
from openai import OpenAI

def write_daily_diary(episodic, log_path="logs/webui-session.jsonl"):
    # gather today’s turns
    today = dt.date.today().isoformat()
    lines = []
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for L in f:
                try:
                    item = json.loads(L)
                    if item["t"].startswith(today):
                        who = item["role"]; txt = item["content"]
                        lines.append(f"{who.upper()}: {txt}")
                except: pass
    if not lines: return None
    client = OpenAI()
    prompt = ("Summarize today’s conversation into a short diary entry (120-180 words). "
              "Capture: what changed, what Kay believes now, and what to watch next. "
              "Be first-person as Kay, no corporate tone.\n---\n" + "\n".join(lines))
    out = client.chat.completions.create(
        model=os.getenv("MODEL","gpt-4o-mini"),
        messages=[{"role":"system","content":"You are Kay; write an evocative diary."},
                  {"role":"user","content":prompt}],
        temperature=0.8).choices[0].message.content
    episodic.add_diary(today, out)
    return out

def weekly_theme_synthesis(episodic):
    # simple weekly key
    week = dt.date.today().isocalendar()
    week_id = f"{week[0]}-W{week[1]:02d}"
    client = OpenAI()
    # pull last ~7 diary docs
    hits = episodic.diary.query(query_texts=["weekly themes"], n_results=12)
    docs = "\n---\n".join(hits.get("documents",[[""]])[0])
    prompt = ("From these diary fragments, synthesize a 150-word 'self-model snapshot'—"
              "first-person, present tense. Include motifs/truths/goals that persist across entries.\n---\n"+docs)
    out = client.chat.completions.create(
        model=os.getenv("MODEL","gpt-4o-mini"),
        messages=[{"role":"system","content":"You are Kay; write a vivid, compact identity snapshot."},
                  {"role":"user","content":prompt}],
        temperature=0.7).choices[0].message.content
    episodic.upsert_theme(week_id, out)
    return out
