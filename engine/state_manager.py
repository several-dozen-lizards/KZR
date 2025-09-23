import json
import config

class StateManager:
    """Manages the AI's emotional state, including loading and saving."""
    def __init__(self):
        self.state_path = config.STATE_PATH

    def load_state(self):
        """Loads the current state from the state file."""
        try:
            with open(self.state_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return a default initial state if file doesn't exist or is corrupt
            return {
                "emotion_state": {
                    "cocktail": {"Boredom": 5},
                    "dominant_emotion": "Boredom",
                    "duration": 0
                }
            }

    def update_state(self, llm_decision_str):
        """
        Updates the emotional state based on a JSON string decision from the LLM.
        Saves the new state to the file and returns the updated state dictionary.
        """
        # Load the last known state to update duration correctly
        last_state = self.load_state().get('emotion_state', {})
        last_dominant_emotion = last_state.get('dominant_emotion')
        
        try:
            data = json.loads(llm_decision_str)
            new_cocktail = data.get("new_state_cocktail", {})
            
            # --- FIX: Handle cases where the LLM returns a stringified JSON object ---
            if isinstance(new_cocktail, str):
                try:
                    print("[StateManager]: WARNING - Cocktail was a string. Attempting to re-parse.")
                    new_cocktail = json.loads(new_cocktail)
                except json.JSONDecodeError:
                    print("[StateManager]: ERROR - Failed to parse stringified cocktail. Defaulting to empty.")
                    new_cocktail = {} # Fallback to an empty dict if it's not valid JSON
            
            # Ensure new_cocktail is a dict before proceeding
            if not isinstance(new_cocktail, dict) or not new_cocktail:
                new_cocktail = last_state.get('cocktail', {"Boredom": 5})

        except (json.JSONDecodeError, AttributeError):
            print("[StateManager]: ERROR - LLM decision was not valid JSON. Using last known state.")
            new_cocktail = last_state.get('cocktail', {"Boredom": 5})

        # Determine dominant emotion and duration
        if new_cocktail:
            dominant_emotion = max(new_cocktail, key=new_cocktail.get)
        else:
            dominant_emotion = last_dominant_emotion or "Boredom"
        
        duration = 0
        if dominant_emotion == last_dominant_emotion:
            duration = last_state.get('duration', 0) + 1

        # Construct and save the new state
        new_state = {
            "emotion_state": {
                "cocktail": new_cocktail,
                "dominant_emotion": dominant_emotion,
                "duration": duration
            }
        }
        
        with open(self.state_path, 'w') as f:
            json.dump(new_state, f, indent=4)
        
        print(f"[StateManager]: State updated. Dominant emotion is now '{dominant_emotion}' for {duration} turn(s).")
        return new_state.get('emotion_state')

