import asyncio
import json
from datetime import datetime
from database import AsyncSessionLocal
from repository import StockRepository
from workspace_manager import workspace_mgr

async def test_manual_save():
    symbol = "6702"
    content_text = "これはテスト分析レポートです。Dドライブへの保存を確認します。"
    score = 8.5
    
    print(f"--- Testing Manual Save for {symbol} ---")
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        structured_content = json.dumps({"text": content_text}, ensure_ascii=False)
        
        # 1. Save to DB
        await repo.save_analysis(
            symbol=symbol,
            content=structured_content,
            score=score,
            thinking_level="test"
        )
        print("1. Saved to Database.")
        
        # 2. Save to Local Hub (D: drive)
        report_title = f"Test_Analysis_{symbol}_{datetime.now().strftime('%H%M')}"
        path = workspace_mgr.save_report(report_title, f"# Test Analysis Report: {symbol}\n\n{content_text}")
        print(f"2. Saved to Workspace: {path}")
        
    print("--- Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_manual_save())
