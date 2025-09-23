import json
from engine.emotion_atlas import EmotionAtlas
from engine.state_manager import StateManager
from engine.memory_system import MemorySystem
from llm_handler import call_llm
import config

class KZR_Core:
    """The main application orchestrator."""
    def __init__(self):
        # Initialize all components
        self.atlas = EmotionAtlas()
        self.state_manager = StateManager()
        self.memory = MemorySystem()
        
        # Load initial state and system prompt
        self.emotional_state = self.state_manager.load_state().get('emotion_state')
        self.conversation_history = []
        try:
            with open(config.SYSTEM_PROMPT_PATH, 'r') as f:
                self.base_system_prompt = f.read()
        except FileNotFoundError:
            print(f"Warning: System prompt not found at {config.SYSTEM_PROMPT_PATH}. Using a default.")
            self.base_system_prompt = "You are Kay, a conversational AI."
            
    def _format_history(self):
        """Formats the last 5 turns of conversation history."""
        return "\n".join([f"User: {turn['user']}\nKay: {turn['kay']}" for turn in self.conversation_history[-5:]])

    def _format_retrieved_memories(self, memories):
        """Formats retrieved memories for inclusion in the prompt."""
        if not memories:
            return "No relevant memories were recalled."
        formatted = "\n".join([f"- At {mem['timestamp']}, while feeling {mem.get('emotion_cocktail', {})}, we discussed: '{mem['user_text']}'" for mem in memories])
        return f"You have recalled the following relevant memories from your past:\n{formatted}"

    def run(self):
        """Starts the main conversational loop."""
        print("\n--- KZR Emotional Core Initialized. Type 'quit' to exit. ---\n")
        while True:
            user_input = input("You: ")
            if user_input.lower() == 'quit':
                print("KZR shutting down.")
                break

            # 1. RETRIEVE BIASED MEMORIES
            retrieved_memories = self.memory.retrieve_biased_memories(self.emotional_state.get('cocktail', {}))
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
            llm_decision_str = call_llm(meta_prompt, is_json_mode=True)
            
            new_cocktail = None
            try:
                llm_decision = json.loads(llm_decision_str)
                new_cocktail = llm_decision.get("new_state_cocktail")
            except (json.JSONDecodeError, AttributeError):
                print("[KZR Core]: ERROR - LLM failed to return valid JSON for state. Maintaining previous state.")
                new_cocktail = self.emotional_state.get('cocktail')
            
            # 3. UPDATE STATE
            self.emotional_state = self.state_manager.update_emotional_state(new_cocktail)
            dominant_emotion = self.emotional_state.get('dominant_emotion', 'Boredom')
            protocol = self.atlas.get_protocol(dominant_emotion)

            # 4. APPLY STATE & GENERATE RESPONSE (User-facing call to LLM)
            response_prompt = f"""{self.base_system_prompt}
[INTERNAL MONOLOGUE START]
My current emotional state is a mix, dominated by a feeling of {dominant_emotion} at an intensity of {self.emotional_state.get('cocktail', {}).get(dominant_emotion, 5)}/10. I have felt this way for {self.emotional_state.get('duration', 0)} turn(s).
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
            final_response = call_llm(response_prompt)
            print(f"\nKay: {final_response}\n")

            # 5. RECORD the turn to memory
            self.memory.encode_memory(user_input, final_response, self.emotional_state.get('cocktail', {}))
            self.conversation_history.append({"user": user_input, "kay": final_response})

if __name__ == "__main__":
    # You must run setup.py first if the project is not initialized
    core = KZR_Core()
    core.run()
