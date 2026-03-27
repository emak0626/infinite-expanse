import sys
import asyncio
sys.path.append('/app')
from database import AsyncSessionLocal
from repository import StockRepository
from workspace_manager import workspace_mgr
from bulk_screener import BulkScreener
import pandas as pd
import json
import traceback

async def main():
    try:
        screener = BulkScreener()
        print("Running Technical Scan for Growth...")
        res = await screener.run_technical_scan(strategy="growth")
        print("Scan result:", res)
        
        async with AsyncSessionLocal() as session:
            repo = StockRepository(session)
            csv_path = workspace_mgr.get_path("market", "Market_Scan_Results.csv")
            print(f"Reading generated CSV: {csv_path}")
            df = pd.read_csv(csv_path)
            print(f"Loaded CSV with {len(df)} rows")
            
            results = []
            for _, row in df.iterrows():
                try:
                    symbol = str(row["銘柄コード"])
                    report = await repo.get_latest_analysis(symbol)
                    
                    stock_dict = {
                        "symbol": symbol,
                        "symbolname": row.get("銘柄名", "Unknown"),
                        "currentprice": float(row.get("終値", 0)),
                        "change_percent": float(row.get("騰落率", 0)),
                        "volume": int(row.get("出来高", 0)),
                        "rsi": float(row.get("RSI", 0)),
                        "per": float(row.get("PER", 0)) if pd.notnull(row.get("PER")) else None,
                        "pbr": float(row.get("PBR", 0)) if pd.notnull(row.get("PBR")) else None,
                        "dividend_yield": float(row.get("利回り", 0)) if pd.notnull(row.get("利回り")) else None,
                        "ai_score": report.score if report else float(row.get("AIスコア", 0)),
                        "ai_summary": report.summary if report else row.get("AI要約", ""),
                        "is_watched": False 
                    }
                    results.append(stock_dict)
                except Exception as e:
                    print(f"Row {symbol} error: {e}")
                    traceback.print_exc()
            
            print(json.dumps(results[:2], indent=2, ensure_ascii=False))
            print(f"Successfully processed {len(results)} rows for JSON.")

    except Exception as e:
        print("GLOBAL ERROR:", e)
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
