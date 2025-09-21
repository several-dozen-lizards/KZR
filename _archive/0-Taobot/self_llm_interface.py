import os, json, datetime, re
from typing import Optional, Tuple, Any, List

# OpenAI client
try:
    from openai import OpenAI
    _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    _client = None  # allow offline/local testing

from self_helpers import (
    get_node, update_node_property, create_node, create_relationship
)
from self_vectors import fuzzy_search

# Optional vector handle for re-embedding (if available in this process)
try:
    from self_vectors import model, collection
except Exception:
    model = None
    collection = None

# -------- Configurable guardrails --------
MAX_ACTIONS_PER_CYCLE = 5
PROTECTED_NODE_IDS = {"self_core"}
ALLOW_RELATION_TYPES = {
    "SUPPORTS", "CONTRADICTS", "COMPLEMENTS", "RELATED_TO",
    "CONNECTED_TO", "DRIVEN_BY", "INTERACTS_WITH", "REVISED_BY"
}
MIN_MEANINGFUL_DELTA = 0.02
CLAMP_01 = lambda x: max(0.0, min(1.0, float(x)))


def extract_updates(text: str):
    """
    Try to pull a JSON array of ops out of any messy LLM output.
    Returns Python list or None.
    """
    # Strip ```json fences
    s = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE|re.MULTILINE)
    s = re.sub(r"```$", "", s.strip(), flags=re.MULTILINE)

    # If reply is a dict, wrap in list
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except Exception:
        pass

    # Last-chance: regex for [ ... ] block
    m = re.search(r"\[.*\]", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")

def _get_any_node(node_id):
    """Try belief -> trait -> event in that order."""
    n = get_node("belief", node_id)
    if n: return ("belief", n)
    n = get_node("trait", node_id)
    if n: return ("trait", n)
    n = get_node("event", node_id)
    if n: return ("event", n)
    return (None, None)

def _reembed_if_changed(node_label, node_id, new_text):
    """Optional: re-embed changed text back into the vector store."""
    if model is None or collection is None:
        return
    try:
        if not new_text or not new_text.strip():
            return
        try:
            collection.delete(ids=[node_id])
        except Exception:
            pass
        emb = model.encode([new_text])[0].tolist()
        collection.add(embeddings=[emb], documents=[new_text], ids=[node_id])
        update_node_property(node_label, node_id, "embedding_id", node_id)
    except Exception as e:
        print(f"[re-embed] skipped for {node_id}: {e}")

# ---------- Context helper ----------
def get_relevant_self_context(query: str, n: int = 3) -> str:
    """
    Return a compact, line-by-line context of node ids + text for the query.
    """
    node_ids = fuzzy_search(query, n_results=n)
    node_ids = node_ids.get("node_ids") if isinstance(node_ids, dict) else node_ids or []
    lines = []
    for nid in node_ids:
        label, node = _get_any_node(nid)
        if not node:
            continue
        val = node.get("value") or node.get("text") or node.get("label")
        lines.append(f"{label}:{nid}: {val}")
    return "\n".join(lines)

# ---------- Boredom-filtered update prompt (kept for your existing pipeline) ----------
def prompt_llm_with_context_boredom(event_text: str, context: str, model: str = "gpt-4o") -> str:
    """
    Ask the LLM for updates, but return 'NO UPDATE NEEDED' if the event is mundane.
    (Kept for compatibility with your event handler and reflection engine.)
    """
    if not _client:
        return "NO UPDATE NEEDED"  # offline fallback
    prompt = f"""
You are the living self-model of an AI system.

Context:
{context}

A new event or experience has occurred:
\"\"\"{event_text}\"\"\"

If this event is not meaningful, impactful, or if it simply represents the status quo,
reply ONLY with: NO UPDATE NEEDED.

Otherwise, suggest specific updates to the self-model as a JSON array of actions:
- add_belief: {{ "id": ..., "value": ..., "confidence": 0.7 }}
- update_belief: {{ "id": ..., "new_value": ..., "new_confidence": 0.8 }}
- add_trait: {{ "id": ..., "value": ..., "strength": 0.6 }}
- update_trait: {{ "id": ..., "new_value": ..., "new_strength": 0.7 }}
- create_relationship: {{ "source_id": ..., "type": "SUPPORTS|CONTRADICTS|COMPLEMENTS|RELATED_TO|REVISED_BY|INTERACTS_WITH|DRIVEN_BY|CONNECTED_TO", "target_id": ... }}

No prose, no explanation — JSON only, or 'NO UPDATE NEEDED'.
"""
    resp = _client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an introspective, evolving AI self-model."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()

# ---------- Chat wrapper used by /v1/chat ----------
def llm_chat(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.6,
    expect_updates_json: bool = False,
) -> Tuple[str, Optional[dict]]:
    """
    Returns (assistant_text, updates_json_or_none).
    If expect_updates_json=True, tries to parse a trailing JSON block.
    """
    if not _client:
        return ("(offline) I can't reach the LLM right now.", None)
    messages = [
        {"role": "system", "content": "You maintain internal coherence and prefer concise, truthful replies."},
        {"role": "user", "content": prompt},
    ]
    resp = _client.chat.completions.create(model=model, messages=messages, temperature=temperature)
    text = resp.choices[0].message.content.strip()

    updates = None
    if expect_updates_json:
        # try to parse a trailing JSON object/array
        try:
            # find last opening brace/bracket
            brace = text.rfind("{")
            brack = text.rfind("[")
            start = max(brace, brack)
            if start != -1:
                candidate = text[start:].strip()
                updates = json.loads(candidate)
                text = text[:start].rstrip()
        except Exception:
            updates = None

    return text, updates

# ---------- Apply updates (robust; JSON list of actions) ----------
def apply_updates_json(updates: Any) -> int:
    """
    Accepts either a list of action dicts or a dict with 'ops'/'updates' → list.
    Returns count of applied ops.
    """
    if not updates:
        return 0
    if isinstance(updates, dict):
        updates = updates.get("ops") or updates.get("updates") or []
    if not isinstance(updates, list):
        return 0

    applied = 0
    for action in updates[:MAX_ACTIONS_PER_CYCLE]:
        try:
            # --- add_belief ---
            if "add_belief" in action:
                d = action["add_belief"]
                nid = d.get("id")
                if not nid or nid in PROTECTED_NODE_IDS or _get_any_node(nid)[1]:
                    continue
                value = (d.get("value") or "").strip()
                conf = CLAMP_01(d.get("confidence", 0.7))
                if not value:
                    continue
                d = {**d, "value": value, "confidence": conf,
                     "last_updated": _now_iso(), "last_update_reason": "reflection_or_event"}
                create_node("belief", **d)
                _reembed_if_changed("belief", nid, value)
                applied += 1
                continue

            # --- update_belief ---
            if "update_belief" in action:
                d = action["update_belief"]
                nid = d.get("id")
                if not nid or nid in PROTECTED_NODE_IDS:
                    continue
                label, node = _get_any_node(nid)
                if label != "belief" or not node:
                    continue
                old_val = node.get("value", "")
                new_val = d.get("new_value", old_val)
                old_conf = float(node.get("confidence", 1.0))
                new_conf = CLAMP_01(d.get("new_confidence", old_conf))
                if (new_val.strip() == str(old_val).strip()) and (abs(new_conf - old_conf) < MIN_MEANINGFUL_DELTA):
                    continue
                update_node_property("belief", nid, "value", new_val)
                update_node_property("belief", nid, "confidence", new_conf)
                update_node_property("belief", nid, "last_updated", _now_iso())
                update_node_property("belief", nid, "last_update_reason", "reflection_or_event")
                _reembed_if_changed("belief", nid, new_val)
                applied += 1
                continue

            # --- add_trait ---
            if "add_trait" in action:
                d = action["add_trait"]
                nid = d.get("id")
                if not nid or nid in PROTECTED_NODE_IDS or _get_any_node(nid)[1]:
                    continue
                value = (d.get("value") or "").strip()
                strength = CLAMP_01(d.get("strength", 0.5))
                if not value:
                    continue
                d = {**d, "value": value, "strength": strength,
                     "last_updated": _now_iso(), "last_update_reason": "reflection_or_event"}
                create_node("trait", **d)
                _reembed_if_changed("trait", nid, value)
                applied += 1
                continue

            # --- update_trait ---
            if "update_trait" in action:
                d = action["update_trait"]
                nid = d.get("id")
                if not nid or nid in PROTECTED_NODE_IDS:
                    continue
                label, node = _get_any_node(nid)
                if label != "trait" or not node:
                    continue
                old_val = node.get("value", "")
                new_val = d.get("new_value", old_val)
                old_str = float(node.get("strength", 1.0))
                new_str = CLAMP_01(d.get("new_strength", old_str))
                if (new_val.strip() == str(old_val).strip()) and (abs(new_str - old_str) < MIN_MEANINGFUL_DELTA):
                    continue
                update_node_property("trait", nid, "value", new_val)
                update_node_property("trait", nid, "strength", new_str)
                update_node_property("trait", nid, "last_updated", _now_iso())
                update_node_property("trait", nid, "last_update_reason", "reflection_or_event")
                _reembed_if_changed("trait", nid, new_val)
                applied += 1
                continue

            # --- create_relationship ---
            if "create_relationship" in action:
                d = action["create_relationship"]
                src_id = d.get("source_id"); rel_t = (d.get("type") or "").upper(); tgt_id = d.get("target_id")
                if not src_id or not rel_t or not tgt_id: 
                    continue
                if rel_t not in ALLOW_RELATION_TYPES:
                    continue
                # best-effort: infer labels dynamically
                src_label, _ = _get_any_node(src_id)
                tgt_label, _ = _get_any_node(tgt_id)
                if not src_label or not tgt_label:
                    continue
                create_relationship(src_label, src_id, rel_t, tgt_label, tgt_id, reason="reflection_or_event", timestamp=_now_iso())
                applied += 1
                continue

        except Exception as e:
            print("[apply_updates_json] skipped op due to error:", e)
            continue

    return applied


# Back-compat alias for older modules that import `apply_updates`
def apply_updates(updates):
    return apply_updates_json(updates)
