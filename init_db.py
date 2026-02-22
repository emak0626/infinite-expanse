import asyncio
from sqlalchemy import text
from database import engine, Base
from models_db import StockMaster, StockPrice, AnalysisReport
from config import settings

async def init_db():
    async with engine.begin() as conn:
        # Create Tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Convert to Hypertable (TimescaleDB specific)
        try:
            await conn.execute(text("SELECT create_hypertable('stock_prices', 'time', if_not_exists => TRUE);"))
            print("Converted stock_prices to hypertable.")
        except Exception as e:
            print(f"Hypertable creation failed (Make sure TimescaleDB extension is active): {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
