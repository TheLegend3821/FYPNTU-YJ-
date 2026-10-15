from pathlib import Path

OLLAMA_HOST = "http://localhost:11434"

VISION_MODEL = "qwen2.5vl:7b"
EMBED_MODEL = "nomic-embed-text"
GEN_MODEL = "qwen3:14b"

BASE_DIR = Path(__file__).parent
RESOURCES_DIR = BASE_DIR / "resources"
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "resource_pool"

RESOURCES_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
TOP_K = 4

FRONTEND_ORIGIN = "http://localhost:3000"

ADMIN_USERNAME = "yongjun"
ADMIN_PASSWORD = "12345678"
SESSION_SECRET = "dev-only-secret-change-me"
