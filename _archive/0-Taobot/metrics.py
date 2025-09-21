# metrics.py
"""
Metrics helpers for Taobot (Phase 5.2 complete).
- Tries Neo4j via official driver if env is present; otherwise returns None where appropriate.
- Adds narrative-quality scoring (heuristic).
- Adds helpers to persist Review/Feedback entries into Neo4j.
Env:
  NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
Labels/props (defaults, adjust if your graph differs):
  - Narratives saved as (:narrative {id, text, refs, created_at})
  - Events saved as (:Event {..., created_at})
  - Reviews  saved as (:Review {id, kind, time, summary, payload})
  - Feedback saved as (:Feedback {id, vote, comment, time})-[:FOR]->(:Review)
"""
from __future__ import annotations
import os, datetime, json
from typing import Optional, Dict, Any, Tuple

# ---------- Neo4j driver ----------
_DRIVER = None
def _get_driver():
    global _DRIVER
    if _DRIVER is not None:
        return _DRIVER
    uri, user, pw = os.getenv("NEO4J_URI"), os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")
    if not (uri and user and pw):
        return None
    try:
        from neo4j import GraphDatabase  # type: ignore
        _DRIVER = GraphDatabase.driver(uri, auth=(user, pw))
        return _DRIVER
    except Exception:
        return None

def _run_cypher(cypher: str, params: Optional[Dict[str, Any]] = None):
    drv = _get_driver()
    if drv is None:
        return None
    with drv.session() as session:
        res = session.run(cypher, params or {})
        return list(res)

def _scalar(cypher: str, params: Optional[Dict[str, Any]] = None) -> Optional[float]:
    rows = _run_cypher(cypher, params)
    if not rows:
        return None
    r = rows[0]
    return float(list(r.values())[0])

# ---------- Core metrics ----------
def contradiction_density() -> Optional[float]:
    """contradicting edges per node. Returns None if graph unavailable."""
    total_nodes = _scalar("MATCH (n) RETURN count(n) AS c")
    if total_nodes is None:
        return None
    if total_nodes <= 0:
        return 0.0
    contradicts = _scalar("MATCH ()-[r:CONTRADICTS]->() RETURN count(r) AS c") or 0.0
    return float(contradicts) / float(total_nodes)

def coherence_index() -> Optional[float]:
    """(supports - contradicts) / total_edges  in [-1,1] approx."""
    supports    = _scalar("MATCH ()-[r:SUPPORTS]->() RETURN count(r) AS c")
    contradicts = _scalar("MATCH ()-[r:CONTRADICTS]->() RETURN count(r) AS c")
    total_edges = _scalar("MATCH ()-[r]->() RETURN count(r) AS c")
    if total_edges is None or supports is None or contradicts is None:
        return None
    denom = max(1.0, float(total_edges))
    return float((supports or 0.0) - (contradicts or 0.0)) / denom

# --- replace in metrics.py ---

def _count_new_nodes_with_created_at(label: Optional[str], since_iso: str) -> Optional[float]:
    """
    Counts nodes created since 'since_iso'. Works whether created_at is a datetime or an ISO string.
    """
    if label:
        cypher = (
            f"MATCH (n:{label}) "
            "WHERE exists(n.created_at) AND ("
            "  (n.created_at >= datetime($since)) OR "
            "  (toString(n.created_at) >= $since)"
            ") "
            "RETURN count(n) AS c"
        )
    else:
        cypher = (
            "MATCH (n) "
            "WHERE exists(n.created_at) AND ("
            "  (n.created_at >= datetime($since)) OR "
            "  (toString(n.created_at) >= $since)"
            ") "
            "RETURN count(n) AS c"
        )
    return _scalar(cypher, {"since": since_iso})

def growth_index(hours: int = 24) -> Optional[float]:
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat()
    cnt = _count_new_nodes_with_created_at("Event", since)
    if cnt is not None:
        return float(cnt) / float(max(1, hours))
    # If driver missing or error, return None instead of guessing
    return None

def _latest_narrative() -> Optional[Tuple[str, int]]:
    """
    Returns (text, ref_count) of the most recent narrative node.
    Tries :narrative then :Narrative.
    """
    for label in ("narrative", "Narrative"):
        rows = _run_cypher(
            f"MATCH (n:{label}) "
            "RETURN n.text AS text, "
            "       coalesce(size(n.refs), 0) AS ref_count, "
            "       coalesce(n.created_at, datetime()) AS ts "
            "ORDER BY ts DESC LIMIT 1"
        )
        if rows:
            r = rows[0]
            text = r.get("text") if hasattr(r, "get") else r["text"]
            refs = r.get("ref_count") if hasattr(r, "get") else r["ref_count"]
            return (text or "", int(refs or 0))
    return None


def growth_index(hours: int = 24) -> Optional[float]:
    """
    Nodes created within the last `hours` based on `created_at` (ISO). Returns rate per hour.
    Fallback: if no nodes have `created_at`, we estimate from total Event count / hours (very rough).
    """
    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat()
    cnt = _count_new_nodes_with_created_at("Event", since)
    if cnt is not None:
        return float(cnt) / float(max(1, hours))
    # Fallback (rough): if created_at isn't used at all, look at total :Event count
    total_events = _scalar("MATCH (:Event) RETURN count(*) AS c")
    if total_events is None:
        return None
    return float(total_events) / float(max(1, hours))

# ---------- Narrative quality ----------
def _readability_proxy(text: str) -> float:
    """
    Lightweight readability proxy in [0,1]: shorter sentences/words -> higher score.
    Avoids bringing extra deps like textstat.
    """
    if not text:
        return 0.0
    words = [w for w in text.split() if w.strip()]
    sent_count = max(1, text.count(".") + text.count("?") + text.count("!"))
    avg_sentence_len = len(words) / sent_count
    avg_word_len = sum(len(w.strip(".,!?;:")) for w in words) / max(1, len(words))
    # Normalize: sentence len ~ [10,40], word len ~ [3,7]
    s_score = 1.0 - min(1.0, max(0.0, (avg_sentence_len - 10) / 30.0))
    w_score = 1.0 - min(1.0, max(0.0, (avg_word_len - 3) / 4.0))
    return max(0.0, min(1.0, 0.6 * s_score + 0.4 * w_score))

_EXPECTED_WORDS = {"short": (150, 400), "medium": (400, 900), "long": (900, 2000)}

def _length_coverage_score(text: str, expected: str) -> float:
    words = len([w for w in text.split() if w.strip()])
    lo, hi = _EXPECTED_WORDS.get(expected, _EXPECTED_WORDS["medium"])
    if words <= lo:
        return max(0.0, (words / lo) * 0.7)  # scale up to 0.7 within range
    if words >= hi:
        # mild penalty for verbosity above range
        return max(0.4, 1.0 - (words - hi) / max(hi, 1) * 0.3)
    # in-range
    return 1.0

def _latest_narrative() -> Optional[Tuple[str, int]]:
    """
    Returns (text, ref_count) of the most recent narrative node if present.
    """
    rows = _run_cypher(
        "MATCH (n:narrative) "
        "RETURN n.text AS text, "
        "       coalesce(size(n.refs), 0) AS ref_count, "
        "       coalesce(n.created_at, datetime()) AS ts "
        "ORDER BY ts DESC LIMIT 1"
    )
    if not rows:
        return None
    r = rows[0]
    text = r.get("text") if hasattr(r, "get") else r["text"]
    refs = r.get("ref_count") if hasattr(r, "get") else r["ref_count"]
    return (text or "", int(refs or 0))

def narrative_quality(expected_length: str = "medium") -> Optional[float]:
    """
    Heuristic quality ∈ [0,1]: 0.45*readability + 0.35*length-fit + 0.20*coverage
    Coverage uses `ref_count` if present (cap at 10 for scaling).
    """
    ln = _latest_narrative()
    if ln is None:
        return None
    text, ref_count = ln
    r = _readability_proxy(text)
    l = _length_coverage_score(text, expected_length)
    coverage = min(1.0, ref_count / 10.0)
    score = 0.45 * r + 0.35 * l + 0.20 * coverage
    return round(max(0.0, min(1.0, score)), 3)

def summary(window_hours: int = 24) -> Dict[str, Optional[float]]:
    return {
        "contradiction_density": contradiction_density(),
        "coherence": coherence_index(),
        "growth_index": growth_index(window_hours),
        "narrative_quality": narrative_quality(),  # uses latest narrative if available
    }

# ---------- Persist Reviews & Feedback ----------
def persist_review(entry: Dict[str, Any]) -> None:
    """
    entry keys: id, kind, time, summary, payload
    """
    drv = _get_driver()
    if drv is None:
        return
    payload_json = json.dumps(entry.get("payload", {}), ensure_ascii=False)
    _run_cypher(
        "MERGE (r:Review {id:$id}) "
        "SET r.kind=$kind, r.time=$time, r.summary=$summary, r.payload=$payload",
        {"id": entry["id"], "kind": entry["kind"], "time": entry["time"],
         "summary": entry.get("summary", ""), "payload": payload_json}
    )

def persist_feedback(entry_id: str, vote: Optional[str], comment: Optional[str]) -> None:
    drv = _get_driver()
    if drv is None:
        return
    _run_cypher(
        "MERGE (r:Review {id:$rid}) "
        "CREATE (f:Feedback {id: randomUUID(), vote:$vote, comment:$comment, time: datetime().toString()})-[:FOR]->(r)",
        {"rid": entry_id, "vote": vote, "comment": comment or ""}
    )
