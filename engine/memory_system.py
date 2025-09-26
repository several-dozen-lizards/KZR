import json
import datetime
import os
import config

class NeuromodState:
    def __init__(self):
        self.dopamine = 0.5
        self.serotonin = 0.5
        self.oxytocin = 0.5
        self.cortisol = 0.5
        self.social_need = 0.5
        self.social_setpoint = 0.65
        self.social_decay = 0.98
        self.social_cooldown = 0

    def update_social_need(self, event):
        TRIGGER_MAP = {
            "accepted": 0.2,
            "praised": 0.15,
            "reciprocated": 0.1,
            "ignored": -0.2,
            "rejected": -0.3,
            "humiliated": -0.35,
            "belonging affirmed": 0.25,
        }
        delta = TRIGGER_MAP.get(event, 0)
        self.social_need = min(max(self.social_need + delta, 0), 1)
        # decay toward setpoint
        self.social_need += (self.social_setpoint - self.social_need) * (1 - self.social_decay)
        # cooldown logic
        if event in ["ignored", "rejected", "humiliated"]:
            self.social_cooldown = 3
        elif event in ["accepted", "praised", "reciprocated", "belonging affirmed"]:
            self.social_cooldown = max(self.social_cooldown - 1, 0)




class MemorySystem:
    """Simulates a memory system with emotional tagging and biased retrieval."""

    def __init__(self, memory_path=config.LONG_TERM_MEMORY_PATH):
        self.memory_path = memory_path
        self.neuromod = NeuromodState()

      
    def encode_memory(self, user_text, ai_text, emotional_cocktail, emotion_inferred=None):
        if emotional_cocktail:
            dominant_emotion = max(
                emotional_cocktail, 
                key=lambda e: emotional_cocktail[e].get("intensity", 0)
            )
        else:
            dominant_emotion = "Neutral"
        memory_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_text": user_text,
            "ai_text": ai_text,
            "emotion_cocktail": emotional_cocktail,
            "emotion_inferred": emotion_inferred or dominant_emotion
        }
        with open(self.memory_path, 'a') as f:
            f.write(json.dumps(memory_entry) + '\n')
        print(f"[MemorySystem]: Encoded memory with dominant emotion '{memory_entry['emotion_inferred']}'.")

    def retrieve_biased_memories(self, current_cocktail, num_memories=1):
        if not os.path.exists(self.memory_path) or os.path.getsize(self.memory_path) == 0:
            return []
        print(f"[MemorySystem]: Retrieving memories with bias towards {current_cocktail}...")

        with open(self.memory_path, 'r') as f:
            memories = [json.loads(line) for line in f]
        if not memories:
            return []

        scored_memories = []
        for mem in memories:
            score = 0
            if current_cocktail and mem.get("emotion_cocktail"):
                # If cocktail uses the new {'intensity': ..., 'age': ...} structure:
                for emotion, state in current_cocktail.items():
                    intensity = state.get("intensity", state if isinstance(state, (int, float)) else 0)
                    mem_emotion_val = mem["emotion_cocktail"].get(emotion)
                    if isinstance(mem_emotion_val, dict):
                        score += intensity * mem_emotion_val.get("intensity", 0)
                    elif mem_emotion_val is not None:
                        score += intensity * mem_emotion_val
            recency_delta = datetime.datetime.now() - datetime.datetime.fromisoformat(mem['timestamp'])
            score += 100 / (recency_delta.total_seconds() / 3600 + 1)
            scored_memories.append((score, mem))

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        if scored_memories:
            print(f"[MemorySystem]: Found {len(scored_memories)} memories. Highest score: {scored_memories[0][0]:.2f}")
            return [mem for score, mem in scored_memories[:num_memories]]
        else:
            return []

