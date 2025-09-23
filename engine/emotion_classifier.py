import openai

def classify_emotion_llm(user_text, ai_text, context):
    prompt = (
        "You are an emotion classifier. Based on the following conversation, "
        "user input, and AI response, what is the dominant emotion or emotions for the USER? "
        "Respond ONLY with a comma-separated list from the official emotion list (no explanation).\n\n"
        f"User: {user_text}\nAI: {ai_text}\nContext: {context}\nEmotion(s):"
    )
    client = openai.OpenAI()
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}]
    )
    emotions = completion.choices[0].message.content.strip()
    return [e.strip() for e in emotions.split(",")]
