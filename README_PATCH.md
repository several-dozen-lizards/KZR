# Kay Fix Pack — Drop-in Instructions

1) **Kill leaks & bloat**
   - Delete any scripts that `setx` or persist API keys.
   - Add `.gitignore` from this pack; commit it first.
   - `git rm -r --cached memory logs __pycache__ *.sqlite3 *.duckdb` then commit.

2) **Pin and install**
   - Replace your `requirements.txt` with this pinned one.
   - `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

3) **Unify logs**
   - Use `logger.py` everywhere you write messages.
   - Run `python log_migration.py logs/` to normalize old JSONL files.

4) **Choose a spine**
   - If you want terminal-only: keep `app.py`, remove or ignore the web server.
   - If you want web-only: keep the FastAPI server, cut the CLI loop.
   - Don’t run both until behavior is stable.

5) **Retrieval (optional, simple)**
   - Put text sources in `vault/`.
   - Import `TFIDFIndex` from `retrieval_tfidf.py` and feed hits into the system prompt (see `generate_reply.py`).

6) **Seed prompt**
   - Use `seed_prompt.kay.txt` as the runtime system message.
   - Keep your long manifesto elsewhere; do not stuff the context window.

7) **Feelings wiring (optional)**
   - Provide a dict like `{"arousal":0..1, "edge":0..1}` to `generate_reply()`.
   - It will bias temperature and output length.

8) **Run**
   - Set up `.env` from `.env.example` with your real key.
   - Use `generate_reply.py` as a reference for your main loop.
