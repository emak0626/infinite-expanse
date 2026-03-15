import asyncio
from database import Base, engine
from models_db import StockMaster, StockPrice, AnalysisReport, UserWatchlist, MarketOverview, DocumentChunk

async def init_db():
    print("Initializing database tables...")
    async with engine.begin() as conn:
        # This will create all tables that don't exist yet
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
