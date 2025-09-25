import os
from typing import List, Dict, Tuple

# Optional deps:
#   pip install pypdf python-docx
try:
    from pypdf import PdfReader  # lightweight PDF text extractor
except Exception:
    PdfReader = None

try:
    from docx import Document as DocxDocument
except Exception:
    DocxDocument = None


def _read_txt_like(path: str) -> str:
    """Read plain text or markdown as text."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            return f.read()
    except Exception:
        return ""


def _read_pdf(path: str) -> str:
    """Extract text from a PDF if pypdf is available, else empty."""
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(path)
        parts = []
        for p in reader.pages:
            text = p.extract_text() or ""
            if text:
                parts.append(text)
        return "\n\n".join(parts)
    except Exception:
        return ""


def _read_docx(path: str) -> str:
    """Extract text from a DOCX if python-docx is available, else empty."""
    if DocxDocument is None:
        return ""
    try:
        doc = DocxDocument(path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text)
    except Exception:
        return ""


def _load_docs(knowledge_folder: str) -> List[Dict[str, str]]:
    """
    Load supported files from a folder into a list of {"file": name, "content": text}.
    Supports: .txt, .md, .markdown, .pdf, .docx
    """
    if not os.path.exists(knowledge_folder):
        return []
    docs = []
    for fname in os.listdir(knowledge_folder):
        path = os.path.join(knowledge_folder, fname)
        if not os.path.isfile(path):
            continue

        low = fname.lower()
        content = ""
        if low.endswith((".txt", ".md", ".markdown")):
            content = _read_txt_like(path)
        elif low.endswith(".pdf"):
            content = _read_pdf(path)
        elif low.endswith(".docx"):
            content = _read_docx(path)

        if content and content.strip():
            docs.append({"file": fname, "content": content})
    return docs


def _chunk_doc(content: str, max_chunk_chars: int = 1200) -> List[str]:
    """
    Chunk by paragraph, then merge up to ~max_chunk_chars per chunk.
    Keeps chunks coherent and not too huge.
    """
    paras = [p.strip() for p in content.split("\n") if p.strip()]
    chunks = []
    buf = ""
    for p in paras:
        # If adding this paragraph would exceed cap, flush buffer
        if len(buf) + len(p) + 1 > max_chunk_chars:
            if buf:
                chunks.append(buf.strip())
                buf = ""
        buf = (buf + "\n" + p) if buf else p
    if buf:
        chunks.append(buf.strip())
    return chunks


def _score_chunk(query_words: set, text: str) -> int:
    """
    Naive score: count overlapping words with the query.
    Lowercase + split on whitespace. Good enough for now.
    """
    words = set(text.lower().split())
    return len(query_words & words)


def simple_doc_search(
    query: str,
    knowledge_folder: str = "knowledge",
    max_results: int = 5,
    max_chars: int = 600,
    max_chunk_chars: int = 1200
) -> List[str]:
    """
    Search all supported files for relevant text.
    Returns up to max_results snippets, each capped to max_chars.
    Output format: "(filename.ext): snippet text..."
    """
    docs = _load_docs(knowledge_folder)
    if not docs:
        return []

    # Build chunk list
    chunks: List[Tuple[int, str, str]] = []  # (score, file, text)
    query_words = set((query or "").lower().split())

    for doc in docs:
        file = doc["file"]
        for chunk in _chunk_doc(doc["content"], max_chunk_chars=max_chunk_chars):
            score = _score_chunk(query_words, chunk)
            if score > 0:
                chunks.append((score, file, chunk))

    if not chunks:
        return []

    # Sort by descending score, then truncate each
    chunks.sort(key=lambda t: t[0], reverse=True)
    results = []
    for score, file, text in chunks[:max_results]:
        text = text.strip().replace("\r", " ")
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"
        results.append(f"({file}): {text}")

    return results
