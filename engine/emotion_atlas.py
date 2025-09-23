import json
import config

class EmotionAtlas:
    """Loads and provides access to the emotion protocol rulebook."""
    def __init__(self, atlas_path=config.EMOTION_MAP_PATH):
        try:
            with open(atlas_path, 'r') as f:
                data = json.load(f)
                self.protocols = {entry['Emotion']: entry for entry in data}
            print(f"[EmotionAtlas]: Loaded {len(self.protocols)} emotion protocols.")
        except FileNotFoundError:
            print(f"[EmotionAtlas]: ERROR - Emotion map not found at {atlas_path}. Please run setup.py.")
            self.protocols = {}
        except json.JSONDecodeError:
            print(f"[EmotionAtlas]: ERROR - Could not decode JSON from {atlas_path}.")
            self.protocols = {}


    def get_protocol(self, emotion_name):
        """Fetches the full protocol dictionary for a given emotion."""
        return self.protocols.get(emotion_name, {})

    def get_all_emotion_names(self):
        """Returns a list of all available emotion names."""
        return list(self.protocols.keys())
