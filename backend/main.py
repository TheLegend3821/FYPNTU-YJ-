from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

from config import FRONTEND_ORIGIN, TOP_K, SESSION_SECRET, VISION_MODEL, EMBED_MODEL, GEN_MODEL, RESOURCES_DIR
import ollama_client
import vectorstore
import auth
import converters
from ingestion import run_ingestion, list_resource_files, SUPPORTED_EXTENSIONS

ADMIN_DIR = Path(__file__).parent / "admin_ui"

# Attachment types accepted on a single question (ephemeral, not added to the resource pool)
ASK_FILE_EXTENSIONS = (
    converters.IMAGE_EXTENSIONS | converters.PDF_EXTENSIONS | converters.DOCX_EXTENSIONS
    | converters.XLSX_EXTENSIONS | converters.PPTX_EXTENSIONS
)

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="admin_session")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/admin/static", StaticFiles(directory=ADMIN_DIR), name="admin-static")


@app.on_event("shutdown")
async def shutdown():
    await ollama_client.close()


class AskRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    text: str
    file: Optional[str] = None
    download_url: Optional[str] = None
    page: Optional[int] = None
    slide: Optional[int] = None
    sheet: Optional[str] = None
    row: Optional[int] = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    primary_source: Optional[SourceItem] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ExplainRequest(BaseModel):
    question: str
    chunks: list[SourceItem]


class ExplainResponse(BaseModel):
    explanation: str


def location_label(meta: dict) -> Optional[str]:
    if meta.get("page"):
        return f"page {meta['page']}"
    if meta.get("slide"):
        return f"slide {meta['slide']}"
    if meta.get("sheet"):
        return f"{meta['sheet']}, row {meta.get('row')}"
    return None


def source_tag(source_file: Optional[str], loc: Optional[str]) -> str:
    if not source_file:
        return ""
    return f"[Source: {source_file}" + (f", {loc}" if loc else "") + "]"


def build_prompt(question: str, chunks: list[dict]) -> str:
    if not chunks:
        return f"Answer the question as best you can.\n\nQuestion: {question}"
    blocks = []
    for c in chunks:
        meta = c["metadata"]
        tag = source_tag(meta.get("source"), location_label(meta))
        blocks.append(f"{tag}\n{c['text']}".strip())
    context = "\n\n---\n\n".join(blocks)
    return (
        "Use the following context to answer the question. Each context block is tagged with its "
        "source file. If you use a block, mention which source file it came from, written as plain "
        "text like (Source: filename, page X) — do not use markdown link syntax like [text](url). "
        "If the context doesn't contain the answer, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )


def to_source_items(chunks: list[dict]) -> list[SourceItem]:
    items = []
    for c in chunks:
        meta = c["metadata"]
        source_file = meta.get("source")
        download_url = f"/files/{source_file}" if source_file else None
        items.append(SourceItem(
            text=c["text"],
            file=source_file,
            download_url=download_url,
            page=meta.get("page"),
            slide=meta.get("slide"),
            sheet=meta.get("sheet"),
            row=meta.get("row"),
        ))
    return items


async def extract_attachment_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext in converters.IMAGE_EXTENSIONS:
        return await converters.extract_image(data)
    if ext in converters.PDF_EXTENSIONS:
        pages = await converters.extract_pdf(data)
        return "\n\n".join(p["text"] for p in pages)
    if ext in converters.DOCX_EXTENSIONS:
        return converters.extract_docx(data)
    if ext in converters.XLSX_EXTENSIONS:
        rows = converters.extract_xlsx(data)
        return "\n".join(r["text"] for r in rows)
    if ext in converters.PPTX_EXTENSIONS:
        slides = await converters.extract_pptx(data)
        return "\n\n".join(s["text"] for s in slides)
    raise HTTPException(400, f"Unsupported file type: {ext}")


@app.get("/")
async def root():
    return RedirectResponse("/admin")


# ---- Public API (used by the frontend on :3000) ----

@app.get("/status")
async def status():
    return {"ingested_chunks": vectorstore.count()}


@app.get("/files/{filename:path}")
async def download_file(filename: str):
    target = (RESOURCES_DIR / filename).resolve()
    resources_root = RESOURCES_DIR.resolve()
    if resources_root != target and resources_root not in target.parents:
        raise HTTPException(404)
    if not target.is_file():
        raise HTTPException(404)
    return FileResponse(target, filename=target.name)


async def answer_question(question_text: str) -> AskResponse:
    embedding = await ollama_client.embed(question_text)
    chunks = vectorstore.query(embedding, TOP_K)
    prompt = build_prompt(question_text, chunks)
    answer = await ollama_client.generate(prompt)
    sources = to_source_items(chunks)
    return AskResponse(answer=answer, sources=sources, primary_source=sources[0] if sources else None)


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    return await answer_question(req.question)


@app.post("/ask-file", response_model=AskResponse)
async def ask_file(question: str = Form(...), file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ASK_FILE_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    data = await file.read()
    extracted = await extract_attachment_text(file.filename, data)
    combined = f"Attached file ({file.filename}):\n{extracted}\n\nQuestion: {question}"
    return await answer_question(combined)


@app.post("/explain", response_model=ExplainResponse)
async def explain(req: ExplainRequest):
    if not req.chunks:
        return ExplainResponse(explanation="I don't have any matched source material to explain from.")

    blocks = []
    for s in req.chunks:
        loc = location_label({"page": s.page, "slide": s.slide, "sheet": s.sheet, "row": s.row})
        tag = source_tag(s.file, loc)
        blocks.append(f"{tag}\n{s.text}".strip())
    context = "\n\n---\n\n".join(blocks)

    prompt = (
        "A user asked the question below and was given an answer based on the context shown. "
        "Now explain the working / reasoning behind that answer step by step, as if teaching a student "
        "who wants to understand how to arrive at it themselves. Walk through the logic using the source "
        "material directly, and mention which source file each part of the working comes from, written as "
        "plain text like (Source: filename, page X) — do not use markdown link syntax like [text](url).\n\n"
        f"Context:\n{context}\n\nQuestion: {req.question}"
    )
    explanation = await ollama_client.generate(prompt)
    return ExplainResponse(explanation=explanation)


# ---- Admin GUI (login-protected, served at :8000/admin) ----

@app.get("/admin")
async def admin_root(request: Request):
    if auth.is_logged_in(request):
        return RedirectResponse("/admin/dashboard")
    return RedirectResponse("/admin/login")


@app.get("/admin/login")
async def admin_login_page(request: Request):
    if auth.is_logged_in(request):
        return RedirectResponse("/admin/dashboard")
    return FileResponse(ADMIN_DIR / "login.html")


@app.get("/admin/dashboard")
async def admin_dashboard_page(request: Request):
    if not auth.is_logged_in(request):
        return RedirectResponse("/admin/login")
    return FileResponse(ADMIN_DIR / "dashboard.html")


@app.post("/admin/api/login")
async def admin_login(req: LoginRequest, request: Request):
    if not auth.check_credentials(req.username, req.password):
        return JSONResponse({"ok": False, "error": "Invalid username or password"}, status_code=401)
    auth.login(request)
    return {"ok": True}


@app.post("/admin/api/logout")
async def admin_logout(request: Request):
    auth.logout(request)
    return {"ok": True}


@app.get("/admin/api/session")
async def admin_session(request: Request):
    return {"authenticated": auth.is_logged_in(request)}


@app.get("/admin/api/status", dependencies=[Depends(auth.require_admin)])
async def admin_status():
    return {
        "ingested_chunks": vectorstore.count(),
        "resource_files": list_resource_files(),
        "models": {"vision": VISION_MODEL, "embedding": EMBED_MODEL, "generation": GEN_MODEL},
    }


@app.post("/admin/api/ingest", dependencies=[Depends(auth.require_admin)])
async def admin_ingest():
    result = await run_ingestion()
    return result


@app.post("/admin/api/upload", dependencies=[Depends(auth.require_admin)])
async def admin_upload(file: UploadFile = File(...)):
    safe_name = Path(file.filename).name  # strips any directory components
    ext = Path(safe_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}")

    content = await file.read()
    dest = RESOURCES_DIR / safe_name
    dest.write_bytes(content)

    result = await run_ingestion()
    return {"uploaded": safe_name, **result}
