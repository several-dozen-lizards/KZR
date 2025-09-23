import os
import sys
import json
from dotenv import load_dotenv

# This tells Python to look for modules in your project's root folder
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from engine.emotion_atlas import EmotionAtlas
from engine.memory_system import MemorySystem
from integrations.llm_integration import get_llm_response

# Load environment variables from .env file
load_dotenv()

class Core:
    def __init__(self):
        """Initializes the Core application components."""
        self.state_file = "emotional_state.json" # Define the file for saving state
        self.emotional_core = EmotionAtlas()
        self.memory = MemorySystem()
        self.llm_name = os.getenv("LLM_NAME", "KZR")
        
        # --- NEW: Load state from file or create a new one ---
        self.emotional_state = self._load_or_initialize_state()

    def _load_or_initialize_state(self):
        """Loads the emotional state from a file, or creates a new one if not found."""
        try:
            with open(self.state_file, 'r') as f:
                print(f"--- Found existing emotional state. Loading... ---")
                return json.load(f)
        except FileNotFoundError:
            print(f"--- No existing state found. Initializing a neutral emotional state. ---")
            return {"cocktail": {}}

    def _save_state(self):
        """Saves the current emotional state to a file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.emotional_state, f, indent=4)
        print(f"--- Emotional state saved. ---")
    def run(self):
            """The main loop that runs the conversational AI."""
            print(f"--- {self.llm_name} Emotional Core Initialized. Type 'quit' to exit. ---")
            while True:
                user_input = input("You: ")
                if user_input.lower() == 'quit':
                    self._save_state()
                    print(f"--- {self.llm_name} shutting down. ---")
                    break
    
                # --- START OF FIX ---
                # 1. Get the current cocktail from the state.
                current_cocktail = self.emotional_state.get('cocktail', {})
    
                # 2. Call the correct method 'analyze_text' with the user input and the current cocktail.
                updated_cocktail = self.emotional_core.analyze_text(user_input, current_cocktail)
    
                # 3. Put the new, updated cocktail back into the main emotional_state dictionary.
                self.emotional_state['cocktail'] = updated_cocktail
                # --- END OF FIX ---
                
                # The variable 'cocktail' is now the same as 'updated_cocktail'
                cocktail = self.emotional_state.get('cocktail', {})
                print(f"[MemorySystem]: Retrieving memories with bias towards {user_input}...")
    
                # This check for string type is still a good safety measure
                if isinstance(cocktail, str):
                    try:
                        cocktail = json.loads(cocktail)
                    except json.JSONDecodeError:
                        print("[Error] Could not decode the emotional cocktail string. Using an empty cocktail.")
                        cocktail = {}
                
                recalled_memories = self.memory.retrieve_biased_memories(user_input, cocktail)
                self.memory.store_memory(f"User said: '{user_input}'")
    
                print(f"[{self.llm_name}]: Thinking...")
                context = {
                    "user_input": user_input,
                    "emotional_state": self.emotional_state,
                    "recalled_memories": recalled_memories
                }
                response = get_llm_response(context)
                print(f"{self.llm_name}: {response}")
                
                self.memory.store_memory(f"{self.llm_name} responded: '{response}'")
if __name__ == '__main__':
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file. Please set it.")
    core = Core()
    core.run()