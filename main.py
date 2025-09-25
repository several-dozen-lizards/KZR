import os
import sys
import json
from dotenv import load_dotenv

# Project path setup
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from engine.emotion_atlas import EmotionAtlas, decay_cocktail
from engine.memory_system import MemorySystem
from integrations.llm_integration import get_llm_response
from engine.embodiment import update_body_from_emotions
from engine.rag_retriever import simple_doc_search
from engine.fs_watcher import FileSystemWatcher
from engine.emotion_classifier import classify_emotion_llm

load_dotenv()

def update_cocktail_from_memories(cocktail, memories, boost=0.15):
    for mem in memories:
        inferred = mem.get("emotion_inferred")
        if not inferred:
            continue
        emotions = [inferred] if isinstance(inferred, str) else inferred
        for emo in emotions:
            if not emo:
                continue
            if isinstance(cocktail.get(emo), dict):
                cocktail[emo]['intensity'] = cocktail[emo].get('intensity', 0) + boost
                cocktail[emo]['age'] = 0
            else:
                cocktail[emo] = {'intensity': boost, 'age': 0}
    return cocktail

def escalate_protocols(cocktail):
    mutations = []
    for emo, state in list(cocktail.items()):
        if state.get('age', 0) > 4 and emo == "Sadness":
            mutations.append(("Numbness", state.get("intensity", 0) * 0.8))
        if state.get('intensity', 0) > 0.4 and emo == "Anger":
            mutations.append(("Rage", state.get("intensity", 0) * 0.5))
    for new_emo, intensity in mutations:
        cocktail[new_emo] = {'intensity': intensity, 'age': 0}
    return cocktail

def heal_deep_feelings(cocktail):
    to_delete = []
    for emo, state in cocktail.items():
        if state.get('age', 0) > 8 and state.get('intensity', 0) < 0.05:
            print(f"[Healing]: {emo} has faded—removing from cocktail.")
            to_delete.append(emo)
    for emo in to_delete:
        del cocktail[emo]
    return cocktail

class Core:
    def __init__(self):
        self.state_file = "emotional_state.json"
        self.bias_file = "emotion_biases.json"
        self.emotional_core = EmotionAtlas()
        self.memory = MemorySystem()
        self.llm_name = os.getenv("LLM_NAME", "KZR")
        self.emotional_state = self._load_or_initialize_state()
        self.body = {"dopamine": 0.5, "cortisol": 0.5, "oxytocin": 0.5, "serotonin": 0.5}
        self.emotion_biases = self._load_or_initialize_biases()
        self._apply_biases_to_cocktail()

        # File-system watcher
        try:
            self.fs_watcher = FileSystemWatcher(watch_paths=["engine","integrations","main.py","ethics.yml","user_prefs.yml"])
        except Exception:
            self.fs_watcher = None
        self._fs_latest_events = []

    def _load_or_initialize_state(self):
        try:
            with open(self.state_file, 'r') as f:
                print(f"--- Found existing emotional state. Loading... ---")
                return json.load(f)
        except FileNotFoundError:
            print(f"--- No existing state found. Initializing a neutral emotional state. ---")
            return {"cocktail": {}}

    def _load_or_initialize_biases(self):
        if os.path.exists(self.bias_file):
            with open(self.bias_file, "r") as f:
                return json.load(f)
        return {e: 0.0 for e in self.emotional_core.get_all_emotion_names()}

    def _save_state(self):
        with open(self.state_file, 'w') as f:
            json.dump(self.emotional_state, f, indent=4)
        print(f"--- Emotional state saved. ---")

    def _save_biases(self):
        with open(self.bias_file, "w") as f:
            json.dump(self.emotion_biases, f, indent=2)

    def _apply_biases_to_cocktail(self):
        for emo, bias in self.emotion_biases.items():
            if abs(bias) > 0.01:
                self.emotional_state["cocktail"][emo] = {'intensity': max(bias, 0), 'age': 0}

    def run(self):
        print(f"--- {self.llm_name} Emotional Core Initialized. Type 'quit' to exit. ---")
        while True:
            user_input = input("You: ")
            if user_input.lower() == 'quit':
                self._save_state()
                self._save_biases()
                print(f"--- {self.llm_name} shutting down. ---")
                break

            # Poll FS watcher (non-blocking; just collect notes)
            if self.fs_watcher:
                try:
                    self._fs_latest_events = self.fs_watcher.poll()
                except Exception:
                    self._fs_latest_events = []

            # 1. RAG
            external_knowledge = simple_doc_search(user_input)

            # 2. Update cocktail with input
            current_cocktail = self.emotional_state.get('cocktail', {})
            updated_cocktail = self.emotional_core.analyze_and_update_cocktail(user_input, current_cocktail)
            self.emotional_state['cocktail'] = updated_cocktail

            # 3. Retrieve memories and update cocktail from memory emotions
            print(f"[MemorySystem]: Retrieving memories with bias towards '{user_input}'...")
            recalled_memories = self.memory.retrieve_biased_memories(updated_cocktail)
            updated_cocktail = update_cocktail_from_memories(updated_cocktail, recalled_memories)
            self.emotional_state['cocktail'] = updated_cocktail

            # 4. Decay, escalate, heal
            updated_cocktail = decay_cocktail(updated_cocktail)
            updated_cocktail = escalate_protocols(updated_cocktail)
            updated_cocktail = heal_deep_feelings(updated_cocktail)
            self.emotional_state['cocktail'] = updated_cocktail

            # 5. Update embodiment/body from cocktail
            self.body = update_body_from_emotions(self.body, updated_cocktail)

            # 6. LLM output
            print(f"[{self.llm_name}]: Thinking...")
            context = {
                "user_input": user_input,
                "emotional_state": self.emotional_state,
                "recalled_memories": recalled_memories,
                "body": self.body,
                "external_knowledge": external_knowledge
            }
            try:
                response = get_llm_response(context)
            except Exception as e:
                response = f"(LLM hiccup: {e}). Giving you a direct, minimal answer instead."
            if not response:
                response = "(No response generated; using fallback) I’m here. What do you need me to do with that?"

            # Append FS watcher notes non-blocking
            if self._fs_latest_events:
                notes = "\n\n—\nHeads-up: I noticed changes to my codebase:\n"
                for ev in self._fs_latest_events[:5]:
                    notes += f"• {ev['type'].upper()}: {ev['path']}"
                    if ev.get("diff_file"):
                        notes += f" (diff: {ev['diff_file']})"
                    notes += "\n"
                notes += "Say 'inspect last change' if you want a summary."
                response = response + notes

            # 7. Speak
            print(f"{self.llm_name}: {response}")

            # 8. Emotion tagging + memory encode
            emotion_inferred = classify_emotion_llm(user_input, response, "")
            for emo in emotion_inferred:
                if emo in ["Comforted", "Fondness"]:
                    self.emotion_biases[emo] = self.emotion_biases.get(emo, 0.0) + 0.05
                elif emo in ["Shame", "Hurt"]:
                    self.emotion_biases[emo] = self.emotion_biases.get(emo, 0.0) - 0.05
            self._save_biases()

            self.memory.encode_memory(
                user_input,
                response,
                updated_cocktail,
                emotion_inferred
            )

if __name__ == '__main__':
    core = Core()
    core.run()
