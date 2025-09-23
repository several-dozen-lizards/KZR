import json
import requests

# --- Ollama Configuration ---
# This is the default address for a local Ollama instance.
OLLAMA_URL = "http://localhost:11434/api/generate"

# Define the model to be used.
# IMPORTANT: Make sure you have pulled this model with `ollama pull llama3`
MODEL = "llama3" 

def call_llm(prompt, is_json_mode=False):
    """
    Handles calls to a local Ollama LLM. It can operate in two modes:
    1. Standard text generation.
    2. JSON mode for structured output (emotional inference).
    
    Args:
        prompt (str): The prompt to send to the LLM.
        is_json_mode (bool): If True, requests a JSON object from the model.
    
    Returns:
        str: The LLM's response. Returns an empty JSON string '{}' on failure
             in JSON mode, or an error message in text mode.
    """
    print(f"--- [Ollama Handler]: Sending prompt to {MODEL} (JSON Mode: {is_json_mode})... ---")
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False # We'll get the full response at once
    }
    
    if is_json_mode:
        payload["format"] = "json"

    try:
        # Make the request to the local Ollama server
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status() # This will raise an error for bad status codes (4xx or 5xx)
        
        # The actual text content is in the 'response' key of the JSON payload
        response_text = response.json().get("response", "")
        return response_text

    except requests.exceptions.ConnectionError as e:
        print("="*50)
        print(f"--- [Ollama Handler]: ERROR - Connection refused.")
        print("Is the Ollama server running? Please start it and try again.")
        print("="*50)
    except Exception as e:
        print(f"--- [Ollama Handler]: ERROR - An API call failed: {e} ---")
    
    # Provide a safe fallback to prevent the main application from crashing
    if is_json_mode:
        return '{}'
    else:
        return "An error occurred while trying to generate a response with Ollama."




