import os
from typing import List, Dict
from openai import OpenAI

from logger import log_message
from retrieval_tfidf import index_dir

client = OpenAI()

SEED_PATH = os.environ.get("KAY_SEED_PATH", "seed_prompt.kay.txt")
VAULT_DIR = os.environ.get("KAY_VAULT_DIR", "vault")

def load_seed():
    try:
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "You are Kay. Dry, sharp, irreverent. Keep it punchy. No flowers."

def feelings_to_params(feelings: Dict[str, float] | None):
    # feelings: {"warmth":0..1, "arousal":0..1, "valence":-1..1, "edge":0..1}
    f = feelings or {}
    arousal = float(f.get("arousal", 0.4))
    edge = float(f.get("edge", 0.5))
    # map to creativity and terseness
    temperature = 0.4 + 0.6 * arousal       # 0.4 .. 1.0
    max_output_tokens = 256 + int(256 * (1.0 - edge))  # edgier -> tighter
    return {"temperature": round(temperature,2), "max_output_tokens": max_output_tokens}

def retrieve(ix, query: str, k=4):
    hits = ix.search(query, top_k=k)
    if not hits:
        return ""
    chunks = []
    for h in hits:
        chunks.append(f"- {h['id']}: {h['text'][:500]}")
    return "Relevant notes:\n" + "\n".join(chunks)

def generate_reply(messages: List[Dict[str,str]], feelings: Dict[str,float] | None = None) -> str:
    """
    messages: [{"role":"user|assistant|system", "content": "..."}]
    """
    seed = load_seed()
    ix = index_dir(VAULT_DIR) if os.path.isdir(VAULT_DIR) else None
    last_user = next((m["content"] for m in reversed(messages) if m["role"]=="user"), "")
    retrieved = retrieve(ix, last_user) if ix else ""

    system_prompt = seed
    if retrieved:
        system_prompt += "\n\n" + retrieved

    params = feelings_to_params(feelings)
    chat = [{"role":"system","content": system_prompt}] + messages[-12:]  # keep context light
    rsp = client.chat.completions.create(
        model=os.environ.get("KAY_MODEL","gpt-4o-mini"),
        messages=chat,
        temperature=params["temperature"],
        max_tokens=params["max_output_tokens"]
    )
    text = rsp.choices[0].message.content
    log_message("assistant", text)
    return text

def initiative_bonus(neuromod, candidate):
    # Higher when social_need is low (system wants connection)
    # Lower when high (system can "rest" or savor)
    bonus = (1 - neuromod.social_need) * 0.3
    if candidate.text.strip().endswith("?") and neuromod.social_need > 0.75:
        bonus -= 0.1
    return bonus
