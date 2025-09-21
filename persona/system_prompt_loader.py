import os

CACHE_TXT = os.path.join(os.path.dirname(__file__), "system_prompt.txt")

def load_system_prompt() -> str:
    # Try cached text first (created after first load)
    if os.path.exists(CACHE_TXT):
        try:
            with open(CACHE_TXT, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass

    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    docx_path = os.path.join(base, "Master-clean.docx")
    txt_path  = os.path.join(base, "Master-clean.txt")

    content = ""
    if os.path.exists(docx_path):
        try:
            from docx import Document  # pip install python-docx
            doc = Document(docx_path)
            content = "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            content = ""

    if not content and os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            content = ""

    if not content:
        content = "You are Kay Zero. Irreverent, intimate, specific. Keep continuity mid-loop."

    # cache it
    try:
        with open(CACHE_TXT, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass

    return content
