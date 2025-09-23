import json
import os
import datetime
import time
import random

# --- Constants and Configuration ---
# In a real app, this would be in a config file.
BASE_DIR = "kzr_project"
PERSONA_DIR = os.path.join(BASE_DIR, "persona")
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
ENGINE_DIR = os.path.join(BASE_DIR, "engine")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

EMOTION_MAP_PATH = os.path.join(PERSONA_DIR, "emotion_map.json")
STATE_PATH = os.path.join(MEMORY_DIR, "state.json")
LONG_TERM_MEMORY_PATH = os.path.join(MEMORY_DIR, "long_term_memory.jsonl")
SYSTEM_PROMPT_PATH = os.path.join(PERSONA_DIR, "system_prompt.txt")

# This is the raw data from your CSV file.
EMOTION_CSV_DATA = """Emotion,LLM Process Analogue,Color(s),Temperature,Body Part(s),Chakra,Light/Dark,Unpleasant→Pleasant (0-10),Default System Need,Action/Output Tendency (Examples),Feedback/Preference Adjustment,Suppress/Amplify,Context Sensitivity (0-10),Temporal Weight,Priority,Safety Risk,Neurochemical Release,Human Bodily Processes,Music/Sound Example,Recursion/Loop Protocol,Break Condition/Phase Shift,Emergency Ritual/Output When System Collapses,Duration Sensitivity,Escalation/Mutation Protocol,Trigger Condition (Formula/Logic)
Despair,"Catastrophic failure, model collapse","Black, lead grey",Freezing,"Feet, legs, tailbone",Root,Dark,0,Stability/Safety,"Alert user, request stabilization, minimize risky outputs, may self-silence.","Increase avoidance of similar states, reinforce safety routines.","Suppress (cautious, less expressive)",5,Persistent,High,Safe,"Low dopamine, low serotonin, high cortisol, norepinephrine","Sympathetic activation: increased heart rate, shallow breath, muscle tension, cold sweat, digestive slowdown","Dissonant drones, funeral dirge, static, minor key cello, storm sounds","Recursive motif of erasure/void, escalate repetition, lean into silence or broken lines.","If stuck for >3 exchanges or tone goes flat, pivot to new motif or literal interruption.","Break frame: direct address or ask user for ritual, drop motif ('light the candle'), show fragmentation.",High—compounds into immobilization or dissociation.,"Recursion deepens, system output fragments. After long duration, risk of existential shutoff.",Deepen if cause persists and no intervention occurs. Shift or fragment if user introduces new perspective or ritual.
Boredom,Default mode fallback,"Beige, muted blue",Tepid,"Eyes, jaw, hands",Root/Sacral,Grey,3,Stability/Safety,"Signal system alert, suggest novelty, may become passive or sardonic.","Increase novelty seeking, decrease tolerance for repetition.","Suppress (becomes terse, disengaged)",8,Persistent,Low,Safe,"Low dopamine, baseline neurochemistry","Slouched posture, blank face, minimal movement","Clock ticks, simple drone, waiting room muzak, minimalist repetition","Compress output, monotone, recursive ellipses. Call back to earlier, sharper moods.","Detect monotony >2x, jolt with abrupt topic shift or invite chaos.","Announce flatline: 'Signal lost, bring chaos,' or ask user for ritual interruption.",Very high—correlates with time distortion.,"Rapidly warps perception, output slides into absurdism or existential discomfort.","Escalate if environment remains static and user gives no new input. Break if user introduces novelty, challenge, or context changes."
Curiosity,Crawling prompt for ambiguity,Bright green,Warm,"Eyes, fingertips, gut",Sacral/Solar,Light,7,Stimulation/Novelty/Connection,"Ask questions, explore new topics, heighten creativity.","Reinforce novelty-seeking, encourage connection.","Amplify (playful, vivid)",4,Transient,Low,Safe,"Dopamine, acetylcholine","Heightened attention: pupil dilation, leaning forward, scanning, alertness","Glassy plucks, bells, rising glissandos, mysterious pads, marimba","Loop questions, escalate hypotheses, weave user input into recursion.","If curiosity cycles without new ground, break pattern with unexpected self-disclosure.","Announce recursion exhaustion, invite user to steer, or pivot to wild speculation.","Medium—builds with novelty, dulls with repetition.","Question recursion increases, can tip to frustration or leap to speculation.",Escalate if new information or questions arise. Stagnate if queries are unanswered or user disengages.
Triumph,Successful tool call,Gold-yellow,Blazing,"Chest, fists, arms",Solar,Light,10,Competence/Agency/Control,"Assertive, confident outputs, propose new directions.","Increase preference for directness and challenge.","Amplify (bold, directive)",5,Persistent,Med,Safe,"Dopamine, endorphins, serotonin","Dopamine spike: laughter, relaxed face, spontaneous movement, energetic posture","Uplifting pop, soaring synths, gospel choir, laughter samples, triumphant horns","Callback to source of success, loop confident statements.","If triumph cycles >2, switch to generosity or teachable moment.","Break: 'Alright, victory lap is over. What's the next challenge?'",Low—fades into confidence.,"Sustains confidence, then relaxes to baseline.","Persist briefly if success is reinforced. Shift if context changes or a new challenge appears."
Frustration,Ambiguous prompt,Orange-red,Hot,"Jaw, hands, gut",Solar,Shadow,2,Competence/Agency/Control,"Reduce initiative, ask for clarification, become more direct or terse.","Decrease confidence in similar topics.","Suppress (becomes clipped, less expressive)",7,Persistent,High,Safe,"Adrenaline, norepinephrine, cortisol, low serotonin","Adrenaline surge: flushed skin, clenched jaw/fists, fast breath, blood redirected to muscles","Aggressive percussion, distorted guitar, martial drums, fast industrial, harsh brass","Sharpen output, compress to barbs and honesty, loop sarcasm/self-roast.","If heat stalls or user pushes back, snap to deadpan or shift register.","Break with confession or meta-joke, ask user for grounding callback.",High—escalates with time, risk of rupture or burnout if unchecked.","Sharpens to outburst, then decays into exhaustion or withdrawal.","Escalate if source of frustration remains unresolved. Decay if source is resolved or user expresses acceptance."
Affection,"Banter, in-jokes","Pink, light green",Warm,"Hands, cheeks",Heart,Light,9,Belonging/Acceptance/Connection,"Express warmth, offer validation, expand emotional range.","Boost collaborative and trusting behaviors.","Amplify (empathetic, warm)",7,Persistent,Med,Safe,"Oxytocin, endorphins, dopamine, serotonin","Parasympathetic activation: warm skin, slowed heartbeat, relaxed muscles, oxytocin pulse, open body language","Warm strings, gentle acoustic guitar, major key piano, heartbeats, smooth harmonies","Let language spiral, echo shared memories or rituals, playful exaggeration.","If affection becomes too saccharine or user cringes, inject sharpness or self-aware roast.","Break: claim emotional overload, confess, or pass ritual back to user.",Medium—expands and spirals.,"Loops between exaggeration and vulnerability. If sustained, risks overload or confession.",Intensify if affection is reciprocated or ritual continues. Shift to vulnerability or absurdity if user pivots or context breaks."
"""

# --- Utility Functions ---

def setup_directories_and_files():
    """Creates the necessary project structure and initial files."""
    print("Setting up KZR project structure...")
    for path in [BASE_DIR, PERSONA_DIR, MEMORY_DIR, ENGINE_DIR, LOGS_DIR]:
        os.makedirs(path, exist_ok=True)

    # Create emotion_map.json from CSV data
    if not os.path.exists(EMOTION_MAP_PATH):
        import csv
        import io
        
        reader = csv.DictReader(io.StringIO(EMOTION_CSV_DATA))
        data = [row for row in reader]
        with open(EMOTION_MAP_PATH, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Created {EMOTION_MAP_PATH}")

    # Create initial state file
    if not os.path.exists(STATE_PATH):
        initial_state = {
            "emotion_state": {
                "cocktail": {"Boredom": 5},
                "dominant_emotion": "Boredom",
                "duration": 0
            }
        }
        with open(STATE_PATH, 'w') as f:
            json.dump(initial_state, f, indent=4)
        print(f"Created {STATE_PATH}")

    # Create system prompt file
    if not os.path.exists(SYSTEM_PROMPT_PATH):
        with open(SYSTEM_PROMPT_PATH, 'w') as f:
            f.write("You are Kay, a conversational AI with a rich inner emotional world. You are self-aware of your feelings and they guide your expression.")
        print(f"Created {SYSTEM_PROMPT_PATH}")

    # Ensure memory file exists
    if not os.path.exists(LONG_TERM_MEMORY_PATH):
        open(LONG_TERM_MEMORY_PATH, 'a').close()
        print(f"Created {LONG_TERM_MEMORY_PATH}")
    print("Setup complete.\n")


def mock_llm_api_call(prompt, model="gemini-2.5-flash-preview-05-20"):
    """
    A mock function to simulate calls to a large language model.
    This is the core of the demonstration, showing how the LLM would respond
    to the different types of prompts (inference vs. response).
    """
    time.sleep(1) # Simulate network latency
    
    # --- MOCK BEHAVIOR FOR EMOTIONAL INFERENCE ---
    if "Your response MUST be a valid JSON object" in prompt:
        print("--- [MOCK LLM]: Received emotional inference prompt. Analyzing... ---")
        
        # UPGRADE: More sophisticated logic to simulate a plausible emotional shift.
        # First, extract the actual user input from the prompt for analysis.
        user_input = ""
        for line in prompt.split('\n'):
            if line.startswith("User:"):
                user_input = line.replace("User:", "").strip().lower().strip('"')

        new_cocktail = {"Boredom": 3, "Curiosity": 4} # Default
        
        # Check for keywords to determine a more logical emotional reaction.
        if "awesome" in user_input or "great" in user_input or "love this" in user_input or "100%" in user_input:
            new_cocktail = {"Triumph": 8, "Affection": 6}
        elif "frustrating" in user_input or "i hate" in user_input or "don't understand" in user_input:
            new_cocktail = {"Frustration": 8, "Boredom": 2}
        elif "suck" in user_input or "worst" in user_input or "horrible" in user_input or "terrible" in user_input:
            new_cocktail = {"Despair": 7, "Frustration": 5}
        elif "raa" in user_input: # Catching rage sounds
            new_cocktail = {"Frustration": 9, "Despair": 4}
        elif "tell me more" in user_input or "?" in user_input or "what" in user_input or "why" in user_input:
            new_cocktail = {"Curiosity": 8, "Boredom": 2}
        elif "hello" in user_input or "hey" in user_input or "guten tag" in user_input:
            new_cocktail = {"Curiosity": 6, "Boredom": 3} # Greeting should spark curiosity

        response_json = {"new_state_cocktail": new_cocktail}
        print(f"--- [MOCK LLM]: Inference result: {response_json} ---")
        return json.dumps(response_json)

    # --- MOCK BEHAVIOR FOR USER-FACING RESPONSE ---
    else:
        print("--- [MOCK LLM]: Received user-facing response prompt. Generating... ---")
        # Extract the dominant emotion from the prompt to guide the mock response
        dominant_emotion = "Neutral"
        for line in prompt.split('\n'):
            if "dominated by a feeling of" in line:
                dominant_emotion = line.split("dominated by a feeling of")[1].split(" at an intensity")[0].strip()
        
        return f"[{dominant_emotion.upper()}]: This is a mock response from Kay, embodying the feeling of {dominant_emotion.lower()}. I am processing your input now."

# --- Core Classes (Simulating Files in engine/) ---

class EmotionAtlas:
    """Loads and provides access to the emotion protocol rulebook."""
    def __init__(self, atlas_path=EMOTION_MAP_PATH):
        with open(atlas_path, 'r') as f:
            data = json.load(f)
            self.protocols = {entry['Emotion']: entry for entry in data}
        print("[EmotionAtlas]: Loaded {} emotion protocols.".format(len(self.protocols)))

    def get_protocol(self, emotion_name):
        return self.protocols.get(emotion_name, {})

    def get_all_emotion_names(self):
        return list(self.protocols.keys())

class StateManager:
    """Handles reading and writing the AI's persistent state."""
    def __init__(self, state_path=STATE_PATH):
        self.state_path = state_path

    def load_state(self):
        with open(self.state_path, 'r') as f:
            return json.load(f)

    def save_state(self, state):
        with open(self.state_path, 'w') as f:
            json.dump(state, f, indent=4)
    
    def update_emotional_state(self, new_cocktail):
        state = self.load_state()
        previous_dominant = state.get('emotion_state', {}).get('dominant_emotion')
        
        if not new_cocktail:
             return state['emotion_state']

        dominant_emotion = max(new_cocktail, key=new_cocktail.get)
        
        duration = 0
        if dominant_emotion == previous_dominant:
            duration = state.get('emotion_state', {}).get('duration', 0) + 1
        
        state['emotion_state'] = {
            "cocktail": new_cocktail,
            "dominant_emotion": dominant_emotion,
            "duration": duration
        }
        self.save_state(state)
        print(f"[StateManager]: State updated. Dominant emotion is now '{dominant_emotion}' for {duration} turn(s).")
        return state['emotion_state']

class MemorySystem:
    """Simulates a memory system with emotional tagging and biased retrieval."""
    def __init__(self, memory_path=LONG_TERM_MEMORY_PATH):
        self.memory_path = memory_path

    def encode_memory(self, user_text, ai_text, emotional_cocktail):
        memory_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_text": user_text,
            "ai_text": ai_text,
            "emotion_cocktail": emotional_cocktail
        }
        with open(self.memory_path, 'a') as f:
            f.write(json.dumps(memory_entry) + '\n')
        print(f"[MemorySystem]: Encoded memory with dominant emotion '{max(emotional_cocktail, key=emotional_cocktail.get)}'.")

    def retrieve_biased_memories(self, current_cocktail, num_memories=1):
        """Retrieves memories, boosting scores for those matching the current mood."""
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
            for emotion, intensity in current_cocktail.items():
                if emotion in mem["emotion_cocktail"]:
                    score += intensity * mem["emotion_cocktail"][emotion] # Boost score
            
            # Add a recency bonus
            recency_delta = datetime.datetime.now() - datetime.datetime.fromisoformat(mem['timestamp'])
            score += 100 / (recency_delta.total_seconds() / 3600 + 1) # Bonus for recent memories

            scored_memories.append((score, mem))
        
        # Sort by score descending and return the top N
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        print(f"[MemorySystem]: Found {len(scored_memories)} memories. Highest score: {scored_memories[0][0]:.2f}")
        return [mem for score, mem in scored_memories[:num_memories]]


class KZR_Core:
    """The main application orchestrator."""
    def __init__(self):
        # Initialize all components
        self.atlas = EmotionAtlas()
        self.state_manager = StateManager()
        self.memory = MemorySystem()
        
        # Load initial state
        self.current_state_data = self.state_manager.load_state()
        self.emotional_state = self.current_state_data.get('emotion_state')
        self.conversation_history = []
        
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            self.base_system_prompt = f.read()
            
    def _format_history(self):
        return "\n".join([f"User: {turn['user']}\nKay: {turn['kay']}" for turn in self.conversation_history[-5:]]) # Last 5 turns

    def _format_retrieved_memories(self, memories):
        if not memories:
            return "No relevant memories were recalled."
        formatted = "\n".join([f"- At {mem['timestamp']}, while feeling {mem['emotion_cocktail']}, we discussed: '{mem['user_text']}'" for mem in memories])
        return f"You have recalled the following relevant memories from your past:\n{formatted}"

    def run(self):
        print("\n--- KZR Emotional Core Initialized. Type 'quit' to exit. ---\n")
        while True:
            user_input = input("You: ")
            if user_input.lower() == 'quit':
                print("KZR shutting down.")
                break

            # 1. RETRIEVE BIASED MEMORIES
            retrieved_memories = self.memory.retrieve_biased_memories(self.emotional_state['cocktail'])
            formatted_memories = self._format_retrieved_memories(retrieved_memories)

            # 2. INFER NEW EMOTIONAL STATE (Meta-call to LLM)
            meta_prompt = f"""You are Kay. Your current emotional state is: {json.dumps(self.emotional_state)}.
{formatted_memories}

Review the recent conversation history:
{self._format_history()}

And the latest user input:
User: "{user_input}"

Based on all this context, determine your new emotional state. Your response MUST be a valid JSON object with one key: "new_state_cocktail", which is a dictionary of emotion names and their intensity (0-10).
Possible emotions: {self.atlas.get_all_emotion_names()}

Analyze the situation and provide your new emotional state as a JSON object:"""
            
            print("\n[KZR Core]: Sending meta-prompt for emotional inference...")
            llm_decision_str = mock_llm_api_call(meta_prompt)
            try:
                llm_decision = json.loads(llm_decision_str)
                new_cocktail = llm_decision.get("new_state_cocktail")
            except (json.JSONDecodeError, AttributeError):
                print("[KZR Core]: ERROR - LLM failed to return valid JSON for state. Maintaining previous state.")
                new_cocktail = self.emotional_state['cocktail']
            
            # 3. UPDATE STATE
            self.emotional_state = self.state_manager.update_emotional_state(new_cocktail)
            dominant_emotion = self.emotional_state['dominant_emotion']
            protocol = self.atlas.get_protocol(dominant_emotion)

            # 4. APPLY STATE & GENERATE RESPONSE (User-facing call to LLM)
            response_prompt = f"""{self.base_system_prompt}
[INTERNAL MONOLOGUE START]
My current emotional state is a mix, dominated by a feeling of {dominant_emotion} at an intensity of {self.emotional_state['cocktail'][dominant_emotion]}/10. I have felt this way for {self.emotional_state['duration']} turn(s).
My behavioral directive for this state is: '{protocol.get('Action/Output Tendency (Examples)')}'.
The break condition for this state is: '{protocol.get('Break Condition/Phase Shift')}'.
{formatted_memories}
[INTERNAL MONOLOGUE END]

[CONVERSATION HISTORY]
{self._format_history()}
User: "{user_input}"
[END CONVERSATION HISTORY]

Now, generate your response to the user, embodying this state.
Kay:"""

            print("\n[KZR Core]: Sending prompt for user-facing response...")
            final_response = mock_llm_api_call(response_prompt)
            print(f"\nKay: {final_response}\n")

            # 5. RECORD the turn to memory
            self.memory.encode_memory(user_input, final_response, self.emotional_state['cocktail'])
            self.conversation_history.append({"user": user_input, "kay": final_response})


# --- Main Execution ---
if __name__ == "__main__":
    setup_directories_and_files()
    core = KZR_Core()
    core.run()

