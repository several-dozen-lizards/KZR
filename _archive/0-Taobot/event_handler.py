from datetime import datetime
from self_helpers import create_node
from self_vectors import model, collection  # model: sentence_transformer, collection: Chroma
from self_llm_interface import prompt_llm_with_context_boredom, apply_updates



def log_event(event_text, metadata=None):
    """
    Logs a new user/environment event to the self-model as an 'event' node (with timestamp and embedding).
    """
    event_id = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    embedding = model.encode([event_text])[0].tolist()
    node_props = {
        "id": event_id,
        "type": "event",
        "text": event_text,
        "timestamp": datetime.now().isoformat(),
        "embedding_id": event_id  # Chroma doc ID
    }
    if metadata:
        node_props.update(metadata)
    # 1. Create node in Neo4j
    create_node("event", **node_props)
    # 2. Add to Chroma for semantic search
    collection.add(
        embeddings=[embedding],
        documents=[event_text],
        ids=[event_id]
    )
    print(f"Logged event: {event_id}")
    return event_id

# --- Trigger full self-model update with event input ---
def process_new_event(event_text):
    event_id = log_event(event_text)
    # 1. Use embedding to find relevant context (now includes events)
    from self_vectors import fuzzy_search
    context_ids = fuzzy_search(event_text, n_results=4)
    from self_helpers import get_node
    context_nodes = []
    for nid in context_ids:
        node = get_node("belief", nid) or get_node("trait", nid) or get_node("event", nid)
        if node:
            context_nodes.append(node)
    context = "\n".join([f"{n['id']}: {n.get('value', n.get('text', ''))}" for n in context_nodes])
    # 2. Prompt LLM with event and context (reuse your prompt_llm_with_context)
    llm_output = prompt_llm_with_context_boredom(event_text, context)
    print("LLM raw output:", llm_output)
    if llm_output.strip().upper().startswith("NO UPDATE"):
        print("Event ignored: nothing meaningful to update.")
        return
    else:
        from self_llm_interface import apply_updates
        apply_updates(llm_output)
        print("Self-model updated with new event and LLM suggestions.")
    if len(event_text) > 60 or "!" in event_text.lower() or "realized" in event_text.lower():
        print("[dialogue] Starting internal dialogue on event...")
        run_internal_dialogue(topic=event_text, rounds=2)


# --- CLI test ---
if __name__ == "__main__":
    print("User/Event Logging & Self-Model Updater")
    while True:
        user_input = input("\nEnter a new event/experience (or 'quit' to exit):\n> ")
        if user_input.lower() == "quit":
            break
        process_new_event(user_input)
