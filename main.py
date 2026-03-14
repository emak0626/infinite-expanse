from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
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
from drive_manager import DriveManager
from sheets_manager import SheetsManager

app = FastAPI(title="Infinite Expanse - Stock Trader")
drive_mgr = DriveManager()
sheets_mgr = SheetsManager()
security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    is_user_ok = secrets.compare_digest(credentials.username, settings.WEB_USERNAME)
    is_pass_ok = secrets.compare_digest(credentials.password, settings.WEB_PASSWORD)
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.on_event("startup")
async def startup_event():
    start_scheduler()

from config import settings
from kabu_api import KabuApiClient as MockClient
from kabu_com_client import KabucomClient

# Initialize API Client
if settings.MOCK_MODE:
    print("WARNING: Running in MOCK MODE")
    api_client = KabuApiClient(mock_mode=True)
else:
    print(f"Connecting to Kabu Station at {settings.KABU_API_HOST}:{settings.KABU_API_PORT}")
    api_client = KabuApiClient(mock_mode=False)

# Consolidate Watchlist to Config Settings
WATCHLIST = settings.WATCHLIST

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root(username: str = Depends(authenticate)):
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/stocks", response_model=List[StockData])
async def get_stocks(username: str = Depends(authenticate)):
    """Fetches latest data for all watched stocks including AI scores."""
    results = []
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        # Fetch watchlist from DB
        db_watchlist = await repo.get_watchlist_symbols()
        
        # Initial seeding from config if DB is empty
        if not db_watchlist:
            for symbol in WATCHLIST:
                await repo.add_to_watchlist(symbol)
            db_watchlist = WATCHLIST
            
        for symbol in db_watchlist:
            data = api_client.get_board(symbol)
            # Fetch latest AI analysis
            report = await repo.get_latest_analysis(symbol)
            if report:
                data.ai_score = report.score
                data.ai_sentiment = report.sentiment
                data.ai_summary = report.summary
                data.ai_thinking = report.thinking_level
            results.append(data)
    return results

@app.post("/api/watchlist/{symbol}")
async def add_to_watchlist(symbol: str, username: str = Depends(authenticate)):
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        await repo.add_to_watchlist(symbol)
    return {"status": "added", "symbol": symbol}

@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str, username: str = Depends(authenticate)):
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        await repo.remove_from_watchlist(symbol)
    return {"status": "removed", "symbol": symbol}

@app.get("/api/screening")
async def get_screening_results(username: str = Depends(authenticate)):
    """Returns stocks filtered by strategies with AI data."""
    full_list = []
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        # Fetch watchlist from DB
        db_watchlist = await repo.get_watchlist_symbols()
        if not db_watchlist: db_watchlist = settings.WATCHLIST
        
        for symbol in db_watchlist:
            data = api_client.get_board(symbol)
            report = await repo.get_latest_analysis(symbol)
            if report:
                data.ai_score = report.score
                data.ai_sentiment = report.sentiment
                data.ai_summary = report.summary
                data.ai_thinking = report.thinking_level
            full_list.append(data)
    
    # 2. Apply Screening
    results = screener.filter_stocks(full_list)
    return results

@app.get("/api/config/strategies")
async def get_strategies(username: str = Depends(authenticate)):
    """Returns current strategy configurations."""
    return screener.get_strategy_config()

@app.get("/api/market_scanner")
async def get_market_scanner(type: str = "1", username: str = Depends(authenticate)):
    """
    Returns ranking data from the market.
    Types: 1: Gainers, 2: Losers, 3: Volume, 4: Volume Spike
    """
    stocks = api_client.get_ranking(type)
    if not stocks:
        return []
        
    # Apply screening to ranking results to show matches
    results = screener.filter_stocks(stocks)
    
    # Add AI summaries if available
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        for stock_dict in results:
            symbol = stock_dict["symbol"]
            report = await repo.get_latest_analysis(symbol)
            if report:
                import json
                try:
                    content = json.loads(report.report_content)
                    stock_dict["ai_summary"] = content.get("summary", "")
                    stock_dict["ai_score"] = report.score
                except:
                    stock_dict["ai_summary"] = report.report_content[:150]
    
    return results

@app.get("/api/bulk_prompt")
async def get_bulk_prompt(source: str = "watchlist", type: str = "1", username: str = Depends(authenticate)):
    """
    Returns a bulk analysis prompt.
    source: 'watchlist' or 'scanner'
    """
    full_list = []
    if source == "watchlist":
        async with AsyncSessionLocal() as session:
            repo = StockRepository(session)
            db_watchlist = await repo.get_watchlist_symbols()
            if not db_watchlist: db_watchlist = WATCHLIST
            
            for symbol in db_watchlist:
                data = api_client.get_board(symbol)
                if data: full_list.append(data)
    else:
        full_list = api_client.get_ranking(type)
    
    if not full_list:
        raise HTTPException(status_code=404, detail="No stock data available")
        
    prompt_text = prompts.generate_bulk_analysis_prompt(full_list)
    return {"prompt": prompt_text, "count": len(full_list)}

@app.get("/api/prompt/{symbol}")
async def get_single_prompt(symbol: str, username: str = Depends(authenticate)):
    """Returns a detail analysis prompt for a single stock."""
    data = api_client.get_board(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Stock data not found")
        
    prompt_text = prompts.generate_analysis_prompt(data)
    return {"prompt": prompt_text}

import report_manager

# ... (Previous code)

from analyzer_agent import GeminiAgent
import json
ai_agent = GeminiAgent()

@app.post("/api/analyze/{symbol}")
async def analyze_stock(symbol: str, username: str = Depends(authenticate)):
    """
    Triggers AI analysis via Gemini and saves the structured result to the DB.
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # 1. Get Stock & Data
        stock = await repo.get_or_create_stock(symbol)
        history = await repo.get_latest_prices(symbol, limit=30)
        
        if not history:
            # Fallback to current board data if no history
            data = api_client.get_board(symbol)
            history_str = f"Current Board Data: Price={data.currentprice}, Vol={data.volume}, RSI={data.rsi}"
        else:
            history_str = "\n".join([
                f"{p.time.strftime('%Y-%m-%d')}: Close={p.close}, Vol={p.volume}, RSI={p.rsi_14}"
                for p in reversed(history)
            ])
            
        # 2. Run Gemini Analysis
        analysis = await ai_agent.analyze(
            stock=stock, 
            context_data=history_str, 
            thinking_level="standard"
        )
        
        # 3. Save to DB
        if "error" not in analysis:
            await repo.save_analysis(
                symbol=symbol,
                content=json.dumps(analysis, indent=2, ensure_ascii=False),
                score=float(analysis.get("score", 0)),
                thinking_level="standard",
                summary=analysis.get("summary"),
                sentiment=analysis.get("sentiment")
            )
            return {"status": "success", "score": analysis.get("score"), "summary": analysis.get("summary")}
        else:
            # Check for Quota/Rate limit issues
            err_msg = analysis['error']
            status_code = 500
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                status_code = 429
                err_msg = "Gemini APIの無料枠制限（クォータ）を超えました。しばらく待つか、別のAPIキーを検討してください。"
            
            raise HTTPException(status_code=status_code, detail=err_msg)

@app.get("/api/report/{symbol}")
async def get_report_status(symbol: str, username: str = Depends(authenticate)):
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
async def get_latest_analysis_detail(symbol: str, username: str = Depends(authenticate)):
    """Returns the latest structured AI analysis from DB."""
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        report = await repo.get_latest_analysis(symbol)
        if not report:
            return {"error": "Analysis not found"}
        
        try:
            content = json.loads(report.report_content)
        except:
            content = {"text": report.report_content}
            
        return {
            "symbol": symbol,
            "score": report.score,
            "sentiment": report.sentiment,
            "summary": report.summary,
            "content": content,
            "created_at": report.created_at
        }

@app.get("/api/analysis_detail/{report_id}")
async def get_analysis_by_id(report_id: int, username: str = Depends(authenticate)):
    """Returns a specific AI analysis by ID."""
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        report = await repo.get_analysis_by_id(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return format_report(report)

def format_report(report):
    import json
    try:
        content = json.loads(report.report_content)
    except:
        content = {"text": report.report_content}
        
    return {
        "id": report.id,
        "symbol": report.symbol,
        "created_at": report.created_at,
        "score": report.score,
        "thinking_level": report.thinking_level,
        "content": content
    }

@app.get("/api/analysis_history/{symbol}")
async def get_analysis_history(symbol: str, username: str = Depends(authenticate)):
    """Returns a list of all analysis reports for a stock."""
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        reports = await repo.get_analysis_history(symbol)
        return [
            {
                "id": r.id,
                "score": r.score,
                "sentiment": r.sentiment,
                "summary": r.summary,
                "created_at": r.created_at
            }
            for r in reports
        ]

@app.post("/api/save_manual_report/{symbol}")
async def save_manual_report(symbol: str, report: dict, username: str = Depends(authenticate)):
    """
    Saves a manually pasted report from Gemini Web to the DB.
    Expected JSON: {"content": "...", "score": 7.5}
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        content_text = report.get("content", "")
        score = float(report.get("score", 0))
        
        # Wrap plain text in a JSON structure if it's not already
        structured_content = json.dumps({"text": content_text}, ensure_ascii=False)
        
        await repo.save_analysis(
            symbol=symbol,
            content=structured_content,
            score=score,
            thinking_level="manual_paste"
        )
        return {"status": "success"}

@app.get("/api/history/{symbol}")
async def get_history(symbol: str, limit: int = 60, username: str = Depends(authenticate)):
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

@app.get("/api/workspace/links")
async def get_workspace_links(username: str = Depends(authenticate)):
    """Returns links to the Google Drive folder and Master Watchlist sheet."""
    try:
        root_link = drive_mgr.get_web_link(drive_mgr.root_folder_name)
        sheet_link = drive_mgr.get_web_link("Master_Watchlist")
        reports_link = drive_mgr.get_web_link("02_AI_Daily_Reports")
    except Exception as e:
        print(f"Error fetching workspace links (possibly API disabled): {e}")
        return {"root": None, "sheet": None, "reports": None, "error": str(e)}
    
    return {
        "root": root_link,
        "sheet": sheet_link,
        "reports": reports_link
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
