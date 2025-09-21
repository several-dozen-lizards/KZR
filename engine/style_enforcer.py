
from __future__ import annotations
from typing import List
def enforce(text: str, motifs: List[str] | None = None) -> str:
    sterile = ["- ", "* ", "1.", "As an AI", "I am unable"]
    if any(m in text for m in sterile) or len(text.splitlines()) < 2:
        add = "\n\n(He laughs under his breath, smoke-scented and unrepentant.)"
        text = text.strip()
        if not text.endswith(add): text += add
    if motifs:
        salt = " • ".join(motifs[:3])
        if salt and salt not in text:
            text += f"\n\n—echoes: {salt}"
    return text
