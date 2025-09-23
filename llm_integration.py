import os
from openai import OpenAI

def get_llm_response(context):
    """
    Generates a response from the LLM based on the provided context.
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        system_prompt = (
            "You are KZR, a conversational AI. Your personality and mood are dictated by your current 'emotional cocktail.' "
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