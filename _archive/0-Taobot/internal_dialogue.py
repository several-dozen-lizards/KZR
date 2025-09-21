import os
import json
import time
import datetime
import re
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

import openai
from self_helpers import get_node
from self_llm_interface import apply_updates
from self_vectors import fuzzy_search

MODEL_DEBATE = "gpt-4o"
MODEL_CONSENSUS = "gpt-4o"
MAX_DEBATE_ROUNDS = 2
MAX_ACTIONS_PER_ROLE = 5
LOG_DIR = "dialogue_logs"
os.makedirs(LOG_DIR, exist_ok=True)

ROLE_WEIGHTS = {"The Critic": 1.0, "The Optimist": 1.0, "The Analyst": 1.2}

ROLE_SYSTEMS = {
    "The Critic":
        "You are 'The Critic'. Your job is to find flaws, risks, contradictions, and propose cautious revisions. "
        "Prefer down-weighting confidence, REVISED_BY links, and removing redundancy. Avoid bloat.",
    "The Optimist":
        "You are 'The Optimist'. Your job is to identify growth opportunities and propose constructive, coherent additions. "
        "Prefer SUPPORTS/COMPLEMENTS links and confidence strengthening only when justified. Avoid naive positivity.",
    "The Analyst":
        "You are 'The Analyst'. Your job is to evaluate feasibility, coherence, and data consistency. "
        "Prefer minimal precise changes; prefer updating existing beliefs/traits over adding new ones unnecessarily.",
}

ROLE_TASK_TEMPLATE = """
Context (relevant self-model snippets):
{context}

Topic / question to debate:
"{topic}"

Task:
1) Output only a JSON array of self-model actions, zero prose.
2) Keep it minimal and precise (max {max_actions} actions).
3) Prefer updating existing items. Only add new ones if strictly necessary.

Allowed actions:
- add_belief: {{ "id": "...", "value": "...", "confidence": 0.7 }}
- update_belief: {{ "id": "...", "new_value": "...", "new_confidence": 0.8 }}
- add_trait: {{ "id": "...", "value": "...", "strength": 0.6 }}
- update_trait: {{ "id": "...", "new_value": "...", "new_strength": 0.7 }}
- create_relationship: {{ "source_id": "...", "type": "SUPPORTS|CONTRADICTS|COMPLEMENTS|RELATED_TO|REVISED_BY|INTERACTS_WITH|DRIVEN_BY|CONNECTED_TO", "target_id": "..." }}

If no changes are warranted, reply with: NO UPDATE NEEDED
"""

CONSENSUS_SYSTEM = (
    "You are the Consensus Arbiter. You receive multiple JSON action lists produced by distinct roles. "
    "Your job is to merge/resolve conflicts and output ONE final JSON array of actions. "
    "Rules: (1) prefer minimality and coherence, (2) reject duplicates or trivial/no-op updates, "
    "(3) keep relationships legal, (4) down-weight conflicting edits unless strongly justified, "
    "(5) if nothing substantive remains, output 'NO UPDATE NEEDED'."
)

CONSENSUS_USER_TEMPLATE = """
Context (relevant self-model snippets):
{context}

Topic:
"{topic}"

Role-weight hints:
{role_weight_hint}

Role proposals (JSON from each role):
{role_jsons}

Output one final JSON array only, or 'NO UPDATE NEEDED'.
"""

def client():
    return openai.OpenAI()

def strip_fences(s: str) -> str:
    s = re.sub(r"^```(?:json)?", "", s.strip(), flags=re.IGNORECASE)
    s = re.sub(r"```$", "", s.strip())
    return s.strip()

def role_infer_votes(actions: List[Dict[str, Any]]) -> Dict[str, float]:
    score = 0.0
    for a in actions:
        if "update_belief" in a or "update_trait" in a:
            score += 1.0
        elif "add_belief" in a or "add_trait" in a:
            score += 0.5
        elif "create_relationship" in a:
            rt = a["create_relationship"].get("type","").upper()
            if rt in {"SUPPORTS","COMPLEMENTS","RELATED_TO","REVISED_BY","INTERACTS_WITH","DRIVEN_BY","CONNECTED_TO","CONTRADICTS"}:
                score += 0.4
    score -= max(0, len(actions) - 3) * 0.2
    return {"score": max(0.0, score)}

def build_context(topic: str, k: int = 6) -> str:
    ids = fuzzy_search(topic, n_results=k) or []
    lines = []
    for nid in ids:
        for lbl in ("belief","trait","event"):
            n = get_node(lbl, nid)
            if n:
                val = n.get("value") or n.get("text") or n.get("label") or n.get("id")
                lines.append(f"{lbl} {n.get('id')}: {val}")
                break
    return "\n".join(lines[:k]) if lines else "(no nearby context)"

def ask_role(role_name: str, topic: str, context: str, max_actions: int = MAX_ACTIONS_PER_ROLE) -> str:
    sys = ROLE_SYSTEMS[role_name]
    user = ROLE_TASK_TEMPLATE.format(context=context, topic=topic, max_actions=max_actions)
    print(f"[debate] Asking role: {role_name}")
    try:
        rsp = client().chat.completions.create(
            model=MODEL_DEBATE,
            messages=[{"role":"system","content":sys},{"role":"user","content":user}],
            temperature=0.4, max_tokens=600, timeout=60
        )
        return rsp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[debate] Role '{role_name}' failed: {e}")
        return "NO UPDATE NEEDED"

def parse_role_output(raw: str) -> List[Dict[str, Any]] | None:
    txt = strip_fences(raw)
    if txt.upper().startswith("NO UPDATE"):
        return []
    try:
        data = json.loads(txt)
        if isinstance(data, list):
            return data
    except Exception:
        return None
    return None

def consensus_merge(topic: str, context: str, role_outputs: Dict[str, str]) -> str:
    role_weight_hint = ", ".join([f"{r}={ROLE_WEIGHTS.get(r,1.0)}" for r in role_outputs.keys()])
    role_jsons = "\n\n".join([f"{r}:\n{role_outputs[r]}" for r in role_outputs])
    print("[consensus] Merging role proposals...")
    try:
        rsp = client().chat.completions.create(
            model=MODEL_CONSENSUS,
            messages=[
                {"role":"system","content":CONSENSUS_SYSTEM},
                {"role":"user","content":CONSENSUS_USER_TEMPLATE.format(
                    context=context, topic=topic, role_weight_hint=role_weight_hint, role_jsons=role_jsons
                )}
            ],
            temperature=0.3, max_tokens=700, timeout=90
        )
        return rsp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[consensus] Failed: {e}")
        return "NO UPDATE NEEDED"

def run_internal_dialogue(topic: str, rounds: int = MAX_DEBATE_ROUNDS) -> Dict[str, Any]:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOG_DIR, f"dialogue_{stamp}.txt")

    context = build_context(topic, k=6)
    all_rounds: List[Dict[str, Any]] = []

    role_names = list(ROLE_SYSTEMS.keys())
    role_final_raw: Dict[str, str] = {}

    for r in range(rounds):
        round_rec = {"round": r, "roles": {}}
        for role in role_names:
            raw = ask_role(role, topic, context)
            parsed = parse_role_output(raw)
            if parsed is None:
                round_rec["roles"][role] = {"raw": raw, "parsed": None, "votes": {"score": 0.0}}
            else:
                votes = role_infer_votes(parsed)
                round_rec["roles"][role] = {"raw": raw, "parsed": parsed, "votes": votes}
                role_final_raw[role] = raw
        all_rounds.append(round_rec)

    any_valid = any(v.get("parsed") is not None for v in all_rounds[-1]["roles"].values())
    if not any_valid:
        result = {"result":"NO UPDATE NEEDED", "reason":"no valid role proposals"}
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2))
        print(result)
        return result

    consensus_raw = consensus_merge(topic, context, role_final_raw)
    consensus_clean = strip_fences(consensus_raw)

    print("\n--- CONSENSUS PROPOSAL ---\n", consensus_clean)
    approve = input("Apply? [y/N]: ").strip().lower()
    if approve != "y":
        return {"result":"ABORTED_BY_USER", "proposal": consensus_clean}

    if consensus_clean.upper().startswith("NO UPDATE"):
        result = {"result":"NO UPDATE NEEDED"}
    else:
        try:
            _ = json.loads(consensus_clean)
            apply_report = apply_updates(consensus_clean)
            result = {"result":"APPLIED", "apply_report": apply_report}
        except Exception as e:
            result = {"result":"PARSE ERROR", "error": str(e), "raw": consensus_raw}

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== TOPIC ===\n")
        f.write(topic + "\n\n")
        f.write("=== CONTEXT ===\n")
        f.write(context + "\n\n")
        f.write("=== ROUNDS ===\n")
        f.write(json.dumps(all_rounds, indent=2) + "\n\n")
        f.write("=== CONSENSUS RAW ===\n")
        f.write(consensus_raw + "\n\n")
        f.write("=== RESULT ===\n")
        f.write(json.dumps(result, indent=2) + "\n")

    print("Internal dialogue complete:", result.get("result"))
    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Internal Dialogue System")
    parser.add_argument("--topic", type=str, required=True, help="Topic/question to debate (e.g., an event or reflection finding)")
    parser.add_argument("--rounds", type=int, default=MAX_DEBATE_ROUNDS, help="Number of debate rounds")
    args = parser.parse_args()

    run_internal_dialogue(topic=args.topic, rounds=args.rounds)
