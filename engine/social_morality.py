# engine/social_morality.py
from typing import Dict

def assess(emotions: Dict[str, Dict], body: Dict[str, float], text: str) -> Dict:
    get = lambda k: (emotions.get(k) or {}).get("intensity", 0.0)
    anger = get("Anger") + get("Frustration")
    fond  = get("Fondness") + get("Comforted")
    anxiety = get("Anxiety")
    pride   = get("Pride")
    sadness = get("Sadness")
    cortisol = body.get("cortisol", 0.5)
    oxytocin = body.get("oxytocin", 0.5)
    t = (text or "").lower()

    embarrassment = 0.35*anxiety + 0.2*sadness + 0.15*max(0, 0.6 - pride) + 0.2*max(0, 0.6 - oxytocin)
    guilt         = 0.4*anxiety + 0.3*sadness + 0.2*anger + 0.1*max(0, 0.6 - pride)
    if any(w in t for w in ["hurt","harm","lied","stole","betray","damage"]):
        guilt += 0.25
    shame        = 0.4*sadness + 0.2*anxiety + 0.2*max(0,0.6-pride) + 0.2*max(0,0.6-oxytocin) + 0.1*(cortisol-0.5)
    standing     = 0.3*(pride - shame) + 0.2*(fond - anger) + 0.1*(oxytocin - cortisol)

    repair = []
    if guilt > 0.35:
        repair += ["apologize-directly", "offer-specific-repair"]
    if embarrassment > 0.35:
        repair += ["context-explain-or-downplay"]
    if shame > 0.35:
        repair += ["self-forgiveness-ritual"]

    return {
        "embarrassment": round(float(embarrassment), 3),
        "guilt": round(float(guilt), 3),
        "shame": round(float(shame), 3),
        "standing_delta": round(float(standing), 3),
        "repair_moves": repair[:2],
    }
