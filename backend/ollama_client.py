import base64
import httpx

from config import OLLAMA_HOST, VISION_MODEL, EMBED_MODEL, GEN_MODEL

_TIMEOUT = httpx.Timeout(300.0)

# Shared, connection-pooled client — reused across all calls instead of opening a new
# connection per request, which matters when embedding many chunks during ingestion.
_client = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=_TIMEOUT)


async def close():
    await _client.aclose()


async def embed(text: str) -> list[float]:
    resp = await _client.post("/api/embeddings", json={"model": EMBED_MODEL, "prompt": text})
    resp.raise_for_status()
    return resp.json()["embedding"]


async def describe_image(image_bytes: bytes, prompt: str = "Describe this image in detail.") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    resp = await _client.post(
        "/api/generate",
        json={
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [encoded],
            "stream": False,
        },
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


async def generate(prompt: str) -> str:
    resp = await _client.post(
        "/api/generate",
        json={
            "model": GEN_MODEL,
            "prompt": prompt,
            "stream": False,
        },
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()
