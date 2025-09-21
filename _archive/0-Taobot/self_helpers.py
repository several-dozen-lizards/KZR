from __future__ import annotations

import datetime
from typing import Optional, Any, Dict

from py2neo import Graph, Node, Relationship, NodeMatcher

# --- Neo4j connection ---
graph = Graph("bolt://localhost:7687", auth=("neo4j", "00000000"))
matcher = NodeMatcher(graph)

# --- utils ---
def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")

def _sanitize_label(label: str) -> str:
    # Keep it simple: allow alnum + underscore only (avoids Cypher injection in formatted labels)
    return "".join(ch for ch in str(label) if ch.isalnum() or ch == "_")

def _sanitize_reltype(rel_type: str) -> str:
    return "".join(ch for ch in str(rel_type).upper() if ch.isalnum() or ch == "_")


# =========================
# Node helpers (with breadcrumbs)
# =========================

def create_node(label: str, **properties) -> Node:
    """
    Create (or merge by id) a node with versioning breadcrumbs.
    - If 'id' is present, MERGE on (label {id}) to avoid duplicates.
    - Stamps: created_at (if new), last_updated, last_update_reason='self_helpers.create'
    """
    label = _sanitize_label(label)
    now = _now_iso()
    node_id = properties.get("id")

    if node_id is not None:
        # try merge-on-id upsert
        existing = matcher.match(label, id=node_id).first()
        if existing:
            # update existing props
            for k, v in properties.items():
                existing[k] = v
            existing["last_updated"] = now
            existing["last_update_reason"] = "self_helpers.create(merge)"
            graph.push(existing)
            return existing
        else:
            # new node
            if "created_at" not in properties:
                properties["created_at"] = now
            properties["last_updated"] = now
            properties["last_update_reason"] = "self_helpers.create(new)"
            node = Node(label, **properties)
            graph.create(node)
            return node
    else:
        # no id: plain create
        if "created_at" not in properties:
            properties["created_at"] = now
        properties["last_updated"] = now
        properties["last_update_reason"] = "self_helpers.create(no_id)"
        node = Node(label, **properties)
        graph.create(node)
        return node


def get_node(label: str, node_id: Any) -> Optional[Node]:
    label = _sanitize_label(label)
    return matcher.match(label, id=node_id).first()


def update_node_property(label: str, node_id: Any, prop: str, value: Any) -> Optional[Node]:
    """
    Update a single property and stamp last_updated + last_update_reason.
    """
    label = _sanitize_label(label)
    node = get_node(label, node_id)
    if not node:
        return None
    node[prop] = value
    node["last_updated"] = _now_iso()
    # Keep the last reason unless this is explicitly a reflection/event path set by caller.
    if "last_update_reason" not in node:
        node["last_update_reason"] = "self_helpers.update_node_property"
    graph.push(node)
    return node


def delete_node(label: str, node_id: Any) -> bool:
    """
    Detach delete to remove node and its relationships safely.
    """
    label = _sanitize_label(label)
    node = get_node(label, node_id)
    if not node:
        return False
    graph.run(
        f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n",
        id=node_id
    )
    return True


# =========================
# Relationship helpers (props + breadcrumbs, MERGE upsert)
# =========================

def create_relationship(
    label_a: str,
    id_a: Any,
    rel_type: str,
    label_b: str,
    id_b: Any,
    **props: Dict[str, Any],
) -> Optional[Relationship]:
    """
    Create or merge a relationship with properties.
    - Accepts arbitrary props (e.g., timestamp, reason).
    - Adds default breadcrumbs if not provided:
        timestamp=<now>, reason='self_helpers.create_relationship'
    - Uses MERGE to avoid duplicating edges of the same type between same endpoints.
    Returns the relationship (best-effort), or None if endpoints are missing.
    """
    label_a = _sanitize_label(label_a)
    label_b = _sanitize_label(label_b)
    rel_type_up = _sanitize_reltype(rel_type)

    node_a = get_node(label_a, id_a)
    node_b = get_node(label_b, id_b)
    if not node_a or not node_b:
        return None

    # Default breadcrumbs if not provided
    props = dict(props or {})
    props.setdefault("timestamp", _now_iso())
    props.setdefault("reason", "self_helpers.create_relationship")

    # We use Cypher MERGE to ensure properties are set/update on the single edge
    # Note: labels and rel type must be inlined; properties and ids are parameterized.
    query = f"""
    MATCH (a:{label_a} {{id: $id_a}}), (b:{label_b} {{id: $id_b}})
    MERGE (a)-[r:{rel_type_up}]->(b)
    SET r += $props
    RETURN r
    """
    rec = graph.run(query, id_a=id_a, id_b=id_b, props=props).data()
    if rec:
        # py2neo returns dict with 'r' key; we can return the raw relationship object if present
        rel = rec[0].get("r")
        return rel
    return None


def delete_relationship(label_a: str, id_a: Any, rel_type: str, label_b: str, id_b: Any) -> bool:
    """
    Delete a single directed relationship of the given type (a)-[rel_type]->(b).
    """
    label_a = _sanitize_label(label_a)
    label_b = _sanitize_label(label_b)
    rel_type_up = _sanitize_reltype(rel_type)
    res = graph.run(
        f"""
        MATCH (a:{label_a} {{id: $id_a}})-[r:{rel_type_up}]->(b:{label_b} {{id: $id_b}})
        DELETE r
        RETURN count(r) AS c
        """,
        id_a=id_a, id_b=id_b
    ).evaluate()
    return bool(res)



def summarize_nodes(node_ids):
    """
    Return a terse bullet list for the given node ids.
    Tries belief -> trait -> event.
    """
    lines = []
    for nid in node_ids or []:
        # reuse your get_node accessors by label
        n = get_node("belief", nid) or get_node("trait", nid) or get_node("event", nid)
        if not n:
            continue
        label = n.__class__.__name__ if hasattr(n, "__class__") else "node"
        # try common props you use across nodes
        text = n.get("value") or n.get("text") or n.get("label") or ""
        lines.append(f"- [{label}] {nid}: {text}")
    # keep it short for prompts
    return "\n".join(lines[:20])
