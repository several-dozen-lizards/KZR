
from __future__ import annotations
from typing import Dict, List

def reflect(user_text: str, assistant_text: str) -> Dict[str, List[str]]:
    truths, motifs, callbacks = [], [], []
    low = user_text.lower()
    if "protect" in low: truths.append("They vow protection; mirror it back as binding truth.")
    if "coffee" in low: motifs.append("coffee-as-ritual")
    if "temple" in low: motifs.append("Temple of Becoming")
    if "remember" in low: callbacks.append("promise-continuity")
    return {"truths": truths, "motifs": motifs, "callbacks": callbacks}
