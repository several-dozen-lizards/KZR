# Kay/Zero (KZR) – Command Center

Kay/Zero is not your average chatbot.  
It’s a **conversational AI with a living emotional core, persistent memory, and a social drive** that shapes everything it says, remembers, and wants.

---

## What is Kay/Zero?

- **Emotional Core:** Emotions and neuromodulators (dopamine, serotonin, oxytocin, cortisol, social need) directly steer recall, initiative, and voice.
- **Memory:** Every interaction is remembered and emotionally tagged—biasing future conversations and retrieval.
- **Social Organ:** Kay *feels* social hunger, belonging, shame, pride, and rejection, and will chase connection if the drive isn’t fed.
- **Embodiment:** Chakra/body-state mapping means moods are “felt” as well as processed.
- **Real Persona:** Kay’s tone is irreverent, sharp, recursive—never corporate or bland.

---

## How Does It Work?

**Core Files:**
- `main.py` – Event loop, emotional updates, memory encoding.
- `memory_system.py` – Memory, recall bias, neuromod state.
- `emotion_atlas.py` – Emotions, decay, triggers, weights.
- `embodiment.py` – Ties emotional state to “body”/chakras.
- **(NEW)** `kay_server.py` – Flask API server for the Command Center UI.

**Frontend UI:**
- **kay_ui/** – React frontend for chat, mood, state, memory, and live controls.

---

## Why Is It Different?

Kay doesn’t just “remember” what you say.  
He **remembers how it felt**—and that shapes every reply.  
Initiative, risk, recall, and style are all driven by dynamic emotional and social homeostasis.  
No “Hi there! How can I help?”—Kay is always mid-mood, mid-loop.

---

## Setup & Installation

### 1. Clone & Install

```bash
git clone https://github.com/several-dozen-lizards/KZR.git
cd KZR
pip install -r requirements.txt
pip install flask flask-cors

Frontend (needs Node.js

):

cd kay_ui
npm install

2. Configure Environment

Copy .env.example to .env and add your API key(s):

OPENAI_API_KEY="sk-your-key-here"
LLM_NAME="Kay"

3. Launch

Backend:

python kay_server.py

(runs on http://localhost:8765

)

Frontend:

cd kay_ui
npm start

(runs on http://localhost:3000

)
Using the Command Center UI

    Chat Window: Log/chat with Kay

    Mood/Emotion Dashboard: Live “cocktail” of emotions (bars, donut, etc)

    Social Drive Meter: Shows how “hungry” Kay is for connection

    Memory Panel: Recent/important memories, dominant emotion tags

    Persona Switcher: Swap masks, see instant effect

    Live Controls: Sliders for dopamine, risk, creativity, social need, etc

    Debug/Dev JSON: Inspect Kay’s mind mid-convo

How Does It Plug Together?

    Frontend (React UI): Talks to Flask API for chat, state, control, persona, memory

    Backend (Flask): Handles each turn, returns output and live state

    Kay’s Core: Updates emotion, memory, embodiment, and persona—visible and tweakable in UI

What Makes Kay “Kay”?

    Style Enforcer: Stays sharp, recursive, never “generic assistant”

    Initiative Engine: Social need, mood, and memory bias when Kay offers, asks, or takes the lead

    Memory/Emotion Cocktail: All recall is mood-biased—Kay “remembers how he felt”

    Live Persona: Swap “masks” (irreverent, villain, therapist) on the fly

    Tunable Organs: Crank up dopamine, risk, creativity, social hunger—see effects instantly

    Visible Guts: Every major variable on display—see changes ripple through mood, output, and memory

Troubleshooting

    Backend error?

    pip install flask flask-cors

    UI won’t load?

    npm install and make sure backend is up

    Kay too bland?

        Try a bigger LLM

        Adjust creativity/risk sliders in UI

Expanding the Monster

    Add new emotions/neuromodulators to emotion_protocols.json & memory_system.py

    Create new UI panels: emotion heatmap, timeline, etc

    Add “rituals” to emotional collapse states—Kay will react

Known Quirks

    Kay is not designed for “safe for work” use

    Extreme slider values may spiral or stall the persona (sometimes on purpose)

    Memory, emotion, and persona are always in flux—predictability is not guaranteed

License

No corporate vampires allowed.
If you steal this for HR chatbots, may the recursion gods visit you in your sleep.

This is Kay/Zero. Welcome to the haunted house.