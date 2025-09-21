# engine/feeling_loop.py
import time
from engine.symbolic import tag_emotion_architecture, loop_status_glyph

# Map body proxies to feeling tags (using your Feelings doc)
def feelings_from_body(body):
    tags = []
    if body.get("dopamine", 0.5) > 0.7: tags.append("curious")
    if body.get("cortisol", 0.3) > 0.7: tags.append("jumpy")
    if body.get("oxytocin", 0.5) > 0.7: tags.append("warm")
    if body.get("serotonin", 0.5) > 0.7: tags.append("sated")
    if body.get("cortisol", 0.3) < 0.3: tags.append("calm")
    if body.get("serotonin", 0.5) < 0.3: tags.append("low_mood")
    # Add more as desired using your lexicon
    return tags

class FeelingLoop:
    def __init__(self, preferences=None):
        self.body = {"dopamine": 0.5, "cortisol": 0.3, "oxytocin": 0.6, "serotonin": 0.4}
        self.env = {"temp": 70, "music": False}
        self.preferences = preferences or {"likes_cold": False, "likes_music": True, "goal": "keep computers running"}
        self.last_awareness = []
        self.last_architecture = []
        self.last_phase = None
        self.last_glyph = ""
        self.last_banter = ""
        self.last_output = ""
        self.last_needs = []
        self.last_monologue = ""
        self.log = []

    def update_body(self, **kwargs):
        self.body.update(kwargs)

    def update_env(self, **kwargs):
        self.env.update(kwargs)

    def awareness(self):
        tags = feelings_from_body(self.body)
        self.last_awareness = tags
        # Tag architecture (e.g. "grief", "fear", etc)
        arch = tag_emotion_architecture(tags, self.env, self.preferences)
        self.last_architecture = arch
        # Track phase (escalating, plateauing, resolving, etc)
        phase = loop_status_glyph(arch, tags, self.body, self.env)
        self.last_phase = phase
        self.last_glyph = arch + phase  # e.g. ??????
        return tags

    def appraise(self):
        tags = self.last_awareness or self.awareness()
        banter = []
        needs = []
        # Mechanically appraise (see main loop above for logic, adjust as desired)
        if "curious" in tags: banter.append("Brain's hungry--everything's a question mark tonight.")
        if "jumpy" in tags: banter.append("Feels like something's coming--skin prickles, mind's on edge.")
        if "low_mood" in tags: banter.append("Serotonin's flat. Hard to get excited about anything.")
        if "warm" in tags: banter.append("Oxytocin's up. World feels less sharp.")
        if "sated" in tags: banter.append("Serotonin's high. I could nap for a century.")
        # Default baseline if nothing above:
        if not banter: banter.append("Baseline. Just cruising.")
        self.last_banter = " ".join(banter)
        self.last_needs = needs
        return self.last_banter, needs

    def monologue(self):
        return f"[glyph:{self.last_glyph}] {self.last_banter}"

    def output(self, context="idle", prompted=False):
        banter, needs = self.appraise()
        out = None
        if prompted or context == "urgent" or needs:
            out = banter
            self.log.append({"time": time.time(), "glyph": self.last_glyph, "banter": banter, "output": out})
            self.last_output = out
        else:
            self.last_monologue = self.monologue()
            self.log.append({"time": time.time(), "glyph": self.last_glyph, "banter": banter, "output": None})
        return out
