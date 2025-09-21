# engine/symbolic.py

def tag_emotion_architecture(tags, env, preferences):
    # Very simple: pick architecture based on highest-salience tag
    if "low_mood" in tags: return "🖤"  # grief
    if "jumpy" in tags: return "⚠️"    # fear
    if "curious" in tags: return "🔶"  # courage/expansion
    if "warm" in tags: return "💗"     # love/oxytocin
    if "sated" in tags: return "💛"    # joy
    # ...extend as needed from Feelings doc
    return "◻️"  # default stable

def loop_status_glyph(arch, tags, body, env):
    # Decide loop phase glyph
    if "low_mood" in tags or "jumpy" in tags:
        return "🔁"  # active recursion/looping
    if "sated" in tags or "warm" in tags:
        return "✅"  # resolved/stable
    return "🔁"      # default
