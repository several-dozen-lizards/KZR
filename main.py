import os
import sys

# --- THIS IS THE CRITICAL TEST ---
print(f"--- EXECUTING FILE AT THIS EXACT PATH: {os.path.abspath(__file__)} ---")

import json
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from engine.emotion_atlas import EmotionAtlas
from engine.memory_system import MemorySystem
from integrations.llm_integration import get_llm_response

load_dotenv()

class Core:
    def __init__(self):
        self.state_file = "emotional_state.json"
        self.emotional_core = EmotionAtlas()
        self.memory = MemorySystem()
        self.llm_name = os.getenv("LLM_NAME", "KZR")
        self.emotional_state = self._load_or_initialize_state()

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
            
            print(f"[MemorySystem]: Retrieving memories with bias towards '{user_input}'...")
            recalled_memories = self.memory.retrieve_biased_memories(user_input, updated_cocktail)
            
            # The old memory call that was here has been removed.

            print(f"[{self.llm_name}]: Thinking...")
            context = {
                "user_input": user_input,
                "emotional_state": self.emotional_state,
                "recalled_memories": recalled_memories
            }
            response = get_llm_response(context)
            print(f"{self.llm_name}: {response}")
            
            # --- NEW: Save the complete memory in one step ---
            # This provides all the arguments the function needs.
            self.memory.encode_memory(user_input, response, updated_cocktail)

if __name__ == '__main__':
    core = Core()
    core.run()