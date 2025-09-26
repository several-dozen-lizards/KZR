# engine/orchestrator.py
from typing import Dict, Any, List, Optional

try:
    from integrations.llm_integration import get_llm_response as _llm_generate
except Exception:
    _llm_generate = None

try:
    from integrations.llm_handler import generate as _alt_generate
except Exception:
    _alt_generate = None

try:
    from generate_reply import generate_reply as _legacy_generate
except Exception:
    _legacy_generate = None

def _fanout_candidates(context: Dict[str, Any], k: int = 4) -> List[str]:
    cands: List[str] = []
    for i in range(max(1, k)):
        ctx = dict(context); ctx['variant'] = i
        out = None
        if _llm_generate is not None: out = _llm_generate(ctx)
        elif _alt_generate is not None: out = _alt_generate(ctx, seed=i)
        elif _legacy_generate is not None: out = _legacy_generate(ctx, seed=i)
        if out is not None:
            cands.append(str(out))
    return cands or ["(no candidate)"]

def generate_response(user_input: str,
                      state: Dict[str, Any],
                      k: int = 4,
                      recent_history: Optional[List[str]] = None) -> Dict[str, Any]:
    recent_history = recent_history or []
    context = {
        "user_input": user_input,
        "emotional_state": state.get("emotional_state") or state.get("state") or {},
        "body": state.get("body", {}),
        "external_knowledge": state.get("external_knowledge", []),
        "recent_history": recent_history,
    }
    cands = _fanout_candidates(context, k=k)
    chosen_idx = 0
    chosen = cands[chosen_idx]
    return {"response": chosen, "candidates": cands, "chosen_index": chosen_idx, "context": context}
