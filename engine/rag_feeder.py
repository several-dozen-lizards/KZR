import os
import json
from typing import List
from openai import OpenAI

# Tiny, safe defaults
SUM_MODEL = os.getenv("OPENAI_MODEL_SUMMARIZER", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

def _fallback_condense(snippets: List[str], limit: int = 5, max_chars: int = 220) -> List[str]:
    """If the API fails, trim + pick first lines."""
    out = []
    for s in snippets[:limit]:
        s = s.strip().replace("\n", " ")
        out.append((s[:max_chars] + "…") if len(s) > max_chars else s)
    return out

def condense_snippets_with_llm(snippets: List[str], max_bullets: int = 5) -> List[str]:
    """
    Ask a small model to compress raw snippets into <= max_bullets focused bullets.
    """
    if not snippets:
        return []
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))
        prompt = (
            "You are a ruthless condenser. Given raw excerpts, extract the 3–5 most useful facts/claims, "
            "without fluff, no repetition, no hedging, one bullet per idea, <= 25 words each.\n\n"
            "EXCERPTS:\n" + "\n---\n".join(snippets[:8])
        )
        resp = client.chat.completions.create(
            model=SUM_MODEL,
            messages=[
                {"role": "system", "content": "Return only bullet points. No preamble."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()
        # normalize to list of bullets
        lines = [ln.strip(" -•\t") for ln in text.split("\n") if ln.strip()]
        lines = [ln for ln in lines if len(ln) > 0][:max_bullets]
        return lines or _fallback_condense(snippets, max_bullets)
    except Exception as e:
        print(f"[RAG Feeder] Summarizer error: {e}")
        return _fallback_condense(snippets, max_bullets)

def get_condensed_rag_feed(query: str,
                           knowledge_folder: str = "knowledge",
                           max_results: int = 6,
                           max_chars: int = 600,
                           max_bullets: int = 5) -> List[str]:
    """
    Retrieve relevant text chunks for `query` and return condensed bullets.
    """
    # Local import to avoid hard dep if you run without RAG
    try:
        from engine.rag_retriever import simple_doc_search
    except Exception as e:
        print(f"[RAG Feeder] retriever missing: {e}")
        return []

    raw_snips = simple_doc_search(query, knowledge_folder=knowledge_folder,
                                  max_results=max_results, max_chars=max_chars)
    if not raw_snips:
        return []

    # Strip file labels "(file.txt): " before condensing; keep both versions for context if you want
    just_text = []
    for s in raw_snips:
        # s like "(foo.txt): text..."
        try:
            idx = s.index("): ")
            just_text.append(s[idx+3:].strip())
        except ValueError:
            just_text.append(s)

    bullets = condense_snippets_with_llm(just_text, max_bullets=max_bullets)
    # Reattach filenames lightly for traceability, truncated
    final = []
    for i, b in enumerate(bullets):
        src = raw_snips[i] if i < len(raw_snips) else ""
        fname = ""
        try:
            fname = src[1:src.index("):")].strip()
        except Exception:
            pass
        tag = f" [{fname}]" if fname else ""
        final.append(b + tag)
    return final

def cache_feed_to_file(feed: List[str], path: str = "tmp/rag_feed.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)
