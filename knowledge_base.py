import logging
import json
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.future import select
from models_db import DocumentChunk
from database import AsyncSessionLocal
import aiohttp
from config import settings

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """
    Manages long-term semantic memory using pgvector and Gemini/Ollama embeddings.
    """
    EMBEDDING_MODEL = "models/text-embedding-004"

    def __init__(self, api_key: str = settings.GEMINI_API_KEY):
        self.api_key = api_key

    async def get_embedding(self, text_content: str) -> List[float]:
        """
        Fetches embedding from Gemini API.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={self.api_key}"
        payload = {
            "model": self.EMBEDDING_MODEL,
            "content": {"parts": [{"text": text_content}]}
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("embedding", {}).get("values", [])
                    else:
                        logger.error(f"Embedding API failed: {resp.status}")
                        return []
            except Exception as e:
                logger.error(f"Embedding error: {e}")
                return []

    async def add_knowledge(self, symbol: str, text_content: str, source: str):
        """
        Chunks text and stores it in pgvector.
        """
        # Simple chunking (for now)
        chunks = [text_content[i:i+1000] for i in range(0, len(text_content), 800)]
        
        async with AsyncSessionLocal() as session:
            for chunk in chunks:
                vec = await self.get_embedding(chunk)
                if vec:
                    new_chunk = DocumentChunk(
                        symbol=symbol,
                        content=chunk,
                        embedding=vec,
                        metadata_json=json.dumps({"source": source})
                    )
                    session.add(new_chunk)
            await session.commit()

    async def search_relevant_context(self, symbol: str, query: str, limit: int = 5) -> str:
        """
        Performs semantic search to find relevant context for a specific stock.
        """
        query_vec = await self.get_embedding(query)
        if not query_vec:
            return ""

        async with AsyncSessionLocal() as session:
            # Use pgvector's cosine distance operator <=> 
            # This query finds the closest chunks for the given stock
            stmt = select(DocumentChunk).where(DocumentChunk.symbol == symbol).order_by(
                DocumentChunk.embedding.cosine_distance(query_vec)
            ).limit(limit)
            
            result = await session.execute(stmt)
            chunks = result.scalars().all()
            
            context = "\n---\n".join([c.content for c in chunks])
            return context

async def test():
    kb = KnowledgeBase()
    # Mock some knowledge
    print("Adding knowledge...")
    await kb.add_knowledge("7203", "トヨタ自動車は2024年に次世代BEVの生産能力を倍増させる計画を発表しました。", "Annual Report Excerpt")
    
    print("Searching...")
    context = await kb.search_relevant_context("7203", "電気自動車の戦略について教えて")
    print(f"Retrieved Context:\n{context}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test())
