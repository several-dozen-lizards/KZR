import os
import time
import json
import re
import datetime
from typing import List, Dict

from py2neo import Graph, NodeMatcher
from self_helpers import get_node, update_node_property, create_node, create_relationship
from self_llm_interface import apply_updates
from self_vectors import fuzzy_search, model  # reuse embeddings
from internal_dialogue import run_internal_dialogue
from narrative_synthesis import (
    build_context, generate_narrative, build_appendix,
    collect_reference_ids, persist_narrative
)

# === Config ===
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "00000000")
REFLECTION_INTERVAL_SECS = 180
LOG_DIR = "reflection_logs"
os.makedirs(LOG_DIR, exist_ok=True)

graph = Graph(NEO4J_URI, auth=NEO4J_AUTH)
matcher = NodeMatcher(graph)

# ----------- DETECTORS -----------

def get_all_beliefs() -> List[dict]:
    return [dict(n) | {"_labels": list(n.labels)} for n in matcher.match("belief")]

def get_all_traits() -> List[dict]:
    return [dict(n) | {"_labels": list(n.labels)} for n in matcher.match("trait")]

def get_all_mysteries() -> List[dict]:
    # No pandas. Use MATCH + .data()
    mysteries = [dict(n) | {"_labels": list(n.labels)} for n in matcher.match("mystery")]
    rows = graph.run("MATCH (n) WHERE n.id STARTS WITH 'mystery_' RETURN n").data()
    mysteries += [dict(r["n"]) | {"_labels": list(r["n"].labels)} for r in rows]

    # De-dup by id
    seen, uniq = set(), []
    for m in mysteries:
        mid = m.get("id")
        if mid and mid not in seen:
            uniq.append(m)
            seen.add(mid)
    return uniq

def get_contradict_edges() -> List[Dict]:
    q = "MATCH (a:belief)-[r:CONTRADICTS]-(b:belief) RETURN a, r, b"
    rows = graph.run(q).data()
    out = []
    for row in rows:
        a = dict(row["a"]); b = dict(row["b"])
        out.append({"a": a, "b": b, "type": "EXPLICIT"})
    return out

POS_WORDS = {"growth","repair","creativity","openness","value","clarity","coherence","curiosity","optimism"}
NEG_WORDS = {"futility","anxiety","rigid","strict","closed","stagnation","meaningless","contradiction"}

def text_polarity(text: str) -> int:
    t = (text or "").lower()
    score = 0
    for w in POS_WORDS:
        if w in t: score += 1
    for w in NEG_WORDS:
        if w in t: score -= 1
    return score

def find_implicit_tensions(beliefs: List[dict], top_k: int = 5) -> List[Dict]:
    out = []
    texts = [b.get("value") or b.get("label") or b.get("id") for b in beliefs]
    ids   = [b.get("id") for b in beliefs]
    if not texts: return out

    import numpy as np
    E = model.encode(texts)
    E = np.array(E)
    norms = (E * E).sum(axis=1) ** 0.5
    sims = (E @ E.T) / (norms[:,None] * norms[None,:] + 1e-8)

    for i, bi in enumerate(beliefs):
        vi = texts[i]; pi = text_polarity(vi)
        if pi == 0: continue
        order = np.argsort(-sims[i])
        for j in order:
            if j == i: continue
            vj = texts[j]; pj = text_polarity(vj)
            if pj == 0: continue
            if pi * pj < 0 and sims[i, j] > 0.4:
                out.append({"a": beliefs[i], "b": beliefs[j], "similarity": float(sims[i, j]), "type": "IMPLICIT"})
                break
        if len(out) >= top_k: break
    return out

def find_gaps_and_orphans(conf_thresh: float = 0.55) -> Dict[str, List[dict]]:
    # Gaps: low-confidence beliefs
    low_conf = [b for b in get_all_beliefs() if float(b.get("confidence", 1.0)) < conf_thresh]

    # Orphans: nodes with no relationships — Neo4j 5+ safe (no size((n)--()))
    try:
        q = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN n
        """
        rows = graph.run(q).data()
    except Exception:
        # Fallback for Neo4j 5 pattern-count
        q = """
        MATCH (n)
        WHERE COUNT { (n)--() } = 0
        RETURN n
        """
        rows = graph.run(q).data()

    orphans = [dict(row["n"]) | {"_labels": list(row["n"].labels)} for row in rows]
    return {"low_confidence": low_conf, "orphans": orphans}

# ----------- CONTEXT & PROMPTS -----------

def summarize_pairs(pairs: List[Dict], label="Contradictions") -> str:
    lines = [f"## {label}"]
    for p in pairs:
        a = p["a"]; b = p["b"]
        lines.append(f"- {a.get('id')}: {a.get('value')}")
        lines.append(f"  vs {b.get('id')}: {b.get('value')}  (type: {p['type']})")
    return "\n".join(lines) if pairs else f"## {label}\n- None"

def summarize_list(nodes: List[dict], label: str, show_prop="value") -> str:
    lines = [f"## {label}"]
    if not nodes:
        lines.append("- None")
    else:
        for n in nodes:
            lines.append(f"- {n.get('id')} ({','.join(n.get('_labels', []))}): {n.get(show_prop) or n.get('text')}")
    return "\n".join(lines)

REFLECTION_TEMPLATE = """
You are the self-model of an AI engaged in periodic reflection.

Here are current tensions and gaps:

{explicit_cs}

{implicit_cs}

{gaps}

{mysteries}

Task:
1) Propose targeted updates as JSON actions only.
   - Prefer minimal, precise changes.
   - When appropriate, propose “letting go” (down-weighting confidence, or adding a REVISED_BY relationship).
   - Avoid trivial changes.
2) If no substantive change is warranted, reply exactly: NO UPDATE NEEDED

Actions format (JSON array only):
[
  {{"update_belief": {{"id": "...", "new_value": "...", "new_confidence": 0.85}}}},
  {{"add_belief":    {{"id": "...", "value": "...", "confidence": 0.7}}}},
  {{"create_relationship": {{"source_id": "...", "type": "REVISED_BY", "target_id": "..."}}}},
  {{"update_trait":  {{"id": "...", "new_value": "...", "new_strength": 0.8}}}}
]
"""


def call_llm_reflect(context_text: str, model_name: str = "gpt-4o") -> str:
    import openai
    client = openai.OpenAI()
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a careful, precise reflection engine. Output JSON actions only, or NO UPDATE NEEDED."},
            {"role": "user", "content": context_text}
        ],
        temperature=0.4,
        max_tokens=800,
    )
    return resp.choices[0].message.content.strip()

def strip_code_fences(s: str) -> str:
    s = re.sub(r"^```(?:json)?", "", s.strip(), flags=re.IGNORECASE)
    s = re.sub(r"```$", "", s.strip())
    return s.strip()

# ----------- REFLECTION CYCLE -----------

def run_reflection_cycle() -> Dict[str, str]:
    beliefs = get_all_beliefs()
    explicit = get_contradict_edges()
    implicit = find_implicit_tensions(beliefs, top_k=5)
    gaps = find_gaps_and_orphans(conf_thresh=0.55)
    mysteries = get_all_mysteries()

    explicit_cs = summarize_pairs(explicit, "Explicit contradictions")
    implicit_cs = summarize_pairs(implicit, "Implicit tensions")
    tensions = explicit + implicit

    # Optional: kick off dialogue on the most salient tension
    if tensions:
        a = tensions[0]["a"].get("value") or tensions[0]["a"].get("id")
        b = tensions[0]["b"].get("value") or tensions[0]["b"].get("id")
        topic = f"Resolve tension between: {a}  vs  {b}"
        print("[dialogue] Starting internal dialogue on reflection tension...")
        try:
            run_internal_dialogue(topic=topic, rounds=2)
        except Exception as e:
            print("[dialogue] failed to run:", e)

    gaps_s = (
        summarize_list(gaps["low_confidence"], "Low-confidence beliefs") + "\n\n" +
        summarize_list(gaps["orphans"], "Orphaned nodes")
    )
    mysteries_s = summarize_list(mysteries, "Mysteries", show_prop="value")

    context = REFLECTION_TEMPLATE.format(
        explicit_cs=explicit_cs,
        implicit_cs=implicit_cs,
        gaps=gaps_s,
        mysteries=mysteries_s
    )

    llm_raw = call_llm_reflect(context)
    print("\n--- Reflection LLM raw ---\n", llm_raw)

    result = "NO UPDATE NEEDED"
    if not llm_raw.upper().startswith("NO UPDATE"):
        cleaned = strip_code_fences(llm_raw)
        try:
            # Validate JSON shape first
            _ = json.loads(cleaned)
            upd_report = apply_updates(cleaned)  # robust updater
            result = "APPLIED" if upd_report.get("applied", 0) > 0 else "NO UPDATE NEEDED"
        except Exception as e:
            result = f"PARSE ERROR: {e}"


    if llm_raw.upper().startswith("NO UPDATE"):
        result = "NO UPDATE NEEDED"
    else:
        cleaned = strip_code_fences(llm_raw)
        try:
            actions = json.loads(cleaned)
            apply_updates(cleaned)  # guarded apply
            result = "APPLIED"
        except Exception as e:
            result = f"PARSE ERROR: {e}"

    # Logging
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(LOG_DIR, f"reflection_{stamp}.txt"), "w", encoding="utf-8") as f:
        f.write("=== CONTEXT ===\n")
        f.write(context + "\n\n")
        f.write("=== LLM RAW ===\n")
        f.write(llm_raw + "\n\n")
        f.write(f"=== RESULT ===\n{result}\n")

    # Auto narrative snapshot (best-effort)
    try:
        ctx = build_context(7)
        md  = generate_narrative(ctx, length="medium", audience="developer", tone="neutral")
        appendix = build_appendix(ctx, {"window_days":7,"audience":"developer","length":"medium","tone":"neutral"})
        refs = collect_reference_ids(ctx)
        persist_narrative(md, appendix, refs, save_node=True)
        print("[narrative] Snapshot generated and persisted.")
    except Exception as e:
        print("[narrative] Failed to generate narrative:", e)

    return {"result": result}

# ----------- MAIN ------------

def main():
    print("Reflection engine started. Press Ctrl+C to stop.")
    if REFLECTION_INTERVAL_SECS <= 0:
        run_reflection_cycle()
        return
    while True:
        try:
            out = run_reflection_cycle()
            print("Cycle result:", out["result"])
            time.sleep(REFLECTION_INTERVAL_SECS)
        except KeyboardInterrupt:
            print("\nReflection paused by user.")
            break

if __name__ == "__main__":
    main()
