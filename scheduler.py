from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
from config import settings
from database import AsyncSessionLocal
from repository import StockRepository
from kabu_com_client import KabucomClient
from kabu_api import KabuApiClient as MockClient

from analyzer_agent import GeminiAgent

# Initialize Clients
real_client = KabucomClient()
mock_client = MockClient(mock_mode=True)
agent = GeminiAgent()

scheduler = AsyncIOScheduler()

async def fetch_stock_data_job():
    """
    Periodic job to fetch stock data and save to DB.
    """
    # ... (Existing code) ...
    print(f"[{datetime.now()}] Starting Data Fetch Job...")
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        for symbol in settings.WATCHLIST:
            try:
                # 1. Fetch Data
                if settings.MOCK_MODE:
                    data = mock_client.get_board(symbol)
                    p_close = data.currentprice
                else:
                    # Real API: Get Board
                    board = real_client.get_board(symbol)
                    if not board:
                        continue
                        
                    # Map API Response to our Model
                    p_close = float(board.get("CurrentPrice", 0))
                    data = {
                        "open": float(board.get("OpeningPrice", 0)),
                        "high": float(board.get("HighPrice", 0)),
                        "low": float(board.get("LowPrice", 0)),
                        "close": p_close,
                        "volume": int(board.get("TradingVolume", 0)),
                        "rsi_14": 50.0 # Placeholder
                    }
                
                # 2. Save to DB
                if settings.MOCK_MODE:
                    await repo.add_price(symbol, {
                        "open": data.currentprice,
                        "high": data.high,
                        "low": data.low,
                        "close": data.currentprice,
                        "volume": data.volume,
                        "rsi_14": data.rsi
                    })
                else:
                    await repo.add_price(symbol, data)
                    
                print(f"Saved {symbol}: {p_close}")
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")

async def run_daily_analysis():
    """
    Daily job to analyze stocks using Gemini.
    """
    print(f"[{datetime.now()}] Starting Daily AI Analysis...")
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        for symbol in settings.WATCHLIST:
            try:
                # 1. Get Stock & History
                stock = await repo.get_or_create_stock(symbol)
                history = await repo.get_latest_prices(symbol, limit=30)
                
                if not history:
                    print(f"No history for {symbol}, skipping analysis.")
                    continue
                
                # 2. Format Context for LLM
                # reverse history to be chronological (oldest -> newest) for the LLM
                history_str = "\n".join([
                    f"{p.time.strftime('%Y-%m-%d')}: Close={p.close}, Vol={p.volume}, RSI={p.rsi_14}"
                    for p in reversed(history)
                ])
                
                # 3. Analyze with Gemini
                print(f"Analyzing {symbol}...")
                analysis = await agent.analyze(
                    stock=stock, 
                    context_data=history_str, 
                    thinking_level="standard"
                )
                
                # 4. Save Report
                if "error" not in analysis:
                    await repo.save_analysis(
                        symbol=symbol,
                        content=json.dumps(analysis, indent=2, ensure_ascii=False),
                        score=float(analysis.get("score", 0)),
                        thinking_level="standard"
                    )
                    print(f"Analysis saved for {symbol} (Score: {analysis.get('score')})")
                else:
                    print(f"Analysis failed for {symbol}: {analysis['error']}")
                
                # Rate Limiting (Free Tier: ~15 RPM)
                await asyncio.sleep(4) 
                
            except Exception as e:
                print(f"Error analyzing {symbol}: {e}")

def start_scheduler():
    # Fetch Data: Every minute (Testing)
    trigger_fetch = CronTrigger(second="0") 
    scheduler.add_job(fetch_stock_data_job, trigger_fetch)
    
    # Analyze: Every day at 16:00 (After market close)
    # For testing, we can run it once on startup or set a near time
    # trigger_analyze = CronTrigger(hour=16, minute=0)
    # scheduler.add_job(run_daily_analysis, trigger_analyze)
    
    scheduler.start()
    print("Scheduler Started.")
    
    # Run analysis once immediately for validation if needed (Optional)
    # asyncio.create_task(run_daily_analysis()) 
