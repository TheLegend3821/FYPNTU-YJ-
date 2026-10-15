"""Core ingestion logic, shared by the CLI script (ingest.py) and the admin GUI."""
import asyncio
import hashlib
from pathlib import Path

from config import RESOURCES_DIR, CHUNK_SIZE, CHUNK_OVERLAP
from ollama_client import embed
import converters
import vectorstore

SUPPORTED_EXTENSIONS = converters.ALL_EXTENSIONS

# How many embedding requests to run concurrently against Ollama during ingestion.
# Extraction (PDF/PPTX page OCR via the vision model) stays sequential — that model
# only serves one generation at a time anyway — but embeddings parallelize well.
EMBED_CONCURRENCY = 8


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def list_resource_files() -> list[dict]:
    files = []
    for path in sorted(RESOURCES_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append({
                "name": str(path.relative_to(RESOURCES_DIR)),
                "size_bytes": path.stat().st_size,
            })
    return files


async def extract_chunks(path: Path) -> list[dict]:
    """Return [{text, extra}] for one resource file, dispatched by extension."""
    suffix = path.suffix.lower()
    data = path.read_bytes()

    if suffix in converters.TEXT_EXTENSIONS:
        text = data.decode("utf-8", errors="ignore")
        return [{"text": c, "extra": {}} for c in chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)]
    if suffix in converters.PDF_EXTENSIONS:
        return await converters.extract_pdf(data)
    if suffix in converters.DOCX_EXTENSIONS:
        text = converters.extract_docx(data)
        return [{"text": c, "extra": {}} for c in chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)]
    if suffix in converters.XLSX_EXTENSIONS:
        return converters.extract_xlsx(data)
    if suffix in converters.PPTX_EXTENSIONS:
        return await converters.extract_pptx(data)
    if suffix in converters.IMAGE_EXTENSIONS:
        description = await converters.extract_image(data)
        return [{"text": description, "extra": {}}] if description.strip() else []
    return []


async def run_ingestion() -> dict:
    files = list_resource_files()
    if not files:
        return {"files_ingested": 0, "chunks_ingested": 0, "message": f"No resource files found in {RESOURCES_DIR}."}

    # Extract first (sequential — PDF/PPTX pages may need vision-model OCR, and that
    # model only serves one request at a time regardless).
    pending = []  # (relpath, chunk_index, text, extra)
    for f in files:
        relpath = f["name"]
        chunks = await extract_chunks(RESOURCES_DIR / relpath)
        for i, chunk in enumerate(chunks):
            text = chunk["text"].strip()
            if text:
                pending.append((relpath, i, text, chunk.get("extra", {})))

    vectorstore.reset()

    if not pending:
        return {
            "files_ingested": len(files),
            "chunks_ingested": 0,
            "message": "No extractable text found in any file.",
        }

    # Embeddings are independent of each other, so run them concurrently — this is the
    # main ingestion speedup, especially for resource pools with many chunks.
    semaphore = asyncio.Semaphore(EMBED_CONCURRENCY)

    async def embed_bounded(text: str) -> list[float]:
        async with semaphore:
            return await embed(text)

    embeddings = await asyncio.gather(*(embed_bounded(text) for _, _, text, _ in pending))

    ids = [hashlib.sha256(f"{relpath}:{i}".encode()).hexdigest() for relpath, i, _, _ in pending]
    documents = [text for _, _, text, _ in pending]
    metadatas = [{"source": relpath, "chunk_index": i, **extra} for relpath, i, _, extra in pending]

    # A single batched add instead of one call per chunk.
    vectorstore.add_chunks(ids=ids, embeddings=list(embeddings), documents=documents, metadatas=metadatas)

    return {
        "files_ingested": len(files),
        "chunks_ingested": len(pending),
        "message": f"Ingested {len(pending)} chunks from {len(files)} files.",
    }
