# engine/consolidation.py
import time
from typing import Tuple

# We’ll use the Chroma collection methods via episodic.[session/diary/themes]
# Each doc has metadatas with "ts" (epoch seconds) and we stored "[role] text" in documents.

def consolidate_and_decay(episodic, keep_recent_secs: int = 3*24*3600,
                          max_session_docs: int = 1500,
                          min_len: int = 15) -> Tuple[int,int]:
    """
    - Keep all items newer than keep_recent_secs.
    - Drop very short crumbs (noise) older than that.
    - If still above max_session_docs, prune oldest.
    Returns: (deleted_count, remaining_count)
    """
    coll = episodic.session
    data = coll.get(include=["documents","metadatas","ids"])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])
    ids = data.get("ids", [])
    now = time.time()
    to_delete = []

    # 1) remove tiny/old crumbs
    for i,(doc,meta,_id) in enumerate(zip(docs, metas, ids)):
        ts = float((meta or {}).get("ts", 0))
        is_old = (now - ts) > keep_recent_secs
        is_tiny = len((doc or "").strip()) < min_len
        if is_old and is_tiny:
            to_delete.append(_id)

    if to_delete:
        coll.delete(ids=to_delete)

    # 2) hard cap count: drop oldest beyond max_session_docs
    data2 = coll.get(include=["metadatas","ids"])
    ids2 = data2.get("ids", [])
    metas2 = data2.get("metadatas", [])
    if len(ids2) > max_session_docs:
        # sort by ts ascending and drop the oldest overflow
        pairs = sorted(zip(ids2, metas2), key=lambda p: float((p[1] or {}).get("ts", 0)))
        overflow = len(ids2) - max_session_docs
        kill_ids = [p[0] for p in pairs[:overflow]]
        if kill_ids:
            coll.delete(ids=kill_ids)

    left = coll.count()
    return (len(to_delete), left)
