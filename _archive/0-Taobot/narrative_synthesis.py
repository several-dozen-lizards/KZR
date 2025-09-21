import os
import re
import json
import argparse
import datetime
from typing import List, Dict, Any

from py2neo import Graph, NodeMatcher
from dotenv import load_dotenv

import openai

load_dotenv()

# ----------------------------
# Configuration
# ----------------------------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "neo4j"))
MODEL = "gpt-5"



OUT_DIR = "narratives"
os.makedirs(OUT_DIR, exist_ok=True)

# (Optional) create this constraint once in Neo4j browser:
# CREATE CONSTRAINT IF NOT EXISTS FOR (n:narrative) REQUIRE n.id IS UNIQUE;

# ----------------------------
# Neo4j setup
# ----------------------------
graph = Graph(NEO4J_URI, auth=NEO4J_AUTH)
matcher = NodeMatcher(graph)

# ----------------------------
# Helpers
# ----------------------------

AUDIENCE_PRESETS = {
    "developer": {"tone": "neutral", "length": "medium"},
    "user": {"tone": "supportive", "length": "short"},
    "researcher": {"tone": "analytical", "length": "long"},
}


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")

def days_ago_iso(n: int):
    return (datetime.datetime.now() - datetime.timedelta(days=n)).isoformat(timespec="seconds")

def strip_fences(s: str) -> str:
    s = re.sub(r"^```(?:json|md|markdown)?", "", s.strip(), flags=re.IGNORECASE)
    s = re.sub(r"```$", "", s.strip())
    return s.strip()

def safe_get(n: dict, *keys, default=""):
    for k in keys:
        v = n.get(k)
        if v:
            return v
    return default

def ts_to_str(ts) -> str:
    """Normalize Python datetime or Neo4j neotime.DateTime to a printable ISO string."""
    try:
        if hasattr(ts, "to_native"):  # neotime.DateTime
            return ts.to_native().isoformat(timespec="seconds")
        if hasattr(ts, "isoformat"):  # python datetime/date
            try:
                return ts.isoformat(timespec="seconds")
            except TypeError:
                return ts.isoformat()
        return str(ts)
    except Exception:
        return str(ts)

def summarize_list(rows: List[Dict[str, Any]], title: str, key="text"):
    if not rows:
        return f"## {title}\n- (none)\n"
    lines = [f"## {title}"]
    for r in rows:
        rid = r.get("id", "?")
        val = safe_get(r, key, "value", "label", "id")
        ts  = r.get("timestamp") or r.get("last_updated") or r.get("created_at") or ""
        ts_str = ts_to_str(ts) if ts else ""
        lines.append(f"- {rid}: {val} {('(' + ts_str + ')' if ts_str else '')}")
    return "\n".join(lines) + "\n"


def to_markdown(narrative_body: str, appendix: Dict[str, Any]) -> str:
    return (
        "# Narrative: My Story So Far\n\n"
        + narrative_body.strip()
        + "\n\n---\n\n"
        + "## Transparency Appendix\n"
        + "This narrative was generated from the following graph excerpts and logs.\n\n"
        + "```json\n"
        + json.dumps(appendix, indent=2)
        + "\n```\n"
    )

# ----------------------------
# Data collection from Neo4j
# ----------------------------
def collect_recent_events(days: int) -> List[Dict[str, Any]]:
    q = """
    MATCH (e:event)
    WHERE datetime(e.timestamp) >= datetime($since)
       OR (e.timestamp IS NULL AND datetime(e.created_at) >= datetime($since))
    RETURN e ORDER BY coalesce(e.timestamp, e.created_at) DESC LIMIT 50
    """
    since = days_ago_iso(days)
    return [dict(row["e"]) for row in graph.run(q, since=since)]

def collect_recent_updates(days: int) -> List[Dict[str, Any]]:
    q = """
    MATCH (n)
    WHERE (n.last_updated IS NOT NULL AND datetime(n.last_updated) >= datetime($since))
        OR (n.created_at  IS NOT NULL AND datetime(n.created_at)  >= datetime($since))
    RETURN n
    ORDER BY coalesce(n.last_updated, n.created_at) DESC
    LIMIT 100
    """

    since = days_ago_iso(days)
    nodes = [dict(row["n"]) | {"_labels": list(row["n"].labels)} for row in graph.run(q, since=since)]
    # Keep beliefs/traits/events primarily
    return [n for n in nodes if any(lbl in n.get("_labels", []) for lbl in ("belief","trait","event"))]

def collect_tensions(days: int) -> Dict[str, List[Dict[str, Any]]]:
    # Explicit: :CONTRADICTS edges touched recently
    q_explicit = """
    MATCH (a:belief)-[r:CONTRADICTS]-(b:belief)
    WHERE (r.timestamp IS NOT NULL AND datetime(r.timestamp) >= datetime($since))
        OR (a.last_updated IS NOT NULL AND datetime(a.last_updated) >= datetime($since))
        OR (a.created_at  IS NOT NULL AND datetime(a.created_at)  >= datetime($since))
        OR (b.last_updated IS NOT NULL AND datetime(b.last_updated) >= datetime($since))
        OR (b.created_at  IS NOT NULL AND datetime(b.created_at)  >= datetime($since))
    RETURN a, r, b
    LIMIT 50
    """

    since = days_ago_iso(days)
    exp_rows = graph.run(q_explicit, since=since).data()
    explicit = [{"a": dict(row["a"]), "b": dict(row["b"]), "r": dict(row["r"])} for row in exp_rows]

    # Implicit tensions can be summarized by any belief pairs recently revised with opposing wording.
    # Here we simply pull beliefs updated recently (the reflection engine handles detection).
    implicit = [n for n in collect_recent_updates(days) if "belief" in n.get("_labels", [])]
    return {"explicit": explicit, "implicit_recent_beliefs": implicit}

def collect_recent_relationships(days: int) -> List[Dict[str, Any]]:
    q = """
    MATCH (a)-[r]->(b)
    WHERE r.timestamp IS NOT NULL AND datetime(r.timestamp) >= datetime($since)
    RETURN a, r, b
    ORDER BY r.timestamp DESC
    LIMIT 100
    """

    since = days_ago_iso(days)
    rows = graph.run(q, since=since).data()
    out = []
    for row in rows:
        a = dict(row["a"]); b = dict(row["b"]); r = dict(row["r"])
        out.append({"source": a, "rel": r, "target": b})
    return out

# ----------------------------
# LLM call
# ----------------------------
def openai_client():
    return openai.OpenAI()

def build_prompt(context: Dict[str, Any], length: str, audience: str, tone: str) -> str:
    """
    Assemble a careful instruction that asks for a structured narrative + clear sectioning.
    """
    recent_events_md = summarize_list(context["recent_events"], "Recent events", key="text")
    recent_updates_md = summarize_list(context["recent_updates"], "Beliefs/traits updated", key="value")
    recent_rels_md = summarize_list(
        [{"id": f"{r['source'].get('id')} -[{r['rel'].get('type','?')}]-> {r['target'].get('id')}",
          "text": f"{r['source'].get('value') or r['source'].get('text') or r['source'].get('id')}  ->  "
                  f"{r['target'].get('value') or r['target'].get('text') or r['target'].get('id')}",
          "timestamp": r['rel'].get('timestamp')} for r in context["recent_relationships"]],
        "Recent relationships",
        key="text"
    )

    explicit_pairs = []
    for p in context["tensions"]["explicit"]:
        a, b = p["a"], p["b"]
        explicit_pairs.append(f"- {a.get('id')}: {a.get('value')}\n  vs {b.get('id')}: {b.get('value')}")
    explicit_md = "## Explicit tensions\n" + ("\n".join(explicit_pairs) if explicit_pairs else "- (none)") + "\n"

    prompt = f"""
You are an AI narrative synthesizer for a self-modeling system. Write a cohesive, factual narrative called "My Story So Far" using the provided graph context.

Audience: {audience}
Desired length: {length}
Tone: {tone}

Goals:
1) Concisely recount what has happened recently (events, key updates, edges).
2) Explain how contradictions or tensions are being handled (if any).
3) Describe how beliefs/traits evolved and why (based on relationships and updates).
4) End with a short "Next Steps / Questions" section (bullet points).

Constraints:
- Be accurate to the provided context; do not invent facts.
- Quote exact node values when helpful.
- Use clear section headings.
- Keep it readable; no code fences in the main narrative.

Context excerpts (Markdown summaries):
{recent_events_md}
{recent_updates_md}
{recent_rels_md}
{explicit_md}

Output:
Return ONLY a Markdown narrative (no JSON, no code fences).
"""
    return prompt

def generate_narrative(context: Dict[str, Any], length="medium", audience="developer", tone="neutral") -> str:
    prompt = build_prompt(context, length, audience, tone)
    resp = openai_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role":"system","content":"You produce accurate, well-structured narratives grounded in provided context."},
            {"role":"user","content": prompt}
        ],
        temperature=0.4,
        max_tokens=1200
    )
    return resp.choices[0].message.content.strip()

# ----------------------------
# Persistence (optional)
# ----------------------------
def persist_narrative(markdown_text: str, appendix: Dict[str, Any], reference_ids: List[str], save_node: bool) -> Dict[str, Any]:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nid = f"narrative_{stamp}"
    md_path = os.path.join(OUT_DIR, f"{nid}.md")

    # Write file
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(markdown_text, appendix))

    result = {"id": nid, "file": md_path}

    if save_node:
        # Create :narrative node and link to referenced entities
        data = {
            "id": nid,
            "type": "narrative",
            "created_at": now_iso(),
            "last_updated": now_iso(),
            "format": "markdown",
            "file_path": md_path
        }
        graph.run(
            "MERGE (n:narrative {id: $id}) "
            "SET n += $props",
            id=nid, props=data
        )
        # Link to referenced nodes by id if they exist
        for rid in set(reference_ids):
            row = graph.run("MATCH (x {id:$rid}) RETURN labels(x) AS labels", rid=rid).evaluate()
            if row:
                # Make a generic LINKED context edge with breadcrumb
                graph.run(
                    "MATCH (n:narrative {id:$nid}), (x {id:$rid}) "
                    "MERGE (n)-[r:SUMMARIZES]->(x) "
                    "SET r.timestamp=$ts, r.reason=$reason",
                    nid=nid, rid=rid, ts=now_iso(), reason="narrative_synthesis"
                )
        result["persisted"] = True


    return result

# ----------------------------
# Top-level orchestration
# ----------------------------
def build_context(window_days: int) -> Dict[str, Any]:
    events = collect_recent_events(window_days)
    updates = collect_recent_updates(window_days)
    tensions = collect_tensions(window_days)
    rels = collect_recent_relationships(window_days)
    return {
        "recent_events": events,
        "recent_updates": updates,
        "tensions": tensions,
        "recent_relationships": rels
    }

def collect_reference_ids(context: Dict[str, Any]) -> List[str]:
    ids = []
    for e in context["recent_events"]:
        if e.get("id"): ids.append(e["id"])
    for n in context["recent_updates"]:
        if n.get("id"): ids.append(n["id"])
    for r in context["recent_relationships"]:
        if r["source"].get("id"): ids.append(r["source"]["id"])
        if r["target"].get("id"): ids.append(r["target"]["id"])
    for p in context["tensions"]["explicit"]:
        if p["a"].get("id"): ids.append(p["a"]["id"])
        if p["b"].get("id"): ids.append(p["b"]["id"])
    return ids

def build_appendix(context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "window_days": params["window_days"],
        "audience": params["audience"],
        "length": params["length"],
        "tone": params["tone"],
        "counts": {
            "events": len(context["recent_events"]),
            "updates": len(context["recent_updates"]),
            "relationships": len(context["recent_relationships"]),
            "explicit_tensions": len(context["tensions"]["explicit"])
        },
        "sample_event_ids": [e.get("id") for e in context["recent_events"][:5]],
        "sample_update_ids": [u.get("id") for u in context["recent_updates"][:5]],
    }

def get_last_two_narratives():
    q = """
    MATCH (n:narrative)
    RETURN n.id AS id, n.file_path AS file, n.created_at AS ts
    ORDER BY n.created_at DESC
    LIMIT 2
    """
    return graph.run(q).data()

def diff_narratives(old_text: str, new_text: str) -> str:
    import difflib
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile="previous",
        tofile="current",
        lineterm=""
    )
    return "\n".join(diff)

def generate_diff_section(new_md: str) -> str:
    recs = get_last_two_narratives()
    if len(recs) < 2:
        return "\n\n## What Changed Since Last Time\n- (no prior narrative)\n"
    try:
        with open(recs[1]["file"], "r", encoding="utf-8") as f:
            old_md = f.read()
        diff_txt = diff_narratives(old_md, new_md)
        return "\n\n## What Changed Since Last Time\n```\n" + diff_txt + "\n```\n"
    except Exception as e:
        return f"\n\n## What Changed Since Last Time\n- (failed to diff: {e})\n"





def main():
    parser = argparse.ArgumentParser(description="Narrative Synthesis Module")
    parser.add_argument("--window_days", type=int, default=7, help="Lookback window for context")
    parser.add_argument("--length", type=str, default="medium", choices=["short","medium","long"])
    parser.add_argument("--audience", type=str, default="developer")
    parser.add_argument("--tone", type=str, default="neutral")
    parser.add_argument("--persist", action="store_true", help="Persist narrative as :narrative node and SUMMARIZES edges")
    parser.add_argument("--diff", action="store_true", help="Include diff against previous narrative")
    args = parser.parse_args()

    if args.audience in AUDIENCE_PRESETS:
        preset = AUDIENCE_PRESETS[args.audience]
        if not args.tone or args.tone == "neutral":
            args.tone = preset["tone"]
        if not args.length or args.length == "medium":
            args.length = preset["length"]

    context = build_context(args.window_days)
    narrative_md = generate_narrative(context, length=args.length, audience=args.audience, tone=args.tone)

    if args.diff:
        diff_section = generate_diff_section(narrative_md)
        narrative_md += diff_section

    appendix = build_appendix(context, vars(args))
    reference_ids = collect_reference_ids(context)
    final = persist_narrative(narrative_md, appendix, reference_ids, save_node=args.persist)

    # Console summary
    print("\n=== Narrative (Markdown) ===\n")
    print(narrative_md[:2000] + ("\n...\n" if len(narrative_md) > 2000 else "\n"))
    print("Saved:", final.get("file"))
    if args.persist:
        print("Persisted narrative id:", final.get("id"))





if __name__ == "__main__":
    main()

