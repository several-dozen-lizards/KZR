# engine/mood.py
import datetime as dt, re

def mood_hint(last_turns:list[str]):
    # legacy helper (kept for compatibility)
    text = "\n".join(last_turns[-12:])
    excit = text.count("!")/ max(1,len(text)/200)
    worry = len(re.findall(r"\b(worried|tired|exhaust|anxious|stuck)\b", text, flags=re.I))
    now = dt.datetime.now()
    tod = ("dawn" if 5<=now.hour<8 else "day" if 8<=now.hour<18 else "night")
    if worry>2: tag = "protective, low and careful"
    elif excit>1.0: tag = "wired, playful, fast"
    else: tag = "even, attentive"
    return f"Mood: {tag}; time: {tod}."

# new lightweight, single-turn classifier used by loop.py
def infer_mood(user_text: str) -> str:
    t = user_text.lower()
    score = 0
    tags = []
    if re.search(r"\b(tired|exhaust(ed)?|drained|burn(ed)?\s*out|wiped|hoarse)\b", t): score -= 2; tags.append("exhausted")
    if re.search(r"\b(stress(ed)?|overwhelmed|anxious|panic|frantic)\b", t):          score -= 2; tags.append("stressed")
    if re.search(r"\b(sad|down|blue|depressed|cry|lonely)\b", t):                     score -= 2; tags.append("low")
    if re.search(r"\b(happy|excited|psyched|thrilled|hyped|stoked)\b", t):            score += 2; tags.append("upbeat")
    if re.search(r"\b(angry|mad|furious|pissed)\b", t):                               score -= 2; tags.append("angry")
    if re.search(r"\b(sore|hurt|pain|ache)\b", t):                                    score -= 1; tags.append("hurting")

    if not tags:
        return "neutral: match the user’s energy without overdoing it."
    if any(k in tags for k in ["exhausted","stressed","low","hurting"]):
        return "grounded: soft edges, shorter sentences, practical help first, then warmth."
    if "angry" in tags:
        return "cool-headed: de-escalate, validate anger, offer actionable next steps."
    if "upbeat" in tags:
        return "amped: playful, high-energy cadence, keep momentum, but don’t ramble."
    return "neutral: match the user’s energy."
