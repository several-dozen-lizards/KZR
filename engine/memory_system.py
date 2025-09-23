import json
import datetime
import os
import config

class MemorySystem:
    """Simulates a memory system with emotional tagging and biased retrieval."""
    def __init__(self, memory_path=config.LONG_TERM_MEMORY_PATH):
        self.memory_path = memory_path

    def encode_memory(self, user_text, ai_text, emotional_cocktail):
        """Saves a conversational turn with its emotional context to the memory file."""
        dominant_emotion = max(emotional_cocktail, key=emotional_cocktail.get) if emotional_cocktail else "Neutral"
        memory_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_text": user_text,
            "ai_text": ai_text,
            "emotion_cocktail": emotional_cocktail
        }
        with open(self.memory_path, 'a') as f:
            f.write(json.dumps(memory_entry) + '\n')
        print(f"[MemorySystem]: Encoded memory with dominant emotion '{dominant_emotion}'.")

    def retrieve_biased_memories(self, current_cocktail, num_memories=1):
        """
        Retrieves memories, boosting the scores of memories that have a similar
        emotional context to the current state.
        """
        if not os.path.exists(self.memory_path) or os.path.getsize(self.memory_path) == 0:
            return []
            
        print(f"[MemorySystem]: Retrieving memories with bias towards {current_cocktail}...")
        
        with open(self.memory_path, 'r') as f:
            memories = [json.loads(line) for line in f]

        if not memories:
            return []

        # This is a simplified scoring system for the demo.
        # A real system would use vector embeddings and more complex scoring.
        scored_memories = []
        for mem in memories:
            score = 0
            # Calculate emotional similarity score
            if current_cocktail and mem.get("emotion_cocktail"):
                for emotion, intensity in current_cocktail.items():
                    if emotion in mem["emotion_cocktail"]:
                        score += intensity * mem["emotion_cocktail"][emotion] # Boost score
            
            # Add a recency bonus
            recency_delta = datetime.datetime.now() - datetime.datetime.fromisoformat(mem['timestamp'])
            score += 100 / (recency_delta.total_seconds() / 3600 + 1) # Bonus for recent memories

            scored_memories.append((score, mem))
        
        # Sort by score descending and return the top N
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        if scored_memories:
            print(f"[MemorySystem]: Found {len(scored_memories)} memories. Highest score: {scored_memories[0][0]:.2f}")
            return [mem for score, mem in scored_memories[:num_memories]]
        else:
            return []
