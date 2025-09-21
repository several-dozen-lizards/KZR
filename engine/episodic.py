# engine/episodic.py
import os, time
import chromadb
from chromadb.utils import embedding_functions
os.environ["CHROMADB_DISABLE_TELEMETRY"] = "1"

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

class EpisodicStore:
    def __init__(self, path="memory/chroma"):
        os.makedirs(path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=path)
        self.embedder = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name=OPENAI_EMBEDDING_MODEL
        )
        self.session = self.client.get_or_create_collection(
            "session", embedding_function=self.embedder, metadata={"hnsw:space":"cosine"})
        self.diary = self.client.get_or_create_collection(
            "diary", embedding_function=self.embedder, metadata={"hnsw:space":"cosine"})
        self.themes = self.client.get_or_create_collection(
            "themes", embedding_function=self.embedder, metadata={"hnsw:space":"cosine"})

    def add_session_turn(self, role: str, text: str):
        if not text: return
        _id = f"s-{time.time_ns()}"
        self.session.add(ids=[_id], documents=[f"[{role}] {text}"], metadatas=[{"ts": time.time()}])

    def add_diary(self, date_str: str, text: str):
        if not text: return
        _id = f"d-{date_str}-{time.time_ns()}"
        self.diary.add(ids=[_id], documents=[text], metadatas=[{"date": date_str, "ts": time.time()}])

    def upsert_theme(self, week_str: str, text: str):
        if not text: return
        _id = f"w-{week_str}"
        try: self.themes.delete(ids=[_id])
        except: pass
        self.themes.add(ids=[_id], documents=[text], metadatas=[{"week": week_str, "ts": time.time()}])

    def search(self, query: str, k: int = 6):
        if not query: return []
        r1 = self.session.query(query_texts=[query], n_results=max(3, k//2))
        r2 = self.diary.query(query_texts=[query], n_results=max(2, k//3))
        r3 = self.themes.query(query_texts=[query], n_results=max(1, k//6))

        def pack(res):
            docs = res.get("documents", [[]])[0]
            dists = res.get("distances", [[]])[0]
            return [{"text": d, "score": float(s)} for d, s in zip(docs, dists)]
        return pack(r1) + pack(r2) + pack(r3)
