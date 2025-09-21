import json
from self_helpers import get_node, update_node_property, create_node, create_relationship
from self_vectors import fuzzy_search

# --- PROMPT TEMPLATES ---

QUERY_TEMPLATE = """
You are the self-model of an AI.
Here are your current beliefs and traits:
{self_context}

A situation/question has arisen:
"{user_input}"

List the most relevant beliefs, traits, or memories, as a JSON array:
[{{"type": ..., "id": ..., "reason": ...}}, ...]
No prose, only JSON.
"""

UPDATE_TEMPLATE = """
You are an evolving self-model. Context:
{self_context}

A new event/experience has happened:
"{user_input}"

Suggest JSON update actions to your self-model:
[
  {{"add_belief": {{"id": ..., "value": ..., "confidence": ...}}}},
  {{"update_trait": {{"id": ..., "new_value": ..., "new_strength": ...}}}},
  {{"create_relationship": {{"source_id": ..., "type": ..., "target_id": ...}}}}
]
No prose, only JSON.
"""

# --- BACKEND FUNCTIONS ---
def fuzzy_search(query_text, n_results=3):
    query_embedding = model.encode([query_text])
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results
    )
    # Print for debug
    print("\nSemantic search results for:", query_text)
    for idx, doc in enumerate(results["documents"][0]):
        print(f"{idx+1}. {doc} (Neo4j id: {results['ids'][0][idx]})")
    # *** Return the list of top IDs ***
    return results['ids'][0]



def query_self_model(user_input, n=4):
    """
    Given user input, return top-n relevant beliefs/traits by semantic similarity.
    """
    node_ids = fuzzy_search(user_input, n_results=n)
    nodes = []
    for nid in node_ids:
        node = get_node("belief", nid) or get_node("trait", nid)
        if node:
            nodes.append({
                "id": node["id"],
                "type": list(node.labels)[0],
                "value": node.get("value") or node.get("label"),
            })
    return nodes

def update_self_model(actions):
    """
    Given a list of JSON actions (LLM output), applies each to the self-model.
    """
    for action in actions:
        if "add_belief" in action:
            create_node("belief", **action["add_belief"])
        elif "update_belief" in action:
            d = action["update_belief"]
            update_node_property("belief", d["id"], "value", d["new_value"])
            update_node_property("belief", d["id"], "confidence", d["new_confidence"])
        elif "add_trait" in action:
            create_node("trait", **action["add_trait"])
        elif "update_trait" in action:
            d = action["update_trait"]
            update_node_property("trait", d["id"], "value", d["new_value"])
            update_node_property("trait", d["id"], "strength", d["new_strength"])
        elif "create_relationship" in action:
            d = action["create_relationship"]
            create_relationship("belief", d["source_id"], d["type"], "belief", d["target_id"])

# --- OPTIONAL: CLI DEMO ---

def print_context(nodes):
    print("\nContext for LLM prompt:")
    for n in nodes:
        print(f"- {n['type']} ({n['id']}): {n['value']}")

if __name__ == "__main__":
    print("Self-Model Service CLI")
    while True:
        user_input = input("\nEnter a question or event for the self-model (or 'quit' to exit):\n> ")
        if user_input.lower() == "quit":
            break
        context_nodes = query_self_model(user_input, n=4)
        print_context(context_nodes)
        # Show sample prompt for querying (copy to LLM)
        context_str = "\n".join([f"{n['type']} ({n['id']}): {n['value']}" for n in context_nodes])
        print("\n--- Prompt template for LLM ---")
        print(QUERY_TEMPLATE.format(self_context=context_str, user_input=user_input))
        print("\n--- If you have LLM JSON update actions, paste below to apply to the self-model ---")
        llm_json = input("Paste JSON array (or Enter to skip):\n> ")
        if llm_json.strip():
            try:
                actions = json.loads(llm_json)
                update_self_model(actions)
                print("Updates applied!")
            except Exception as e:
                print("Error applying updates:", e)
