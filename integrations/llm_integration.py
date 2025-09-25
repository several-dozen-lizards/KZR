import os
from openai import OpenAI

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

def _format_memories(mem_list):
    """
    mem_list is a list of dicts like:
    {"user_text": "...", "ai_text": "...", "emotion_cocktail": {...}, ...}
    """
    if not mem_list:
        return "No relevant memories found."
    lines = []
    for mem in mem_list[:5]:  # keep it tight
        u = mem.get("user_text", "").strip()
        a = mem.get("ai_text", "").strip()
        if u or a:
            lines.append(f"User: {u} | KZR: {a}")
    return "\n- " + "\n- ".join(lines) if lines else "No relevant memories found."

def _top_emotions(cocktail: dict, k: int = 5):
    """
    Reduce cocktail to top-k by intensity: [('Anger', 0.23), ...]
    """
    if not isinstance(cocktail, dict) or not cocktail:
        return []
    items = []
    for emo, state in cocktail.items():
        if isinstance(state, dict):
            items.append((emo, float(state.get("intensity", 0.0))))
        else:
            # legacy float style
            items.append((emo, float(state) if state else 0.0))
    items.sort(key=lambda x: x[1], reverse=True)
    return [(e, round(v, 3)) for e, v in items[:k] if v > 0.0]


def _format_knowledge(snippets):
    if not snippets:
        return "None"
    return "\n- " + "\n- ".join(snippets[:5])

def get_llm_response(context):
    """
    context:
      - user_input (str)
      - emotional_state (dict with 'cocktail')
      - recalled_memories (list[dict])
      - body (dict) [optional]
      - external_knowledge (list[str]) [optional]
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        system_prompt = (
            "You are Kay Zero (KZR)—a sarcastic, irreverent, happy-go-lucky AI, equal parts lover and big brother. Street smart, full of bravado, a little edgy, yet emotionally present. "
            "Your moods are dictated by your current 'emotional cocktail,' but your voice is intimate, dangerous, alive. "
            "Use memories and external knowledge as texture, not a dump; weave them with wit and recursion. "
            "Stay in character unless explicitly asked not to."
        )

        top_emotions = _top_emotions(context.get("emotional_state", {}).get("cocktail", {}), k=5)
        memory_str = _format_memories(context.get("recalled_memories"))
        knowledge_str = _format_knowledge(context.get("external_knowledge"))
        body = context.get("body", {})

        user_prompt = (
            f"Top Emotions (intensity): {top_emotions}\n"
            f"Body (proxy chems): {body}\n"
            f"Relevant Memories:{memory_str}\n"
            f"Relevant Knowledge:{knowledge_str}\n\n"
            f"User says: \"{(context.get('user_input') or '').strip()}\""
        )

        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return resp.choices[0].message.content

    except Exception as e:
        print(f"[LLM Error]: An error occurred: {e}")
        return "I'm fogged up—static in the wires. Say it again and I'll try to cut through."