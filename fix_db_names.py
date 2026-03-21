import asyncio
import json
import os
from database import AsyncSessionLocal
from repository import StockRepository
from kabu_api import KabuApiClient

async def fix_unknown_names():
    print("Starting DB cleanup for Unknown names...")
    api_client = KabuApiClient(mock_mode=True)
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        stocks = await repo.get_all_stocks()
        
        updated_count = 0
        for stock in stocks:
            if not stock.name or "Unknown" in stock.name or "Mock" in stock.name or stock.name.startswith("銘柄"):
                if stock.symbol in api_client.stock_name_map:
                    old_name = stock.name
                    new_name = api_client.stock_name_map[stock.symbol]
                    stock.name = new_name
                    print(f"Updating {stock.symbol}: {old_name} -> {new_name}")
                    updated_count += 1
        
        if updated_count > 0:
            await session.commit()
            print(f"Successfully updated {updated_count} stocks.")
        else:
            print("No stocks needed updating.")

if __name__ == "__main__":
    asyncio.run(fix_unknown_names())
