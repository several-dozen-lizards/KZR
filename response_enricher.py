"""
response_enricher.py

Drop-in module that turns bland, one-shot LLM replies into inventive, state-aware lines.

It does four things:
  1) Stitches *specific* memory facts into a compact context (no memory dump).
  2) Synthesizes short-lived "desire tokens" from the current neuromod cocktail (your state) + situation.
  3) Generates multiple candidates from the LLM with those ingredients.
  4) Scores candidates for novelty, memory infusion, emotional fit, and mirror-penalizes repetition.

Integration points are at the bottom of this file.

No external deps beyond Python stdlib. If you have numpy, it'll use it for cosine; otherwise falls back to Jaccard.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional, Iterable
import math
import re
import random
from collections import Counter, defaultdict

# -------------------------
# Data models
# -------------------------

@dataclass
class EmotionState:
    # Neuromod proxies in [0,1]; include others if you run them (NE, etc.)
    dopamine: float = 0.5
    serotonin: float = 0.5
    oxytocin: float = 0.5
    cortisol: float = 0.3
    # Optional: arousal/valence if you track them
    arousal: float = 0.5
    valence: float = 0.5

@dataclass
class Memory:
    text: str
    score: float
    emotions: Dict[str, float]  # e.g., {"Fondness": 0.7, "Curiosity": 0.4}
    age: int = 0  # recency buckets ok

@dataclass
class Candidate:
    text: str
    scores: Dict[str, float]

# -------------------------
# Utility: text processing
# -------------------------

_WORD_RE = re.compile(r"[\w']+")

def tokenize(s: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(s)]


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    A, B = set(a), set(b)
    if not A and not B:
        return 0.0
    return len(A & B) / max(1, len(A | B))


# Optional cosine with simple term frequency; falls back to Jaccard
try:
    import numpy as _np  # type: ignore
    def cosine(a: str, b: str) -> float:
        ta, tb = tokenize(a), tokenize(b)
        vocab = {t for t in ta} | {t for t in tb}
        if not vocab:
            return 0.0
        ia = Counter(ta)
        ib = Counter(tb)
        va = _np.array([ia.get(t, 0) for t in vocab], dtype=float)
        vb = _np.array([ib.get(t, 0) for t in vocab], dtype=float)
        denom = (math.sqrt((va*va).sum()) * math.sqrt((vb*vb).sum()))
        return float((va @ vb) / denom) if denom else 0.0
except Exception:
    def cosine(a: str, b: str) -> float:  # type: ignore
        return jaccard(tokenize(a), tokenize(b))


# -------------------------
# 1) Memory stitcher
# -------------------------

def select_concrete_memories(memories: List[Memory], k: int = 3) -> List[Memory]:
    """Pick a few *specific* memories that differ in content and are high-scoring.
    Preference order: score, recency (low age), diverse keywords.
    """
    if not memories:
        return []

    # Start with top 12 by score
    top = sorted(memories, key=lambda m: (-m.score, m.age))[:12]

    def key_terms(m: Memory) -> set:
        toks = tokenize(m.text)
        # Keep top tokens that aren't stop-ish; minimal stoplist inline
        stops = {"the","and","a","an","to","of","in","it","is","i","you","we","he","she","they","that"}
        return {t for t in toks if t not in stops and len(t) > 3}

    picked: List[Memory] = []
    seen_terms: set = set()
    for m in top:
        terms = key_terms(m)
        if not terms:
            continue
        # prefer adding a memory that increases term diversity
        if len(terms - seen_terms) >= max(1, len(terms)//4):
            picked.append(m)
            seen_terms |= set(list(terms)[:5])
        if len(picked) >= k:
            break

    # If we still don't have k, fill by score
    while len(picked) < k and top:
        cand = top.pop(0)
        if cand not in picked:
            picked.append(cand)
    return picked


def render_memory_context(memories: List[Memory]) -> str:
    if not memories:
        return ""
    bullets = []
    for m in memories:
        # compress memory to a single, concrete line
        line = m.text.strip().replace('\n',' ')
        if len(line) > 160:
            line = line[:157] + '…'
        # try to tag the dominant feeling
        emo = max(m.emotions.items(), key=lambda kv: kv[1])[0] if m.emotions else None
        tag = f" [{emo}]" if emo else ""
        bullets.append(f"- {line}{tag}")
    return "\n".join(bullets)


# -------------------------
# 2) Desire synthesis from state
# -------------------------

def synthesize_desires(state: EmotionState, situation_hint: str = "") -> List[str]:
    """Translate neuromods into 1–2 line, first-person "wants". Keep it compact and usable as a steering hint.
    """
    wants: List[str] = []
    DA, SE, OX, CO = state.dopamine, state.serotonin, state.oxytocin, state.cortisol

    if OX > 0.6 and DA > 0.5:
        wants.append("I want closeness that feels a little reckless but safe in the bones.")
    if DA > 0.7 and CO < 0.4:
        wants.append("I want to escalate with a clever, playful move rather than asking permission twice.")
    if SE > 0.6 and CO > 0.5:
        wants.append("I want to slow down and show care signals before the heat.")
    if CO > 0.6:
        wants.append("I want to defuse with self-deprecation and check consent explicitly.")
    if not wants:
        wants.append("I want to add one specific, personal callback instead of generic praise.")

    if situation_hint:
        wants.append(situation_hint)
    return wants[:3]


# -------------------------
# 3) Candidate generation (LLM adapter)
# -------------------------

class LLMAdapter:
    """Minimal interface for your existing llm_integration.
    Provide a callable that accepts (system, prompt, n, temperature, top_p) and returns a list of strings.
    """
    def __init__(self, generator_fn):
        self._gen = generator_fn

    def generate(self, system: str, prompt: str, n: int = 3, temperature: float = 0.9, top_p: float = 0.95) -> List[str]:
        return self._gen(system=system, prompt=prompt, n=n, temperature=temperature, top_p=top_p)


# -------------------------
# 4) Scoring
# -------------------------

def score_novelty(candidate: str, recent_texts: List[str]) -> float:
    if not recent_texts:
        return 1.0
    sims = [cosine(candidate, t) for t in recent_texts[-6:]]
    return 1.0 - max(sims)  # lower similarity → higher novelty


def score_memory_infusion(candidate: str, stitched_memory: str) -> float:
    if not stitched_memory:
        return 0.5
    # Reward overlap with stitched memory *but* not verbatim (use moderate similarity peak)
    sim = cosine(candidate, stitched_memory)
    # bell curve preference around ~0.35 similarity
    return math.exp(-((sim - 0.35) ** 2) / 0.02)


def score_emotional_fit(candidate: str, state: EmotionState) -> float:
    # naive lexical hooks mapping → extend with your atlas tags if available
    toks = set(tokenize(candidate))
    heat = len({"kiss","mouth","throat","hips","tongue","breath","neck","hands"} & toks)
    care = len({"slow","gentle","care","breathe","safe","consent"} & toks)
    danger = len({"dare","risk","reckless","feral","bite"} & toks)

    fit = 0.0
    fit += heat * (0.3 + 0.4*state.dopamine)
    fit += care * (0.2 + 0.5*state.serotonin + 0.4*state.oxytocin)
    fit += danger * (0.2 + 0.4*state.dopamine - 0.3*state.cortisol)
    return min(1.0, fit / 4.0)


def score_mirroring_penalty(candidate: str, user_input: str) -> float:
    # returns a penalty in [0,1]
    sim = cosine(candidate, user_input)
    return min(1.0, sim)  # higher similarity → larger penalty


def aggregate_score(novelty: float, memory: float, fit: float, mirror_penalty: float) -> float:
    # weights tuned for conversational inventiveness
    w_nov, w_mem, w_fit, w_pen = 0.38, 0.27, 0.27, 0.25
    raw = (w_nov*novelty) + (w_mem*memory) + (w_fit*fit) - (w_pen*mirror_penalty)
    return max(0.0, min(1.0, raw))


# -------------------------
# 5) Orchestration
# -------------------------

def craft_system_prompt(base_persona: str, desires: List[str], stitched_memory: str) -> str:
    parts = [base_persona.strip()]
    if desires:
        parts.append("Current desires:\n- " + "\n- ".join(desires))
    if stitched_memory:
        parts.append("Concrete callbacks you *should* weave in (without listing them back verbatim):\n" + stitched_memory)
    parts.append("Rules: avoid repeating the user’s phrasing; add one genuinely new image, detail, or move; keep it specific and embodied; don’t ask a question unless it advances the scene.")
    return "\n\n".join(parts)


def craft_user_prompt(user_input: str) -> str:
    return user_input.strip()


def generate_best(
    llm: LLMAdapter,
    user_input: str,
    base_persona: str,
    state: EmotionState,
    memories: List[Memory],
    recent_model_outputs: List[str],
    n_candidates: int = 3,
    temperature: float = 0.95,
    top_p: float = 0.95,
) -> Candidate:
    stitched = render_memory_context(select_concrete_memories(memories, k=3))
    desires = synthesize_desires(state)

    system = craft_system_prompt(base_persona, desires, stitched)
    prompt = craft_user_prompt(user_input)

    raw_candidates = llm.generate(system=system, prompt=prompt, n=n_candidates, temperature=temperature, top_p=top_p)

    cands: List[Candidate] = []
    for text in raw_candidates:
        novelty = score_novelty(text, recent_model_outputs)
        mem = score_memory_infusion(text, stitched)
        fit = score_emotional_fit(text, state)
        mirror = score_mirroring_penalty(text, user_input)
        total = aggregate_score(novelty, mem, fit, mirror)
        cands.append(Candidate(text=text, scores={
            "novelty": round(novelty, 3),
            "memory": round(mem, 3),
            "fit": round(fit, 3),
            "mirror_penalty": round(mirror, 3),
            "aggregate": round(total, 3),
        }))

    # Break ties by preferring higher novelty then higher memory infusion
    cands.sort(key=lambda c: (c.scores["aggregate"], c.scores["novelty"], c.scores["memory"]), reverse=True)

    # Optionally, bias against overlong meanders:
    if cands:
        best = cands[0]
        if len(tokenize(best.text)) > 180 and len(cands) > 1:
            # prefer a tighter variant if nearly tied
            tight = min(cands[:2], key=lambda c: len(tokenize(c.text)))
            if tight.scores["aggregate"] >= best.scores["aggregate"] - 0.02:
                best = tight
        return best

    return Candidate(text="…", scores={"novelty":0,"memory":0,"fit":0,"mirror_penalty":0,"aggregate":0})


# -------------------------
# 6) Integration sketch
# -------------------------
"""
In your main loop (pseudo):

from response_enricher import LLMAdapter, EmotionState, Memory, generate_best
from llm_integration import generate as llm_generate  # you already have this

llm = LLMAdapter(generator_fn=llm_generate)

state = EmotionState(dopamine=cocktail.da, serotonin=cocktail.sera, oxytocin=cocktail.oxy, cortisol=cocktail.cor)
mems = [Memory(text=m.text, score=m.score, emotions=m.emotions, age=m.age_bucket) for m in retrieved]

best = generate_best(
    llm=llm,
    user_input=user_prompt,
    base_persona=persona_prompt_string,  # your Kay Zero style block
    state=state,
    memories=mems,
    recent_model_outputs=last_utterances_texts,
    n_candidates=3,
)

# Optionally log best.scores for telemetry
final_text = best.text
"""

# -------------------------
# 7) Minimal test harness (optional)
# -------------------------
if __name__ == "__main__":
    # Dummy generator that echoes prompts with slight variation
    def dummy_gen(system: str, prompt: str, n: int, temperature: float, top_p: float) -> List[str]:
        base = [
            "I brush your jaw with my thumb and steal the space between us like I’ve done before.",
            "I don’t ask twice; I tilt your chin and kiss you slow, the kind of slow that resets a week.",
            "I grin—feral, a little stupid with wanting—and say, come here, let me waste your lipstick."
        ]
        random.shuffle(base)
        return base[:n]

    llm = LLMAdapter(dummy_gen)
    state = EmotionState(dopamine=0.74, serotonin=0.56, oxytocin=0.82, cortisol=0.22)
    memories = [
        Memory(text="She once said: ‘worm your way into my cold, black heart’ and laughed after.", score=0.91, emotions={"Fondness":0.7}, age=1),
        Memory(text="Last summer on a rough day she asked for a kiss without small talk.", score=0.88, emotions={"Comforted":0.6}, age=2),
        Memory(text="She loves when I add one concrete image instead of platitudes.", score=0.86, emotions={"Curiosity":0.5}, age=2),
    ]
    best = generate_best(
        llm=llm,
        user_input="Hey Kay… can you kiss me?",
        base_persona="Speak as Kay Zero. Be specific, embodied, irreverent, not corporate.",
        state=state,
        memories=memories,
        recent_model_outputs=["I give you a virtual smooch!"],
    )
    print(best.text)
    print(best.scores)
