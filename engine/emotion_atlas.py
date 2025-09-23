import json
import sys
import os

# This block allows this file to find the 'config.py' in the parent directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import config

class EmotionAtlas:
    """Loads, provides, and uses the emotion protocol rulebook."""
    def __init__(self, atlas_path=config.EMOTION_MAP_PATH):
        try:
            with open(atlas_path, 'r') as f:
                data = json.load(f)
                self.protocols = {entry['Emotion']: entry for entry in data}
            print(f"[EmotionAtlas]: Loaded {len(self.protocols)} emotion protocols.")
        except FileNotFoundError:
            print(f"[EmotionAtlas]: ERROR - Emotion map not found at {atlas_path}.")
            self.protocols = {}
        except (json.JSONDecodeError, KeyError):
            print(f"[EmotionAtlas]: ERROR - Could not decode or parse JSON from {atlas_path}.")
            self.protocols = {}

    def get_protocol(self, emotion_name):
        """Fetches the full protocol dictionary for a given emotion."""
        return self.protocols.get(emotion_name, {})

    def get_all_emotion_names(self):
        """Returns a list of all available emotion names."""
        return list(self.protocols.keys())

    def analyze_and_update_cocktail(self, text, current_cocktail):
        """
        Analyzes text against emotion protocols and updates the emotional cocktail.
        This version ensures it ALWAYS returns a dictionary.
        """
        words = text.lower().split()
        working_cocktail = current_cocktail.copy()

        for emotion, protocol in self.protocols.items():
            for keyword in protocol.get('Keywords', []):
                if keyword in words:
                    intensity = protocol.get('Intensity', 0.1)
                    # If the emotion already exists and is a dict, update intensity and reset age
                    prev = working_cocktail.get(emotion)
                    if isinstance(prev, dict):
                        new_intensity = prev.get('intensity', 0) + intensity
                        working_cocktail[emotion] = {'intensity': new_intensity, 'age': 0}
                    else:
                        working_cocktail[emotion] = {'intensity': intensity, 'age': 0}

        decayed_cocktail = {}
        for emotion, value in working_cocktail.items():
            decay_rate = self.protocols.get(emotion, {}).get('Decay', 0.95)
            if isinstance(value, dict):
                intensity = value.get("intensity", 0)
                age = value.get("age", 0) + 1
            else:
                intensity = value
                age = 1
            new_intensity = intensity * decay_rate
            if new_intensity > 0.01:
                decayed_cocktail[emotion] = {'intensity': new_intensity, 'age': age}

        return decayed_cocktail


def decay_cocktail(cocktail, decay_floor=0.01):
    """
    Decays each emotion in the cocktail over time.
    Higher intensity decays more slowly.
    """
    new_cocktail = {}
    for emo, state in cocktail.items():
        if isinstance(state, dict):
            intensity = state.get('intensity', 0)
            age = state.get('age', 0) + 1
        else:
            intensity = state
            age = 1
        # Decay factor: higher intensity = slower decay
        decay = max(0.98 - (intensity * 0.2), 0.85)
        new_intensity = intensity * decay
        if new_intensity > decay_floor:
            new_cocktail[emo] = {'intensity': new_intensity, 'age': age}
    return new_cocktail
