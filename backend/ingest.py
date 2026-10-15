"""CLI entry point for ingestion.

Run once at setup, and re-run whenever the resource pool changes:
    python ingest.py

(The admin GUI at http://localhost:8000/admin can also trigger this.)
"""
import asyncio

from ingestion import run_ingestion


async def main():
    result = await run_ingestion()
    print(result["message"])


if __name__ == "__main__":
    asyncio.run(main())
