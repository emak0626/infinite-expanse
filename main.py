from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List

from kabu_api import KabuApiClient
from models import StockData, AnalysisRequest
import prompts
from screener import Screener
from database import AsyncSessionLocal
from repository import StockRepository
import os

screener = Screener()

from scheduler import start_scheduler

app = FastAPI(title="Infinite Expanse - Stock Trader")

@app.on_event("startup")
async def startup_event():
    start_scheduler()

from config import settings
from kabu_api import KabuApiClient as MockClient
from kabu_com_client import KabucomClient

# Initialize API Client
if settings.MOCK_MODE:
    print("WARNING: Running in MOCK MODE")
    api_client = MockClient(mock_mode=True)
else:
    print(f"Connecting to Kabu Station at {settings.KABU_API_HOST}:{settings.KABU_API_PORT}")
    api_client = KabucomClient()

# Watchlist (Expanded for Screening Test)
WATCHLIST = [
    "7203", "9984", "6758", "8035", "5401", 
    "9101", "8306", "8316", "7267", "6501",
    "6702", "7751", "4502", "4503", "6954",
    "6098", "6367", "6861", "7974", "9432"
]

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/stocks", response_model=List[StockData])
async def get_stocks():
    """Fetches latest data for all watched stocks including AI scores."""
    results = []
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        for symbol in WATCHLIST:
            data = api_client.get_board(symbol)
            # Fetch latest AI analysis for score
            report = await repo.get_latest_analysis(symbol)
            if report:
                data.ai_score = report.score
            results.append(data)
    return results

@app.get("/api/screening")
async def get_screening_results():
    """Returns stocks filtered by strategies with AI data."""
    full_list = []
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        for symbol in WATCHLIST:
            data = api_client.get_board(symbol)
            report = await repo.get_latest_analysis(symbol)
            if report:
                data.ai_score = report.score
            full_list.append(data)
    
    # 2. Apply Screening
    results = screener.filter_stocks(full_list)
    return results

@app.get("/api/config/strategies")
async def get_strategies():
    """Returns current strategy configurations."""
    return screener.get_strategy_config()

@app.get("/api/prompt/{symbol}")
async def get_prompt(symbol: str):
    """Returns the analysis prompt for clipboard copy."""
    data = api_client.get_board(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    prompt_text = prompts.generate_analysis_prompt(data)
    return {"symbol": symbol, "prompt": prompt_text}

import report_manager

# ... (Previous code)

@app.post("/api/analyze/{symbol}")
async def analyze_stock(symbol: str):
    """
    Triggers analysis and saves the context report.
    This allows the user to use Gemini CLI with the generated file.
    """
    data = api_client.get_board(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    # Save Report
    filepath = report_manager.save_report(data, context_type="manual_trigger")
    
    return {
        "message": f"Analysis context saved.",
        "filepath": filepath,
        "symbol": symbol
    }

@app.get("/api/report/{symbol}")
async def get_report_status(symbol: str):
    """Checks if a report exists for today and returns its relative path/URL."""
    import datetime
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    filename = f"{symbol}_report.md"
    rel_path = f"trade_reports/{date_str}/{filename}"
    abs_path = os.path.join(os.getcwd(), rel_path)
    
    if os.path.exists(abs_path):
        return {"exists": True, "url": f"/{rel_path}"}
    return {"exists": False}

@app.get("/api/analysis/{symbol}")
async def get_latest_analysis_detail(symbol: str):
    """Returns the latest structured AI analysis from DB."""
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        report = await repo.get_latest_analysis(symbol)
        if not report:
            raise HTTPException(status_code=404, detail="No analysis found")
        
        import json
        try:
            content = json.loads(report.report_content)
        except:
            content = {"text": report.report_content}
            
        return {
            "symbol": symbol,
            "created_at": report.created_at,
            "score": report.score,
            "thinking_level": report.thinking_level,
            "content": content
        }

@app.get("/api/history/{symbol}")
async def get_history(symbol: str, limit: int = 60):
    """Returns historical price data for charting."""
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        prices = await repo.get_latest_prices(symbol, limit=limit)
        # Reverse to return chronological order
        return [
            {
                "time": p.time,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume
            }
            for p in reversed(prices)
        ]

# Mount trade reports as static files to allow direct viewing
if not os.path.exists("trade_reports"):
    os.makedirs("trade_reports")
app.mount("/trade_reports", StaticFiles(directory="trade_reports"), name="trade_reports")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
