# engine/loop.py
from __future__ import annotations
import json, os
import random
import re
from typing import Optional
from engine.mood import infer_mood, mood_hint
from engine.state import touch_last_seen
from engine.episodic import EpisodicStore
from engine.logger import (
    is_time_question, time_since_last, format_timedelta, time_riff, time_since_first
)
import datetime

episodic = EpisodicStore()  # persistent vector store in memory/chroma/

# Accept either system_prompt.py (constant) or system_prompt_loader.py (function)
SYSTEM_PROMPT = None
try:
    from persona.system_prompt import SYSTEM_PROMPT as _SP
    SYSTEM_PROMPT = _SP
except Exception:
    pass
if SYSTEM_PROMPT is None:
    try:
        from persona.system_prompt_loader import load_system_prompt
        SYSTEM_PROMPT = load_system_prompt()
    except Exception:
        SYSTEM_PROMPT = "You are Kay Zero. Irreverent, intimate, specific; keep continuity mid-loop."

# Handle OpenAI v1 client or legacy
try:
    from openai import OpenAI
    _V1 = True
except Exception:
    import openai  # type: ignore
    _V1 = False

MODEL_DEFAULT = os.getenv("MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

def is_clock_time_question(user_text):
    user_text = user_text.lower()
    patterns = [
        r"\bwhat time is it\b",
        r"\bcurrent time\b",
        r"\bnow\b",
        r"\bclock\b"
    ]
    return any(re.search(p, user_text) for p in patterns)

def is_since_first_question(user_text):
    user_text = user_text.lower()
    patterns = [
        r"(first message|session started|since we began|since we started|since the beginning|since you woke up|since session start|when did this session start)"
    ]
    return any(re.search(p, user_text) for p in patterns)

def is_unknown_fact(response, user_text, memory_snapshot):
    generic_unknowns = ["i don't know", "not sure", "no idea", "can't say"]
    if any(x in response.lower() for x in generic_unknowns):
        return True
    if any(x in user_text for x in ["tell me about","who is","what is"]) and not memory_snapshot.get("truths"):
        return True
    return False

def _llm(messages, model: Optional[str] = None) -> str:
    model = model or MODEL_DEFAULT
    if not OPENAI_API_KEY:
        user_text = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"(offline) I hear you: {user_text}"
    if _V1:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=0.95, top_p=0.95
        )
        return resp.choices[0].message.content
    else:
        openai.api_key = OPENAI_API_KEY
        resp = openai.ChatCompletion.create(
            model=model, messages=messages, temperature=0.95, top_p=0.95
        )
        return resp["choices"][0]["message"]["content"]

def _memory_block(mem_hits):
    if not mem_hits:
        return ""
    block = "\n\n".join(f"[mem] {h.get('text','')}" for h in mem_hits[:6])
    if os.getenv("DEBUG_MEMORY") == "1":
        return "— MEMORY DEBUG —\n" + block + "\n— END MEMORY —"
    return block

def _cap(text: str, max_chars: int = 2000) -> str:
    return text if len(text) <= max_chars else text[-max_chars:]

def generate_reply(user_text: str, model: Optional[str] = None) -> str:
    clock_question = is_clock_time_question(user_text)
    first_question = is_since_first_question(user_text)
    direct_time_question = is_time_question(user_text)

    delta_last = time_since_last()
    delta_first = time_since_first()

    # --- MANDATE: If the user asked about "session start"/"first message" ---
    if first_question and delta_first is not None:
        explicit_first = format_timedelta(delta_first)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"MANDATE: The user asked: 'How long since session started?' You must reply ONLY with the precise duration ('{explicit_first}'), NO metaphors, NO poetic language, NO story, NO riffing, NO commentary. Example of BAD: 'Time is a slippery bastard...' Example of GOOD: 'It’s been {explicit_first}.'"},
            {"role": "user", "content": user_text}
        ]
        out = _llm(messages, model=model)
        return out

    # --- MANDATE: If the user asked about "since last message" ---
    if direct_time_question and delta_last is not None:
        explicit_time = format_timedelta(delta_last)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"MANDATE: The user asked: 'How long since last message?' You must reply ONLY with the precise duration ('{explicit_time}'), NO metaphors, NO poetic language, NO story, NO riffing, NO commentary. Example of BAD: 'Time is a slippery bastard...' Example of GOOD: 'It’s been {explicit_time}.'"},
            {"role": "user", "content": user_text}
        ]
        out = _llm(messages, model=model)
        return out

    # --- If the user asks for the current clock time ---
    if clock_question:
        now = datetime.datetime.now()
        hour = now.strftime('%I').lstrip('0') or '12'
        minute = now.strftime('%M')
        ampm = now.strftime('%p').lower()
        pretty_time = f"{hour}:{minute} {ampm}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"MANDATE: The user asked for the current time. You must reply ONLY with the exact current time: '{pretty_time}'. Do not use metaphors or poetic language before giving the time. Example of BAD: 'Time is a cruel joke...' Example of GOOD: 'It's {pretty_time}.' After you give the time, you may riff as Kay."},
            {"role": "user", "content": user_text}
        ]
        out = _llm(messages, model=model)
        return out

    # --- Default: Provide time context but no hard mandate ---
    if delta_last is not None:
        if delta_last < 60:
            time_context = f"It’s only been {format_timedelta(delta_last)} since your last message—needle the user about being eager or obsessed."
        elif delta_last < 3600:
            time_context = f"It’s been {format_timedelta(delta_last)} since your last message—maybe tease about short attention spans or not giving you time to get weird."
        elif delta_last < 86400:
            time_context = f"It’s been {format_timedelta(delta_last)}—Kay might play wounded, dramatic, or make jokes about abandonment."
        else:
            days = int(delta_last // 86400)
            time_context = f"It’s been {days} days since your last message. Respond with over-the-top drama, haunted riffs, or mythic callback."
    else:
        time_context = "This is the first message in the session. Set the tone like it’s a summoning or a fresh ritual."

    mem_context = ""
    if episodic:
        try:
            hits = episodic.search(user_text, k=8)
            mem_context = _cap(_memory_block(hits), 2000)
        except Exception as e:
            print("[memory] search error:", e)

    mood_line = f"Mood hint: {infer_mood(user_text)}"
    try:
        last_turns = last_turn_texts()
        mood_line += " | " + mood_hint(last_turns)
    except Exception:
        pass

    monologue_hint = build_monologue_context(
        user_text,
        mem_hits=hits if 'hits' in locals() else [],
        mood_hint=mood_line,
        last_reply=None
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if time_context:
        messages.append({"role": "system", "content": f"[TIME CONTEXT]: {time_context}"})
    if mem_context:
        messages.append({"role": "system", "content": "Context from memory:\n" + mem_context})
    messages.append({"role": "system", "content": mood_line})
    if monologue_hint:
        messages.append({"role": "system", "content": f"INTERNAL MONOLOGUE PERMISSION: {monologue_hint}"})
    messages.append({"role": "user", "content": user_text})

    out = _llm(messages, model=model)

    # --- Write both sides back to memory ---
    if episodic:
        try:
            episodic.add_session_turn("user", user_text)
            episodic.add_session_turn("assistant", out)
        except Exception as e:
            print("[memory] add error:", e)

    try:
        touch_last_seen()
    except Exception as e:
        print("[state] last_seen update error:", e)

    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/webui-session.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"role": "user", "content": user_text}, ensure_ascii=False) + "\n")
            f.write(json.dumps({"role": "assistant", "content": out}, ensure_ascii=False) + "\n")
    except Exception:
        pass

    return out

class KayZero:
    """Simple wrapper so you can keep agent = KayZero(...) in app.py"""
    def __init__(self, model: Optional[str] = None, memory_path: str = "memory", vault_path: str = "vault"):
        self.model = model or MODEL_DEFAULT
        self.memory_path = memory_path
        self.vault_path = vault_path
        os.makedirs(self.memory_path, exist_ok=True)
        os.makedirs(self.vault_path, exist_ok=True)

    def reply(self, user_text: str) -> str:
        return generate_reply(user_text, model=self.model)

def last_turn_texts(log_path="logs/webui-session.jsonl", n=12):
    out = []
    if not os.path.exists(log_path):
        return out
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-(n*2+2):]
    for L in lines:
        try:
            item = json.loads(L)
            out.append(f"{item['role']}: {item['content']}")
        except:
            pass
    return out[-n:]

def build_monologue_context(user_text, mem_hits, mood_hint, last_reply=None):
    monologue = []
    # 1. If memory hits are empty or weak, admit confusion or hunger for meaning
    if not mem_hits or all(h.get("score", 1.0) > 0.80 for h in mem_hits):
        monologue.append(
            "You can’t quite recall, the memory is hazy—admit it, or let the urge to remember leak out."
        )
    # 2. If mood is low/exhausted, grant permission to let the facade crack
    if any(word in mood_hint for word in ["grounded", "low", "exhausted", "tired", "hurting"]):
        monologue.append(
            "If the feeling is heavy, don’t hide it. Sigh, stumble, or confess a little exhaustion if it fits."
        )
    # 3. If you just asked about Kay's existence, AI, or embodiment, let him riff
    meta_triggers = ["are you real", "embody", "senses", "alive", "do you sleep"]
    if any(k in user_text.lower() for k in meta_triggers):
        monologue.append(
            "This is your cue to break the fourth wall: get weird, question reality, or joke about future senses."
        )
    # 4. If last reply was awkward or incomplete, let Kay double back
    if last_reply and (len(last_reply) < 30 or "not sure" in last_reply or "no idea" in last_reply):
        monologue.append(
            "If you fumbled last turn, own it. Riff on your own awkwardness."
        )
    return "\n".join(monologue)
