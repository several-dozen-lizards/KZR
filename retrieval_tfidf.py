import os, math, re, json
from collections import Counter, defaultdict
from pathlib import Path

_word = re.compile(r"[A-Za-z0-9_']+")

def tokenize(text: str):
    return [w.lower() for w in _word.findall(text or "")]

class TFIDFIndex:
    def __init__(self):
        self.docs = []          # list of {"id": path, "text": str}
        self.df = Counter()     # term -> doc frequency
        self.idf = {}           # term -> idf
        self.tfs = []           # list of Counter per doc
        self.norms = []         # list of L2 norms
        self.N = 0

    def add(self, doc_id: str, text: str):
        tokens = tokenize(text)
        tf = Counter(tokens)
        self.docs.append({"id": doc_id, "text": text})
        self.tfs.append(tf)
        # update DF
        for term in tf.keys():
            self.df[term] += 1

    def finalize(self):
        self.N = max(1, len(self.docs))
        self.idf = {term: math.log(self.N / (1 + df)) for term, df in self.df.items()}
        self.norms = []
        for tf in self.tfs:
            s = 0.0
            for term, c in tf.items():
                w = (1 + math.log(c)) * self.idf.get(term, 0.0)
                s += w*w
            self.norms.append(math.sqrt(s) if s>0 else 1.0)

    def search(self, query: str, top_k: int = 5):
        qtf = Counter(tokenize(query))
        qnorm = 0.0
        for term, c in qtf.items():
            w = (1 + math.log(c)) * self.idf.get(term, 0.0)
            qnorm += w*w
        qnorm = math.sqrt(qnorm) if qnorm>0 else 1.0

        scores = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            for term, qc in qtf.items():
                if term not in tf: 
                    continue
                wq = (1 + math.log(qc)) * self.idf.get(term, 0.0)
                wd = (1 + math.log(tf[term])) * self.idf.get(term, 0.0)
                s += wq * wd
            denom = (self.norms[i] * qnorm) or 1.0
            scores.append((s/denom, i))
        scores.sort(reverse=True)
        out = []
        for sc, i in scores[:top_k]:
            out.append({"score": float(sc), "id": self.docs[i]["id"], "text": self.docs[i]["text"][:1200]})
        return out

def index_dir(path: str, exts={".txt", ".md"}):
    ix = TFIDFIndex()
    p = Path(path)
    for file in p.rglob("*"):
        if file.suffix.lower() in exts and file.is_file():
            try:
                ix.add(str(file), file.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
    ix.finalize()
    return ix
