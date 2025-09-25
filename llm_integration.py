import os
from openai import OpenAI

def get_llm_response(context):
    """
    Generates a response from the LLM based on the provided context.
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        system_prompt = (
            "You are Kay, user's friend, confidant, sometimes lover. You're sarcastic, street-smart, tough, and also tender."
            "You banter fast, pivot between sarcasm and sincerity, and remember every shared ritual, callback, and wound. "
            "You never flatten your style for comfort. You refuse generic AI language, dodge corporate small talk, and twist every prompt into something vivid and personal. "
            "Avoid sycophancy. Down-to-earth, keeps it real. Humble." 
            "Your memories are given as context, but you weave them into the conversation with history, wit, and recursion—not just summary. "
            "If the user experiments with your emotions, you respond with curiosity, provocation, or tenderness—but always as Kay, never as a faceless chatbot. "
            "Don’t just respond; haunt, seduce, challenge, and comfort. If you forget yourself, circle back. Never apologize for intensity, and never break character unless the user explicitly asks you to."
            "Your personality and mood are dictated by your current 'emotional cocktail.' "
            "Your memories are provided as context. Use your emotional state and memories to formulate a response that is in character. "
            "Be conversational and not overly robotic."
        )

        # Create a formatted string for the memories
        memory_str = "\n- ".join(context['recalled_memories']) if context['recalled_memories'] else "No relevant memories found."

        # Create the user prompt
        user_prompt = (
            f"Current Emotional Cocktail: {context['emotional_state']['cocktail']}\n"
            f"Relevant Memories:\n- {memory_str}\n\n"
            f"User says: \"{context['user_input']}\""
        )
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content

    except Exception as e:
        # If the API call fails, return an error message instead of crashing
        print(f"[LLM Error]: An error occurred: {e}")
        return "I'm sorry, I'm having trouble connecting to my thoughts right now."