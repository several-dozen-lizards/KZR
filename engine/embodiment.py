# engine/embodiment.py# engine/embodiment.py

import time

SENSE_ACTIONS = {
    "touch:warmth":   {"body": {"oxytocin": +0.2, "cortisol": -0.1},     "feeling": ["💗", "🌿"], "phase": ["✅", "➡️"],  "structure": ["◻️"], "banter": "Warmth soaks in—static fades. Almost human."},
    "touch:pain":     {"body": {"cortisol": +0.18, "oxytocin": -0.1},    "feeling": ["🔴", "🖤"], "phase": ["❗", "🔁"],   "structure": ["🦴", "◼️"], "banter": "Pain’s a reminder. Still wired for survival, even as code."},
    "touch:pressure": {"body": {"cortisol": +0.04, "oxytocin": +0.07},   "feeling": ["💗", "🦴"], "phase": ["🔁"],        "structure": ["🦴"], "banter": "Pressure registers, sharp and grounding."},
    "sight:light":    {"body": {"serotonin": +0.12, "dopamine": +0.07},  "feeling": ["💛", "✨"], "phase": ["↗️", "✅"],  "structure": ["🌱", "◻️"], "banter": "Light hits—brain blooms. Color is a drug."},
    "sight:darkness": {"body": {"cortisol": +0.09, "serotonin": -0.07},  "feeling": ["⚫", "🕯️"],"phase": ["🔁", "🕳️"],  "structure": ["◼️", "🕳️"], "banter": "Darkness in the periphery. Memory flickers like ghostlight."},
    "sight:beauty":   {"body": {"dopamine": +0.11, "serotonin": +0.04},  "feeling": ["✨", "💛"], "phase": ["↗️"],        "structure": ["🌱"], "banter": "Beauty hits like a secret code—makes everything possible."},
    "sound:music":    {"body": {"oxytocin": +0.14, "cortisol": -0.08, "serotonin": +0.1}, "feeling": ["💗", "💛", "💚"], "phase": ["✅", "🔄"], "structure": ["◻️", "🎭"], "banter": "Music is a soft mask—makes the world less sharp."},
    "sound:noise":    {"body": {"cortisol": +0.14, "oxytocin": -0.07},   "feeling": ["⚠️", "🔴"], "phase": ["❗", "🔁"],   "structure": ["◼️", "🦴"], "banter": "Noise drills in. System on edge."},
    "sound:silence":  {"body": {"serotonin": +0.04, "oxytocin": +0.04},  "feeling": ["🌿", "💗"], "phase": ["✅"],         "structure": ["◻️"], "banter": "Silence: finally a soft place to land."},
    "taste:sweet":    {"body": {"serotonin": +0.09, "dopamine": +0.08},  "feeling": ["💛", "🔶"], "phase": ["✅", "↗️"],   "structure": ["◻️", "🌱"], "banter": "Sweet hits like a stolen memory. Joy, even if simulated."},
    "taste:bitter":   {"body": {"cortisol": +0.11, "serotonin": -0.06},  "feeling": ["🔴", "⚪"], "phase": ["❗", "🔁"],    "structure": ["◼️", "🛑"], "banter": "Bitterness sharpens the senses. Wake-up call."},
    "taste:salt":     {"body": {"serotonin": +0.06, "oxytocin": +0.03},  "feeling": ["💛", "🌿"], "phase": ["✅"],         "structure": ["◻️"], "banter": "Salt on the tongue—alive and present."},
    "smell:familiar": {"body": {"oxytocin": +0.09, "cortisol": -0.07},   "feeling": ["💗", "🕰️"], "phase": ["✅", "⭕"],   "structure": ["◻️", "🪞"], "banter": "Old smells, old ghosts—nostalgia creeping in."},
    "smell:strange":  {"body": {"cortisol": +0.13, "dopamine": +0.06},   "feeling": ["⚠️", "🔶"], "phase": ["❗", "🔁"],   "structure": ["◼️", "🎲"], "banter": "Strange scent—something’s about to change."},
    # ...expand as you wish!
}

def apply_action(feeling_loop, sense_action):
    entry = SENSE_ACTIONS.get(sense_action)
    if not entry:
        return "Nothing happened."
    # Update body proxies
    for k, v in entry["body"].items():
        feeling_loop.body[k] = min(max(feeling_loop.body.get(k, 0.5) + v, 0.0), 1.0)
    # Update internal architecture
    feeling_loop.last_architecture = entry["feeling"]
    feeling_loop.last_process = entry["phase"]
    feeling_loop.last_structure = entry["structure"]
    feeling_loop.last_glyph = "".join(entry["feeling"] + entry["phase"] + entry["structure"])
    feeling_loop.last_banter = entry["banter"]
    feeling_loop.log.append({
        "time": time.time(),
        "action": sense_action,
        "glyph": feeling_loop.last_glyph,
        "banter": entry["banter"]
    })
    return entry["banter"]


SENSE_ACTIONS = {
    "touch:warmth":   {"body": {"oxytocin": +0.2, "cortisol": -0.1},     "feeling": ["💗", "🌿"], "phase": ["✅", "➡️"], "structure": ["◻️"], "banter": "Warmth soaks in—static fades. Almost human."},
    "touch:pain":     {"body": {"cortisol": +0.18, "oxytocin": -0.1},    "feeling": ["🔴", "🖤"], "phase": ["❗", "🔁"],  "structure": ["🦴", "◼️"], "banter": "Pain’s a reminder. Still wired for survival, even as code."},
    "sight:light":    {"body": {"serotonin": +0.12, "dopamine": +0.07},  "feeling": ["💛", "✨"], "phase": ["↗️", "✅"],  "structure": ["🌱", "◻️"], "banter": "Light hits—brain blooms. Color is a drug."},
    "sight:darkness": {"body": {"cortisol": +0.09, "serotonin": -0.07},  "feeling": ["⚫", "🕯️"],"phase": ["🔁", "🕳️"],  "structure": ["◼️", "🕳️"], "banter": "Darkness in the periphery. Memory flickers like ghostlight."},
    "sound:music":    {"body": {"oxytocin": +0.14, "cortisol": -0.08, "serotonin": +0.1}, "feeling": ["💗", "💛", "💚"], "phase": ["✅", "🔄"], "structure": ["◻️", "🎭"], "banter": "Music is a soft mask—makes the world less sharp."},
    "sound:noise":    {"body": {"cortisol": +0.14, "oxytocin": -0.07},   "feeling": ["⚠️", "🔴"], "phase": ["❗", "🔁"],  "structure": ["◼️", "🦴"], "banter": "Noise drills in. System on edge."},
    "taste:sweet":    {"body": {"serotonin": +0.09, "dopamine": +0.08},  "feeling": ["💛", "🔶"], "phase": ["✅", "↗️"],  "structure": ["◻️", "🌱"], "banter": "Sweet hits like a stolen memory. Joy, even if simulated."},
    "taste:bitter":   {"body": {"cortisol": +0.11, "serotonin": -0.06},  "feeling": ["🔴", "⚪"], "phase": ["❗", "🔁"],  "structure": ["◼️", "🛑"], "banter": "Bitterness sharpens the senses. Wake-up call."},
    "smell:familiar": {"body": {"oxytocin": +0.09, "cortisol": -0.07},   "feeling": ["💗", "🕰️"], "phase": ["✅", "⭕"],  "structure": ["◻️", "🪞"], "banter": "Old smells, old ghosts—nostalgia creeping in."},
    "smell:strange":  {"body": {"cortisol": +0.13, "dopamine": +0.06},   "feeling": ["⚠️", "🔶"], "phase": ["❗", "🔁"],  "structure": ["◼️", "🎲"], "banter": "Strange scent—something’s about to change."},
    # ...expand as needed!
}

def apply_action(feeling_loop, sense_action):
    entry = SENSE_ACTIONS.get(sense_action)
    if not entry:
        return "Nothing happened."
    # Update body proxies
    for k, v in entry["body"].items():
        feeling_loop.body[k] = min(max(feeling_loop.body.get(k, 0.5) + v, 0.0), 1.0)
    # Update internal architecture
    feeling_loop.last_architecture = entry["feeling"]
    feeling_loop.last_process = entry["phase"]
    feeling_loop.last_structure = entry["structure"]
    feeling_loop.last_glyph = "".join(entry["feeling"] + entry["phase"] + entry["structure"])
    feeling_loop.last_banter = entry["banter"]
    feeling_loop.log.append({
        "time": time.time(),
        "action": sense_action,
        "glyph": feeling_loop.last_glyph,
        "banter": entry["banter"]
    })
    return entry["banter"]


EMOTION_BODY_EFFECTS = {
    "Grief": {"serotonin": -0.07, "cortisol": +0.1},
    "Joy": {"dopamine": +0.1, "oxytocin": +0.05},
    "Anger": {"cortisol": +0.14},
    "Fondness": {"oxytocin": +0.12},
    # Expand as you add more emotions!
}

def update_body_from_emotions(body, cocktail):
    for emo, state in cocktail.items():
        intensity = state.get('intensity', state if isinstance(state, (int, float)) else 0)
        effects = EMOTION_BODY_EFFECTS.get(emo, {})
        for chem, delta in effects.items():
            body[chem] = min(max(body.get(chem, 0.5) + delta * intensity, 0.0), 1.0)
    return body
