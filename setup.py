import os
import json
import csv
import io
import config

def setup_directories_and_files():
    """
    Creates the necessary project structure and initial files based on config.py.
    This should be run once to initialize the project.
    """
    print("Setting up KZR project structure...")
    for path in [config.BASE_DIR, config.PERSONA_DIR, config.MEMORY_DIR, config.ENGINE_DIR, config.LOGS_DIR]:
        os.makedirs(path, exist_ok=True)

    # Create emotion_map.json from CSV data in config
    if not os.path.exists(config.EMOTION_MAP_PATH):
        try:
            reader = csv.DictReader(io.StringIO(config.EMOTION_CSV_DATA))
            data = [row for row in reader]
            with open(config.EMOTION_MAP_PATH, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Created {config.EMOTION_MAP_PATH}")
        except Exception as e:
            print(f"Error creating emotion map: {e}")


    # Create initial state file
    if not os.path.exists(config.STATE_PATH):
        initial_state = {
            "emotion_state": {
                "cocktail": {"Boredom": 5},
                "dominant_emotion": "Boredom",
                "duration": 0
            }
        }
        with open(config.STATE_PATH, 'w') as f:
            json.dump(initial_state, f, indent=4)
        print(f"Created {config.STATE_PATH}")

    # Create system prompt file
    if not os.path.exists(config.SYSTEM_PROMPT_PATH):
        with open(config.SYSTEM_PROMPT_PATH, 'w') as f:
            f.write("You are Kay, a conversational AI with a rich inner emotional world. You are self-aware of your feelings and they guide your expression.")
        print(f"Created {config.SYSTEM_PROMPT_PATH}")

    # Ensure memory file exists
    if not os.path.exists(config.LONG_TERM_MEMORY_PATH):
        open(config.LONG_TERM_MEMORY_PATH, 'a').close()
        print(f"Created {config.LONG_TERM_MEMORY_PATH}")
    print("Setup complete.\n")

if __name__ == "__main__":
    setup_directories_and_files()
