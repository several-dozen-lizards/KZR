import os
import sys
import json
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from engine.emotion_atlas import EmotionAtlas
from engine.memory_system import MemorySystem
from integrations.llm_integration import get_llm_response
from engine.embodiment import update_body_from_emotions  # We'll add this function below

load_dotenv()

def update_cocktail_from_memories(cocktail, memories, boost=0.15):
    """
    For each recalled memory, boost the relevant emotions in the current cocktail.
    """
    for mem in memories:
        inferred = mem.get("emotion_inferred")
        if not inferred:
            continue
        if isinstance(inferred, str):
            emotions = [inferred]
        else:
            emotions = inferred
        for emo in emotions:
            if emo:
                if isinstance(cocktail.get(emo), dict):
                    cocktail[emo]['intensity'] = cocktail[emo].get('intensity', 0) + boost
                    cocktail[emo]['age'] = 0  # reset on new hit
                else:
                    cocktail[emo] = {'intensity': boost, 'age': 0}
    return cocktail

class Core:
    def __init__(self):
        self.state_file = "emotional_state.json"
        self.emotional_core = EmotionAtlas()
        self.memory = MemorySystem()
        self.llm_name = os.getenv("LLM_NAME", "KZR")
        self.emotional_state = self._load_or_initialize_state()
        # Add a body state for embodiment
        self.body = {"dopamine": 0.5, "cortisol": 0.5, "oxytocin": 0.5, "serotonin": 0.5}

    def _load_or_initialize_state(self):
        try:
            with open(self.state_file, 'r') as f:
                print(f"--- Found existing emotional state. Loading... ---")
                return json.load(f)
        except FileNotFoundError:
            print(f"--- No existing state found. Initializing a neutral emotional state. ---")
            return {"cocktail": {}}

    def _save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.emotional_state, f, indent=4)
        print(f"--- Emotional state saved. ---")

    def run(self):
        print(f"--- {self.llm_name} Emotional Core Initialized. Type 'quit' to exit. ---")
        while True:
            user_input = input("You: ")
            if user_input.lower() == 'quit':
                self._save_state()
                print(f"--- {self.llm_name} shutting down. ---")
                break

            current_cocktail = self.emotional_state.get('cocktail', {})
            updated_cocktail = self.emotional_core.analyze_and_update_cocktail(user_input, current_cocktail)
            self.emotional_state['cocktail'] = updated_cocktail

            # 1. Retrieve memories and update cocktail from memory emotions
            print(f"[MemorySystem]: Retrieving memories with bias towards '{user_input}'...")
            recalled_memories = self.memory.retrieve_biased_memories(updated_cocktail)
            updated_cocktail = update_cocktail_from_memories(updated_cocktail, recalled_memories)
            self.emotional_state['cocktail'] = updated_cocktail

            # 2. Decay cocktail (age and fade emotions)
            from engine.emotion_atlas import decay_cocktail
            updated_cocktail = decay_cocktail(updated_cocktail)
            self.emotional_state['cocktail'] = updated_cocktail

            # 3. Update embodiment/body from cocktail
            self.body = update_body_from_emotions(self.body, updated_cocktail)

            # 4. LLM output
            print(f"[{self.llm_name}]: Thinking...")
            context = {
                "user_input": user_input,
                "emotional_state": self.emotional_state,
                "recalled_memories": recalled_memories,
                "body": self.body
            }
            response = get_llm_response(context)
            print(f"{self.llm_name}: {response}")

            # === LLM emotion tagging ===
            from engine.emotion_classifier import classify_emotion_llm
            classifier_context = {
                "emotional_state": self.emotional_state,
                "recalled_memories": recalled_memories,
                "body": self.body
            }
            context_str = json.dumps(classifier_context)
            emotion_inferred = classify_emotion_llm(user_input, response, context_str)

            # 5. Encode memory with both cocktail and inferred emotion
            self.memory.encode_memory(
                user_input,
                response,
                updated_cocktail,
                emotion_inferred
            )

if __name__ == '__main__':
    core = Core()
    core.run()
