import os
from openai import OpenAI

MODEL_NAME = os.getenv("OPENAI_MODEL_CLASSIFIER", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))

LABELS = [
    "Joy","Fondness","Curiosity","Wonder","Calm","Pride",
    "Sadness","Grief","Shame","Guilt","Anxiety","Fear",
    "Anger","Frustration","Boredom","Numbness","Rage","Loneliness",
    "Comforted","Hurt","Confusion","Hope","Relief","Disgust"
]

INSTRUCTION = (
    "Classify the user's last message and the assistant's last reply into 1–3 emotions "
    "from the provided label set. Return a JSON array of strings, e.g. [\"Curiosity\",\"Fondness\"]. "
    "Do not include anything else."
)

def classify_emotion_llm(user_text: str, ai_text: str, _ignored_context_str: str = ""):
    """
    Lightweight classifier: only needs last user + last AI text.
    Returns a Python list of strings (emotion labels).
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        messages = [
            {"role": "system", "content": INSTRUCTION + f"\nValid labels: {', '.join(LABELS)}"},
            {"role": "user", "content": f"User: {user_text}\nAssistant: {ai_text}"}
        ]
        resp = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        raw = resp.choices[0].message.content.strip()
        # Be defensive on parsing
        import json
        try:
            labels = json.loads(raw)
            if isinstance(labels, list):
                # sanitize to known labels
                return [l for l in labels if l in LABELS][:3]
        except Exception:
            pass
        # fallback: empty or unknown
        return []
    except Exception as e:
        print(f"[Classifier Error]: {e}")
        return []
