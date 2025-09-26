# engine/retriever.py
from typing import List
try:
    from engine.rag_retriever import simple_doc_search as _rag_search
except Exception:
    _rag_search = None
try:
    import retrieval_tfidf as _tf
    _tfidf_search = getattr(_tf, "search", None)
except Exception:
    _tfidf_search = None

def retrieve(query: str, k: int = 6) -> List[str]:
    results: List[str] = []
    if _rag_search is not None:
        try:
            r = _rag_search(query)
            if isinstance(r, list):
                results.extend(r[:k])
        except Exception:
            pass
    if len(results) < k and _tfidf_search is not None:
        try:
            r = _tfidf_search(query, top_k=k-len(results))
            if isinstance(r, list):
                results.extend(r)
        except Exception:
            pass
    return results[:k]
