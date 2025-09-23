import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- OpenAI API Configuration ---
# Securely load the API key from environment variables
try:
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=OPENAI_API_KEY)
except KeyError:
    print("="*50)
    print("ERROR: OPENAI_API_KEY not found in .env file or environment variables.")
    print("Please create a .env file and add your API key to it.")
    print("="*50)
    exit()

# Define the model to be used. gpt-4-turbo is recommended for its JSON mode support.
MODEL = "gpt-4-turbo" 

def call_llm(prompt, is_json_mode=False):
    """
    Handles calls to the OpenAI LLM. It can operate in two modes:
    1. Standard text generation.
    2. JSON mode for structured output (emotional inference).
    
    Args:
        prompt (str): The prompt to send to the LLM.
        is_json_mode (bool): If True, forces the LLM to return a JSON object.
    
    Returns:
        str: The LLM's response. Returns an empty JSON string '{}' on failure
             in JSON mode, or an error message in text mode.
    """
    print(f"--- [OpenAI Handler]: Sending prompt to {MODEL} (JSON Mode: {is_json_mode})... ---")
    
    try:
        if is_json_mode:
            # Use OpenAI's dedicated JSON mode for reliable structured output
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
        else:
            # Standard text generation
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
        
        # Extract the content from the response object
        return response.choices[0].message.content

    except Exception as e:
        print(f"--- [OpenAI Handler]: ERROR - An API call failed: {e} ---")
        # Provide a safe fallback to prevent the main application from crashing
        if is_json_mode:
            return '{}' # Return an empty JSON object string on failure
        else:
            return "An error occurred while trying to generate a response with the OpenAI API."

