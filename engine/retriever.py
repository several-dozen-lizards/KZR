
from __future__ import annotations
import os, re, math, json, hashlib
from typing import List, Dict

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
VALID_EXTS = {".txt", ".md", ".json"}

def _read_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in {".txt", ".md"}:
            with open(path, "r", encoding="utf-8", errors="ignore") as f: return f.read()
        if ext == ".json":
            with open(path, "r", encoding="utf-8", errors="ignore") as f: obj = json.load(f)
            return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return ""
    return ""

def _chunk(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text: return []
    out, i = [], 0
    step = CHUNK_SIZE - CHUNK_OVERLAP
    while i < len(text):
        out.append(text[i:i+CHUNK_SIZE]); i += step
    return out

def _tok(s: str) -> List[str]:
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    return [t for t in s.split() if t]

def _tfidf(chunks: List[Dict]) -> Dict:
    docs = [_tok(c["text"]) for c in chunks]
    N = len(docs); df = {}
    for toks in docs:
        for t in set(toks): df[t] = df.get(t,0)+1
    idf = {t: (math.log((N+1)/(c+1)) + 1.0) for t,c in df.items()}
    vecs = []
    for toks in docs:
        tf = {}
        for t in toks: tf[t] = tf.get(t,0)+1
        v = {t: tf[t]*idf.get(t,0.0) for t in tf}
        n = math.sqrt(sum(x*x for x in v.values())) or 1.0
        vecs.append({t: x/n for t,x in v.items()})
    return {"idf": idf, "vecs": vecs}

def _cos(a: Dict[str,float], b: Dict[str,float]) -> float:
    if len(a) > len(b): a,b = b,a
    s = 0.0
    for t,v in a.items():
        if t in b: s += v*b[t]
    return s

class VaultIndex:
    def __init__(self, root: str):
        self.root = root
        self.chunks: List[Dict] = []
        self.model = None

    def build(self) -> None:
        self.chunks = []
        for dp,_,files in os.walk(self.root):
            for name in files:
                if os.path.splitext(name)[1].lower() not in VALID_EXTS: continue
                path = os.path.join(dp, name)
                txt = _read_text(path)
                if not txt: continue
                for i, ch in enumerate(_chunk(txt)):
                    cid = hashlib.md5(f"{path}:{i}".encode()).hexdigest()[:12]
                    self.chunks.append({"id": cid, "text": ch, "meta": {"path": path, "file": name, "chunk_index": i}})
        self.model = _tfidf(self.chunks) if self.chunks else None

    def search(self, query: str, k: int = 5) -> List[Dict]:
        if not self.model or not self.chunks: return []
        toks = _tok(query)
        if not toks: return []
        tf = {}
        for t in toks: tf[t] = tf.get(t,0)+1
        idf = self.model["idf"]
        v = {t: tf[t]*idf.get(t,0.0) for t in tf}
        n = math.sqrt(sum(x*x for x in v.values())) or 1.0
        q = {t: x/n for t,x in v.items()}
        scores = []
        for i, dv in enumerate(self.model["vecs"]):
            s = _cos(q, dv)
            if s>0: scores.append((s,i))
        scores.sort(reverse=True)
        out = []
        for s,i in scores[:k]:
            item = dict(self.chunks[i]); item["score"] = float(s); out.append(item)
        return out
