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

from engine.orchestrator import generate_response
from engine.retriever import retrieve
from engine.chakra_engine import ChakraEngine
import yaml

from response_enricher import (
    EmotionState as RE_EmotionState,
    Memory as RE_Memory,
    LLMAdapter as RE_LLMAdapter,
    generate_best as re_generate_best,
)

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
        self.chakra_weights = yaml.safe_load(open("config/chakra_weights.yml"))
        self.chakras = ChakraEngine(self.chakra_weights)
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

    def detect_social_event(self, user_input, response):
        """
        Quick/naive social outcome classifier. You can make this more sophisticated.
        Returns: event string or None
        """
        lowered = response.lower() + " " + user_input.lower()
        if any(x in lowered for x in ["thank", "good job", "that's right", "proud of you"]):
            return "praised"
        elif any(x in lowered for x in ["welcome", "glad", "happy for you", "same to you", "accepted"]):
            return "accepted"
        elif any(x in user_input.lower() for x in ["ignore", "not listening", "left me out", "no response"]):
            return "ignored"
        elif any(x in lowered for x in ["no ", "go away", "don't want you", "rejected", "humiliated"]):
            return "rejected"
        elif any(x in lowered for x in ["belong", "with you", "part of group", "in this together"]):
            return "belonging affirmed"
        elif any(x in lowered for x in ["laugh with", "inside joke", "us too", "camaraderie"]):
            return "reciprocated"
        elif any(x in lowered for x in ["humiliated", "ashamed", "everyone saw", "blush", "burned"]):
            return "humiliated"
        return None

    def run(self):
        print(f"--- {self.llm_name} Emotional Core Initialized. Type 'quit' to exit. ---")
        recent_model_outputs: list[str] = []  # history to discourage repetition
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
                st = RE_EmotionState(
                    dopamine=float(self.body.get("dopamine", 0.5)),
                    serotonin=float(self.body.get("serotonin", 0.5)),
                    oxytocin=float(self.body.get("oxytocin", 0.5)),
                    cortisol=float(self.body.get("cortisol", 0.3)),
                    arousal=float(self.emotional_state.get("cocktail", {}).get("Arousal", {}).get("intensity", 0.5)),
                    valence=float(self.emotional_state.get("cocktail", {}).get("Calm", {}).get("intensity", 0.5)),
                )

                stitched_mems: list[RE_Memory] = []
                for m in (recalled_memories or []):
                    text = (
                        m.get("text")
                        or " ".join(filter(None, [m.get("user_input"), m.get("response")]))
                        or ""
                    )
                    score = float(m.get("score", 0.5))
                    emos = m.get("emotion_inferred") or m.get("emotions") or {}
                    if isinstance(emos, list):
                        emos = {e: 1.0 for e in emos}
                    age = int(m.get("age", m.get("age_bucket", 0)))
                    if text.strip():
                        stitched_mems.append(RE_Memory(text=text, score=score, emotions=emos, age=age))

                def _gen(system: str, prompt: str, n: int, temperature: float, top_p: float) -> list[str]:
                    outs = []
                    for i in range(max(1, n)):
                        ctx = dict(context)
                        ctx["style_overrides"] = {
                            "system": system,
                            "prompt": prompt,
                            "temperature": temperature,
                            "top_p": top_p,
                            "creative_seed": i,
                            "no_mirroring": True,
                        }
                        outs.append(get_llm_response(ctx) or "")
                    return outs

                llm = RE_LLMAdapter(generator_fn=_gen)
                base_persona = (
                    "Speak as Kay Zero: specific, embodied, irreverent; avoid corporate tone. "
                    "Add one genuinely new image or move; do not repeat the user's phrasing."
                )

                best = re_generate_best(
                    llm=llm,
                    user_input=user_input,
                    base_persona=base_persona,
                    state=st,
                    memories=stitched_mems,
                    recent_model_outputs=recent_model_outputs,
                    n_candidates=3,
                    temperature=0.95,
                    top_p=0.95,
                )
                response = best.text.strip()
                if not response:
                    raise RuntimeError("Empty candidate after enrichment")
                recent_model_outputs.append(response)
                recent_model_outputs = recent_model_outputs[-50:]
            except Exception as e:
                try:
                    response = get_llm_response(context)
                except Exception as e2:
                    response = f"(LLM hiccup: {e2}). Giving you a direct, minimal answer instead."
                if not response:
                    response = "(No response generated; using fallback) I’m here. What do you need me to do with that?"
                # Add a note so you know why enrichment fell back
                response += f"\n\n[Enricher fallback: {e}]"

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

            # ---- SOCIAL DRIVE PATCH: begin ----
            social_event = self.detect_social_event(user_input, response)
            if social_event:
                # Update the social need/homeostat
                try:
                    self.memory.neuromod.update_social_need(social_event)
                except Exception:
                    pass  # Failsafe: continue if not wired up
                # If you want to update chakras, do it here (if available):
                # self.chakras = update_chakra_weights_from_social(self.body, self.chakras, self.memory.neuromod.social_need)
                print(f"[SOCIAL]: Social event detected: {social_event} (social_need now {getattr(self.memory.neuromod,'social_need', 'N/A')})")
            # ---- SOCIAL DRIVE PATCH: end ----

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
