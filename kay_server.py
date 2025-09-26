# kay_server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

# Import your main Kay/Zero engine here.
from main import Core  # Or 'from kay_core import Core' if you split it out

app = Flask(__name__)
CORS(app)

kay_core = Core()
kay_lock = threading.Lock()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    with kay_lock:
        # You might want to wrap this in a try/except for dev
        kay_core.run_one_turn = getattr(kay_core, 'run_one_turn', None)
        if kay_core.run_one_turn is None:
            # Patch in a single-turn method if not present
            def run_one_turn(msg):
                # Replicate a single step from your CLI loop
                kay_core.last_user_input = msg
                kay_core._fs_latest_events = []
                kay_core.external_knowledge = None
                # Adapt from your main loop as needed
                # ...copy the relevant code...
                return {"text": "Not implemented", "state": {}, "memories": []}
            kay_core.run_one_turn = run_one_turn

        reply, state, memories = kay_core.run_one_turn(message)
        return jsonify({"reply": reply, "state": state, "memories": memories})

@app.route('/state', methods=['GET'])
def state():
    # Return current emotional state, neuromod, social_need, persona, etc.
    state = {
        "emotional_cocktail": kay_core.emotional_state.get("cocktail", {}),
        "body": kay_core.body,
        "neuromod": getattr(kay_core.memory, 'neuromod', None).__dict__ if hasattr(kay_core.memory, 'neuromod') else {},
        "persona": getattr(kay_core, 'persona', 'Kay Zero'),
    }
    return jsonify(state)

@app.route('/memories', methods=['GET'])
def memories():
    # Return last N or top-scored memories
    try:
        rec = kay_core.memory.retrieve_biased_memories(kay_core.emotional_state.get('cocktail', {}), num_memories=5)
        return jsonify({"memories": rec})
    except Exception as e:
        return jsonify({"error": str(e), "memories": []})

@app.route('/control', methods=['POST'])
def control():
    data = request.json
    # Set neuromod/creativity/risk/etc directly
    for k, v in data.items():
        if hasattr(kay_core.memory.neuromod, k):
            setattr(kay_core.memory.neuromod, k, v)
    return jsonify({"status": "ok"})

@app.route('/persona', methods=['POST'])
def persona():
    data = request.json
    new_persona = data.get('persona', 'Kay Zero')
    # Set the persona/system prompt
    kay_core.persona = new_persona
    return jsonify({"status": "ok", "persona": new_persona})

if __name__ == '__main__':
    app.run(debug=True, port=8765)
