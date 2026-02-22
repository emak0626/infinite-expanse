import asyncio
import random
from datetime import datetime, timedelta
from database import AsyncSessionLocal
from repository import StockRepository
from kabu_api import KabuApiClient

# Initialize Mock Client
api = KabuApiClient(mock_mode=True)

async def seed_data():
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # Seed Watchlist
        watchlist = ["7203", "9984", "6758", "8035", "5401"]
        
        print("Seeding data...")
        for symbol in watchlist:
            # Create Master
            await repo.get_or_create_stock(symbol, f"Mock Corp {symbol}")
            
            # Generate 30 days of history
            base_price = 1000.0
            for i in range(30):
                # Fake data generation
                change = random.uniform(-0.05, 0.05)
                close = base_price * (1 + change)
                
                price_data = {
                    "open": base_price,
                    "high": max(base_price, close) * 1.01,
                    "low": min(base_price, close) * 0.99,
                    "close": close,
                    "volume": int(random.uniform(10000, 50000)),
                    "rsi_14": random.uniform(20, 80)
                }
                
                # Mock time travel
                past_time = datetime.now() - timedelta(days=30-i)
                
                # Manually create object to override 'time' in repo
                from models_db import StockPrice
                p = StockPrice(symbol=symbol, time=past_time, **price_data)
                session.add(p)
                
                base_price = close
            
        await session.commit()
        print("Seeding Request Completed.")

if __name__ == "__main__":
    asyncio.run(seed_data())
