import asyncio
import os
from database import AsyncSessionLocal, engine, Base
from repository import StockRepository
from models_db import StockNote

async def verify_fixes():
    print("--- Verification Start ---")
    
    # 1. Ensure tables are created (just in case)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables ensured.")

    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        symbol = "7203" # Toyota
        test_note = "Test note from verification script"
        
        print(f"Adding test note for {symbol}...")
        try:
            await repo.add_stock_note(symbol, test_note, priority="high")
            print("Successfully called add_stock_note.")
            
            # Verify persistence
            from sqlalchemy import select
            stmt = select(StockNote).where(StockNote.symbol == symbol)
            result = await session.execute(stmt)
            notes = result.scalars().all()
            
            if any(n.note == test_note for n in notes):
                print(f"VERIFICATION SUCCESS: Note persisted for {symbol}.")
            else:
                print("VERIFICATION FAILURE: Note not found in DB.")
                
        except Exception as e:
            print(f"VERIFICATION ERROR: {e}")

    print("--- Verification End ---")

if __name__ == "__main__":
    asyncio.run(verify_fixes())
