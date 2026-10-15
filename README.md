[SETUP.md](https://github.com/user-attachments/files/33502393/SETUP.md)
# FYPNTU-YJ-# Local AI Image + RAG Pipeline — Setup & Usage

A local, fully offline RAG assistant: ask questions in a browser chat UI, get answers
grounded in your own documents (PDF, Word, Excel, PowerPoint, images), with the
matching source file identified and downloadable. An admin panel lets you manage the
document pool. Everything runs on your machine via Ollama — nothing leaves it.

**Works on Windows 10/11 and macOS (Intel or Apple Silicon).** The application code
itself (Python backend + HTML/JS frontend) is identical on both — only the setup
commands differ, which is what this doc separates out below.

## Architecture

```
Frontend (localhost:3000)  --->  Backend (localhost:8000)  --->  Ollama (localhost:11434)
  plain HTML/JS chat UI           FastAPI, admin GUI              + Chroma vector store
```

- **Frontend** — the chat UI end users interact with. No login required.
- **Backend** — FastAPI server. Serves the public `/ask` API the frontend uses, plus a
  login-protected admin GUI (`/admin`) for uploading documents and managing the index.
- **Ollama** — runs the three local models (vision, embedding, generation).
- **Chroma** — embedded vector database, stored on disk at `backend/chroma_db/` (created
  automatically, don't need to touch it).

---

## 1. Prerequisites

### Windows

1. **Python 3.12+** — [python.org](https://www.python.org/downloads/) (check "Add
   python.exe to PATH" during install) or the Microsoft Store version. Confirm with:
   ```powershell
   python --version
   ```
2. **Ollama** — [ollama.com/download](https://ollama.com/download), Windows installer.
   Installs as a background service, so you generally don't need to start it manually.
   Confirm with:
   ```powershell
   ollama --version
   ```

### macOS

1. **Python 3.12+** — [python.org](https://www.python.org/downloads/macos/) installer,
   or via [Homebrew](https://brew.sh): `brew install python@3.12`. macOS ships its own
   old system Python — don't use that one. Confirm with:
   ```bash
   python3 --version
   ```
2. **Ollama** — [ollama.com/download](https://ollama.com/download), macOS app, or
   `brew install ollama`. Launch it once from Applications (or `ollama serve` if
   installed via Homebrew) so it's running in the background. Confirm with:
   ```bash
   ollama --version
   ```
3. **Xcode Command Line Tools** (usually only needed if a dependency has no prebuilt
   wheel for your exact Python version): `xcode-select --install`.

> Every command below that starts with `python` on Windows is `python3` on macOS —
> macOS doesn't map the plain `python` command to Python 3 by default.

### GPU / performance notes

- **Windows:** the generation model (`qwen3:14b`, ~9GB) needs roughly 10GB+ of free
  VRAM to run fully on GPU. After asking a question, run `ollama ps` — if it shows a
  `CPU/GPU` split instead of `100% GPU`, the model doesn't fit in your VRAM and will be
  slow. Switch `GEN_MODEL` in `backend/config.py` to a smaller model (e.g. `qwen3:8b`)
  and `ollama pull` it first.
- **macOS (Apple Silicon — M1/M2/M3/M4):** Ollama uses Metal acceleration and unified
  memory automatically, no setup needed. The model just needs to fit in your Mac's
  total unified memory — 16GB+ recommended for `qwen3:14b`. Check with `ollama ps` the
  same way.
- **macOS (Intel):** Ollama runs on CPU only (no GPU acceleration path), which will be
  noticeably slow for a 14b model. Prefer a smaller model like `qwen3:8b`.

---

## 2. Pull the models

Identical command on both platforms (Ollama's CLI doesn't differ by OS):

```bash
ollama pull qwen2.5vl:7b
ollama pull nomic-embed-text
ollama pull qwen3:14b
```

| Model | Role | Size |
|---|---|---|
| `qwen2.5vl:7b` | Vision — describes images and OCRs scanned/image-only pages | ~6GB |
| `nomic-embed-text` | Embeddings — turns text into vectors for retrieval | ~300MB |
| `qwen3:14b` | Generation — writes the actual answers | ~9GB |

---

## 3. Install Python dependencies

**Windows** (PowerShell):
```powershell
cd backend
python -m pip install -r requirements.txt
```

**macOS** (Terminal):
```bash
cd backend
python3 -m pip install -r requirements.txt
```

All pinned versions in `requirements.txt` have prebuilt wheels for Windows, Intel
macOS, and Apple Silicon macOS — nothing should need to compile from source. If
something does try to build from source on Windows, don't install Visual Studio Build
Tools to fix it; it means a version in `requirements.txt` got changed from what's
committed — check `git diff` / re-pull the pinned versions instead.

---

## 4. Add your documents

Drop files into `backend/resources/` (or use the admin GUI's upload button, which does
the same thing — see step 7). Supported types: `.pdf`, `.docx`, `.pptx`, `.xlsx`/`.xls`,
`.txt`, `.md`.

Then run ingestion once:

**Windows:**
```powershell
cd backend
python ingest.py
```

**macOS:**
```bash
cd backend
python3 ingest.py
```

This reads every file in `resources/`, extracts text (with automatic vision-model OCR
for scanned/image-only PDF pages and image-only slides), embeds it, and builds the
search index. **Re-run this (or use the admin GUI's "Re-run ingestion" button) any time
you add, remove, or change a file** — it isn't automatic.

Ingestion time depends on document count and whether OCR is needed — expect roughly a
few seconds per page/slide with a text layer, and 15–30s per page that needs OCR.

---

## 5. Run everything

Three things need to be running at once, each in its own terminal window/tab.

**Ollama** — usually already running in the background after install. If not:
```bash
ollama serve
```

**Backend** (from the `backend/` folder):

Windows:
```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
macOS:
```bash
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

**Frontend** (from the `frontend/` folder):

Windows:
```powershell
python -m http.server 3000 --bind 127.0.0.1
```
macOS:
```bash
python3 -m http.server 3000 --bind 127.0.0.1
```

Then open:
- **Chat UI:** http://localhost:3000
- **Admin panel:** http://localhost:8000/admin — login `yongjun` / `12345678`

Both backend and frontend are bound to `127.0.0.1` only (not reachable from other
machines on your network), on both platforms.

---

## 6. Using the admin panel

- **Upload resource file** — uploads a file into `resources/` and automatically
  re-runs ingestion.
- **Re-run ingestion** — rebuilds the search index from whatever's currently in
  `resources/`. Use this after manually adding/removing files without the upload button.
- Dashboard shows live chunk/file counts and which models are configured.

Change the login credentials in `backend/config.py` (`ADMIN_USERNAME`,
`ADMIN_PASSWORD`) before sharing this with anyone else — they're plaintext defaults
meant only for local personal use.

---

## Shutting down

Stop each process with `Ctrl+C` in its terminal, in any order. There's no persistent
background state to clean up beyond that.

**If a port is stuck in use** (e.g. you closed the terminal without Ctrl+C first):

Windows (PowerShell):
```powershell
netstat -ano | findstr :8000
taskkill /PID <the_pid_shown> /F
```

macOS (Terminal):
```bash
lsof -i :8000
kill -9 <the_pid_shown>
```
(swap `:8000` for `:3000` to free the frontend port instead)

Ollama can keep running — it unloads idle models from memory on its own after a few
minutes. Quit it from the system tray (Windows) / menu bar (macOS) if you want to stop
it fully.

---

## Troubleshooting

- **`python: command not found` (macOS)** — use `python3` instead; see the note at the
  end of the Prerequisites section.
- **A question takes a very long time the first time, then is fast after** — normal.
  Ollama unloads a model from memory after ~5 minutes idle; the next request has to
  reload it before it can respond.
- **A question is consistently slow (minutes, not seconds)** — run `ollama ps` while a
  question is in flight and check GPU usage (see the GPU/performance notes above for
  your platform).
- **CSS/logo looks broken or stale after an update** — hard refresh
  (`Ctrl+Shift+R` on Windows, `Cmd+Shift+R` on macOS), or just reload normally;
  stylesheet links are cache-busted with a `?v=` query string so a normal reload should
  already pick up changes.
- **Admin dashboard numbers look wrong right after a manual `ingest.py` run while the
  backend was already running** — shouldn't happen (fixed), but if it does, restart the
  backend.
- **"No resource files found"** — nothing's been placed in `backend/resources/` yet, or
  ingestion hasn't been run since adding files.
