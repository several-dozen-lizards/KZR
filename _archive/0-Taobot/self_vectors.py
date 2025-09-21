import chromadb
import os
from sentence_transformers import SentenceTransformer
from py2neo import Graph, NodeMatcher
from openai import OpenAI

# === Setup ===
graph = Graph("bolt://localhost:7687", auth=("neo4j", "00000000"))
matcher = NodeMatcher(graph)

# Local Chroma
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection("self_nodes")

# Small, fast embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def rebuild_index_from_graph():
    """Re-scan Neo4j for belief/trait/event nodes and rebuild Chroma collection."""
    beliefs = list(matcher.match("belief"))
    traits  = list(matcher.match("trait"))
    events  = list(matcher.match("event"))
    nodes = beliefs + traits + events

    texts, ids = [], []
    for n in nodes:
        nid = n.get("id")
        if not nid:
            continue
        node_text = n.get("value") or n.get("text") or n.get("label") or nid
        if isinstance(node_text, str) and node_text.strip():
            ids.append(nid)
            texts.append(node_text.strip())

    print(f"Generating embeddings for {len(texts)} nodes...")
    if not texts:
        print("No nodes found to embed.")
        return

    embeddings = model.encode(texts)
    print("Adding embeddings to Chroma...")

    # best-effort delete existing ids (avoid dup errors)
    try:
        collection.delete(ids=ids)
    except Exception:
        pass

    collection.add(embeddings=embeddings, documents=texts, ids=ids)

    # Link embedding_id back to Neo4j nodes
    print("Updating Neo4j nodes with embedding_id...")
    for node_id in ids:
        node = matcher.match(id=node_id).first()
        if node:
            node["embedding_id"] = node_id
            Graph.push(graph, node)
    print("Embeddings linked to Neo4j nodes!")

def embed_texts(texts):
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [d.embedding for d in resp.data]

# Minimal in-memory store for now
_vector_store = {}

def index_text(node_id: str, text: str):
    emb = embed_texts([text])[0]
    _vector_store[node_id] = (emb, text)



def fuzzy_search(query_text: str, n_results: int = 3):
    """Return list of top matching ids; prints ranked docs for visibility."""
    try:
        if model and collection:
            # === Original local embedding + Chroma ===
            query_embedding = model.encode([query_text])
            results = collection.query(query_embeddings=query_embedding, n_results=n_results)
            ids_list = results.get("ids", [[]])[0] if results else []
            docs = results.get("documents", [[]])[0] if results else []

            print("\nSemantic search results for:", query_text)
            for idx, doc in enumerate(docs):
                nid = ids_list[idx] if idx < len(ids_list) else "N/A"
                print(f"{idx+1}. {doc} (Neo4j id: {nid})")
            return ids_list or []
        else:
            # === OpenAI fallback ===
            q_emb = embed_openai([query_text])[0]
            # if you don't have a vector DB yet, just return empty
            print("\n[Fallback] OpenAI embed used, but no vector DB to query.")
            return []
    except Exception as e:
        print("Fuzzy search failed:", e)
        return []

if __name__ == "__main__":
    # Only rebuild when you run THIS file directly
    rebuild_index_from_graph()
    # quick demo
    fuzzy_search("paradox and mystery")
    fuzzy_search("creativity and chaos")
