
import asyncio
import os
import sys
import json
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Mock settings/env
# GEMINI_API_KEY should be set in .env or environment
os.environ["GEMINI_MODEL_ID"] = "gemini-2.0-flash"
os.environ["POSTGRES_USER"] = "user"
os.environ["POSTGRES_PASSWORD"] = "password"
os.environ["POSTGRES_DB"] = "stock_analysis"
os.environ["POSTGRES_HOST"] = "timescaledb" # Inside docker network

sys.path.append(os.getcwd())

from analyzer_agent import GeminiAgent
from repository import StockRepository
from database import Base, engine

async def test_analysis():
    agent = GeminiAgent()
    
    # Mock stock
    from models_db import StockMaster
    stock = StockMaster(symbol="7203", name="Toyota")
    
    context = "2026-03-14: Close=3370, Vol=1000, RSI=50"
    
    print("Testing Gemini Analysis...")
    try:
        analysis = await agent.analyze(stock, context)
        print(f"Analysis Result: {json.dumps(analysis, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Gemini Agent threw an error: {e}")
        return
    
    if "error" in analysis:
        print(f"Analysis returned error: {analysis['error']}")
        return

    print("Testing DB Save...")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        repo = StockRepository(session)
        try:
            await repo.save_analysis(
                symbol="7203",
                content=json.dumps(analysis, indent=2, ensure_ascii=False),
                score=float(analysis.get("score", 0)),
                thinking_level="standard"
            )
            print("DB Save Success!")
        except Exception as e:
            print(f"DB Save Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_analysis())
