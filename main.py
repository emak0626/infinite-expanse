from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from typing import List, Optional
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from kabu_api import KabuApiClient
from models import StockData, AnalysisRequest, ManualReportRequest
import prompts
from screener import Screener
from database import AsyncSessionLocal
from repository import StockRepository
from bulk_screener import BulkScreener
from models_db import AnalysisReport, StockNote
import os
import time
import asyncio
from pydantic import BaseModel
from datetime import datetime, time as dt_time, timedelta, timezone
jst = timezone(timedelta(hours=9))
import json
from functools import wraps
import pandas as pd

def _safe_float(val, default=0.0):
    if val is None or val == "" or str(val).lower() == "nan": return default
    try:
        if isinstance(val, str): val = val.replace(',', '').replace('%', '')
        return float(val)
    except: return default

def _safe_int(val, default=0):
    if val is None or val == "" or str(val).lower() == "nan": return default
    try:
        if isinstance(val, str): val = val.replace(',', '')
        return int(float(val))
    except: return default

def retry_db_async(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_err = None
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    print(f"DB Retry {i+1}/{max_retries} due to: {e}")
                    await asyncio.sleep(delay * (i + 1))
            raise last_err
        return wrapper
    return decorator

# Simple API Cache
_api_cache = {}
CACHE_TTL = 300 # 5 minutes

def get_cached_board(symbol):
    now = time.time()
    if symbol in _api_cache:
        data, timestamp = _api_cache[symbol]
        if now - timestamp < CACHE_TTL:
            return data
    data = api_client.get_board(symbol)
    _api_cache[symbol] = (data, now)
    return data

screener = Screener()
market_screener = BulkScreener()

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

@app.get("/manual", response_class=HTMLResponse)
async def get_manual_page(username: str = Depends(authenticate)):
    """Serves the operation manual page."""
    with open("templates/manual.html", "r", encoding="utf-8") as f:
        return f.read()

from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
@app.get("/manual_md")
async def get_manual_markdown(username: str = Depends(authenticate)):
    """Serves the raw MANUAL.md content as plain text."""
    with open("MANUAL.md", "r", encoding="utf-8") as f:
        return PlainTextResponse(content=f.read())

async def get_stock_data_with_fallback(symbol: str, repo: StockRepository) -> StockData:
    """Gets latest data from API, falling back to DB if API returns mock data in non-mock mode."""
    data = get_cached_board(symbol)
    
    # If the API returned mock data (fallback in kabu_api.py or global Mock Mode)
    # then try to enhance it with better historical data from DB if available.
    if not data.is_real_data:
        latest_prices = await repo.get_latest_prices(symbol, limit=2)
        if latest_prices:
            p = latest_prices[0]
            # 1. マスターマップ（stock_names.json）を最優先
            if symbol in api_client.stock_name_map:
                better_name = api_client.stock_name_map[symbol]
                if better_name and better_name != "Unknown":
                    data.symbolname = better_name

            # 2. DB情報の確認と更新
            # 現在の名称が不十分（Unknown, Mock, 銘柄コード等）な場合、取得できた実名で上書きする
            # エラーメッセージが銘柄名に混入するのを防ぐ
            is_generic = data.symbolname == "Unknown" or "Mock" in data.symbolname or data.symbolname.startswith("銘柄")
            is_error_msg = any(x in data.symbolname for x in ["[Local AI Fallback]", "【接続エラー】", "【モデル未取得】"])
            
            if is_error_msg:
                 data.symbolname = "Unknown" # Reset if invalid
                 is_generic = True

            stock_master = await repo.get_or_create_stock(symbol, name=data.symbolname if not is_error_msg else "Unknown")
            
            if is_generic and stock_master.name != "Unknown" and not stock_master.name.startswith("銘柄"):
                # DBの方が良い名前を持っている場合
                data.symbolname = stock_master.name
            elif not is_generic and (stock_master.name == "Unknown" or stock_master.name.startswith("銘柄")):
                # APIの方が新しい実名を持っている場合、DBを更新
                stock_master.name = data.symbolname
                await repo.session.commit()
            
            data.currentprice = p.close
            
            # Update change percentage only if we have sufficient history
            if len(latest_prices) > 1:
                prev_p = latest_prices[1]
                data.previousclose = prev_p.close
                diff = p.close - prev_p.close
                new_percent = round((diff / prev_p.close) * 100, 2) if prev_p.close != 0 else 0.0
                
                # If DB results in 0.0 but we already have a non-zero mock value, keep the mock
                if new_percent != 0.0 or data.change_percent == 0.0:
                    data.change_percent = new_percent
            else:
                # If we only have 1 price record, keep the existing (e.g. mock) change percentage
                # if it's non-zero, otherwise set to 0.0
                if data.change_percent == 0.0:
                    data.previousclose = p.close
                    data.change_percent = 0.0
            
            data.volume = p.volume
            data.high = p.high
            data.low = p.low
            data.rsi = p.rsi_14
    
    # Ensure RSI is present from DB if API didn't provide it
    if data.rsi is None:
        try:
            latest_prices = await repo.get_latest_prices(symbol, limit=1)
            if latest_prices:
                data.rsi = latest_prices[0].rsi_14
        except:
            pass

    # 3. Ensure fundamental data (PER/PBR/Yield) is present for screening
    # Use cached or fresh symbol info if missing
    if data.per is None or data.pbr is None or data.dividend_yield is None:
        try:
            info = api_client.get_symbol_info(symbol)
            if info:
                data.per = data.per or info.get("PER")
                data.pbr = data.pbr or info.get("PBR")
                data.dividend_yield = data.dividend_yield or info.get("DividendYield")
                data.equity_ratio = data.equity_ratio or info.get("EquityRatio")
                data.credit_ratio = data.credit_ratio or info.get("MarginBuyRatio")
        except:
            pass
            
    # 4. Fallback to Scan Results CSV if still missing (Last resort for fundamentals)
    if data.per is None or data.pbr is None:
        try:
            csv_path = os.path.join("workspace", "Market_Data", "Market_Scan_Results.csv")
            if os.path.exists(csv_path):
                df_scan = pd.read_csv(csv_path)
                # Filter by string or int symbol
                match = df_scan[df_scan["銘柄コード"].astype(str) == str(symbol)]
                if not match.empty:
                    data.per = data.per or _safe_float(match.iloc[0].get("PER"))
                    data.pbr = data.pbr or _safe_float(match.iloc[0].get("PBR"))
                    data.dividend_yield = data.dividend_yield or _safe_float(match.iloc[0].get("利回り"))
        except:
            pass

    # Timezone aware logic for market status
    now = datetime.now(jst)
    
    # Market is open Mon-Fri, 9:00-11:30 and 12:30-15:00.
    is_weekend = now.weekday() >= 5
    current_time = now.time()
    
    is_market_open = (
        (dt_time(9, 0) <= current_time <= dt_time(11, 30)) or
        (dt_time(12, 30) <= current_time <= dt_time(15, 0))
    )
    
    should_show_closed = is_weekend or (not is_market_open)
    
    # Log for debug verification (visible in docker logs)
    # print(f"DEBUG: {symbol} at {now.strftime('%H:%M:%S')} JST -> MarketOpen={is_market_open}, ClosedSuffix={should_show_closed}")

    suffix = " (週末/閉場中)"
    if should_show_closed:
        if suffix not in data.symbolname:
            data.symbolname = f"{data.symbolname}{suffix}"
    else:
        if suffix in data.symbolname:
            data.symbolname = data.symbolname.replace(suffix, "")

    return data

@app.get("/api/stocks", response_model=List[StockData])
@retry_db_async()
async def get_stocks(refresh: bool = False, username: str = Depends(authenticate)):
    """Fetches latest data for all watched stocks including AI scores and DB fallback."""
    if refresh:
        print("[API] Manual refresh requested. Clearing cache.")
        global _api_cache
        _api_cache = {}

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
            # Use fallback enhanced data
            data = await get_stock_data_with_fallback(symbol, repo)
            
            # Proactive name refresh for the UI
            if not data.symbolname or "Unknown" in data.symbolname or "Mock" in data.symbolname or data.symbolname.startswith("銘柄"):
                # 1. Check Master Map
                if symbol in api_client.stock_name_map:
                    data.symbolname = api_client.stock_name_map[symbol]
                else:
                    # 2. Check Database
                    stock = await repo.get_or_create_stock(symbol)
                    if stock.name and not stock.name.startswith("Unknown") and not "Mock" in stock.name and not stock.name.startswith("銘柄"):
                        data.symbolname = stock.name
                
                # 3. Update DB if we found a better name
                if data.symbolname and not "Unknown" in data.symbolname and not "Mock" in data.symbolname and not data.symbolname.startswith("銘柄"):
                    await repo.get_or_create_stock(symbol, name=data.symbolname)

            # Set is_watched for UI (heart icon)
            data.is_watched = True

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
@retry_db_async()
async def add_to_watchlist(symbol: str, username: str = Depends(authenticate)):
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        # 追加時に即座にボード情報を取得して銘柄名を確定させる
        board = api_client.get_board(symbol)
        name = board.symbolname if board and board.symbolname and board.symbolname != "Unknown" else "Unknown"
        
        # 銘柄マスタを更新または作成（実名優先）
        await repo.get_or_create_stock(symbol, name=name)
        await repo.add_to_watchlist(symbol)
        
    return {"status": "added", "symbol": symbol, "name": name}

@app.delete("/api/watchlist/{symbol}")
@retry_db_async()
async def remove_from_watchlist(symbol: str, username: str = Depends(authenticate)):
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        await repo.remove_from_watchlist(symbol)
    return {"status": "removed", "symbol": symbol}

@app.get("/api/screening")
async def get_screening_results(refresh: bool = False, username: str = Depends(authenticate)):
    """Returns stocks filtered by strategies with AI data."""
    if refresh:
        print("[API] Manual screening refresh requested. Clearing cache.")
        global _api_cache
        _api_cache = {}

    full_list = []
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        # Fetch watchlist from DB
        db_watchlist = await repo.get_watchlist_symbols()
        if not db_watchlist: db_watchlist = settings.WATCHLIST
        
        for symbol in db_watchlist:
            data = await get_stock_data_with_fallback(symbol, repo)
            data.is_watched = True # Screening results from watchlist
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
                data = await get_stock_data_with_fallback(symbol, repo)
                if data: full_list.append(data)
    else:
        full_list = api_client.get_ranking(type)
    
    if not full_list:
        raise HTTPException(status_code=404, detail="No stock data available")
        
    prompt_text = prompts.generate_bulk_analysis_prompt(full_list)
    return {"prompt": prompt_text, "count": len(full_list)}

class ExportRequest(BaseModel):
    symbols: list[str] = None

class ScanAIRequest(BaseModel):
    symbols: Optional[list[str]] = None
    scope: Optional[str] = "scanner" # "scanner" or "watchlist"


@app.post("/api/export/notebooklm")
@app.get("/api/export/notebooklm")
@retry_db_async()
async def export_notebooklm(request: ExportRequest = None, username: str = Depends(authenticate)):
    """
    Generates a consolidated Markdown file for NotebookLM.
    Includes watchlist data, scanner results, and latest AI reports.
    """
    symbols = request.symbols if request else None
    logger.info(f"Exporting NotebookLM data... Symbols: {symbols}")
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # 1. Get Symbols
        if symbols:
            watchlist_symbols = symbols
        else:
            watchlist_symbols = await repo.get_watchlist_symbols()
        
        # 2. Fetch Data for each symbol
        stock_data_list = []
        reports_list = []
        for symbol in watchlist_symbols:
            try:
                data = await get_stock_data_with_fallback(symbol, repo)
                stock_data_list.append(data)
                
                report = await repo.get_latest_analysis(symbol)
                if report:
                    reports_list.append(report)
            except Exception as e:
                logger.error(f"Error fetching data for export ({symbol}): {e}")

        # 3. Fetch recent scanner results for context
        # (This is a simplified way to get some market context)
        scanner_results = []
        try:
             # Just use the current watchlist data as "market context" for now
             # but we could also fetch actual scanner results from a cache if we had one.
             pass
        except:
            pass

        # 4. Generate Content using the new prompt function
        content = prompts.generate_notebooklm_context(stock_data_list, reports_list, scanner_results)
            
    return {"prompt": content}

@app.post("/api/export/notebooklm/sync_drive")
@retry_db_async()
async def sync_notebooklm_to_drive(request: ExportRequest = None, username: str = Depends(authenticate)):
    """
    Generates the NotebookLM export and syncs it to Google Drive.
    Uses the dedicated '04_NotebookLM_Context' folder.
    Shares the file with emori@m-e-asset.com.
    """
    # 1. Generate content
    export_data = await export_notebooklm(request=request, username=username)
    content = export_data["prompt"]
    
    filename = f"NotebookLM_Export_{datetime.now(jst).strftime('%Y%m%d_%H%M%S')}.md"
    
    try:
        from drive_manager import DriveManager
        dm = DriveManager()
        
        # 2. Upload to Drive (using dedicated NotebookLM folder)
        folder = "04_NotebookLM_Context"
        file_id, web_link = dm.upload_file_content(filename, content, folder_name=folder)
        
        # 3. Share with the specific user
        target_email = "emori@m-e-asset.com"
        dm.share_with_user(file_id, target_email, role='reader')
        
        return {
            "status": "success", 
            "filename": filename, 
            "webViewLink": web_link,
            "shared_with": target_email,
            "folder": folder
        }
    except Exception as e:
        logger.error(f"Failed to sync to Drive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/full_workspace")
@retry_db_async()
async def trigger_full_workspace_sync(username: str = Depends(authenticate)):
    """
    Triggers a full recursive sync of the local workspace to Google Drive.
    """
    try:
        from drive_manager import DriveManager
        dm = DriveManager()
        root_link = dm.full_workspace_sync()
        return {"status": "success", "root_link": root_link}
    except Exception as e:
        logger.error(f"Full workspace sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prompt/{symbol}")
async def get_single_prompt(symbol: str, username: str = Depends(authenticate)):
    """Returns a detail analysis prompt for a single stock."""
    data = api_client.get_board(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Stock data not found")
        
    prompt_text = prompts.generate_analysis_prompt(data)
    return {"prompt": prompt_text}

@app.get("/api/analysis/prompt/{symbol}")
async def get_analysis_prompt(symbol: str, username: str = Depends(authenticate)):
    """Returns a clinical analysis prompt for detailed reporting."""
    data = api_client.get_board(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Stock data not found")
    prompt_text = prompts.generate_analysis_prompt(data)
    return {"prompt": prompt_text}

import report_manager
from analyzer_agent import GeminiAgent
import json
ai_agent = GeminiAgent()

@app.post("/api/analyze/{symbol}")
@retry_db_async()
async def analyze_stock(symbol: str, username: str = Depends(authenticate)):
    """
    Triggers AI analysis via Gemini and saves the structured result to the DB.
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # 1. Get Stock & Data
        stock = await repo.get_or_create_stock(symbol)
        
        # Ensure company name is updated if Unknown
        if stock.name == "Unknown":
            board = api_client.get_board(symbol)
            if board and board.symbolname:
                stock.name = board.symbolname
                await session.commit()
                await session.refresh(stock)

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
            
        # 2. Run Analysis (Gemini with Local Fallback)
        thinking_level = "standard"
        is_fallback = False
        
        try:
            try:
                analysis = await ai_agent.analyze(
                    stock=stock, 
                    context_data=history_str, 
                    thinking_level=thinking_level
                )
            except Exception as e:
                logger.error(f"Gemini AI analysis failed for {symbol}: {e}", exc_info=True)
                analysis = {"error": f"Gemini API call failed: {str(e)}"}

            if "error" in analysis and ("RESOURCE_EXHAUSTED" in analysis["error"] or "429" in analysis["error"] or "Gemini API call failed" in analysis["error"]):
                # Fallback to Local LLM if Gemini is over quota or failed
                print(f"Gemini API Quota Exceeded or failed for {symbol}. Falling back to Local AI...")
                from local_agent import LocalAgent
                local_agent = LocalAgent()
                # Simple prompt for local analysis
                local_result = await local_agent.screen_document(symbol, f"Manual Deep Analysis: {stock.name}", history_str)
                analysis = {
                    "score": 5.0 if local_result.get("priority") == "medium" else (7.0 if local_result.get("priority") == "high" else 3.0),
                    "summary": f"[Local AI Fallback] {local_result.get('reason')}",
                    "sentiment": "Neutral",
                    "reasoning": f"Gemini API was unavailable (Quota Limit or error). This is a fallback analysis from the local LLM.\n\n### Local Reasoning:\n{local_result.get('reason')}\n\n### Context used:\n{history_str}",
                    "source": "Local AI (Fallback)"
                }
                is_fallback = True
                thinking_level = "fallback"
            
            # 3. Save to DB
            if "error" not in analysis:
                report = await repo.save_analysis(
                    symbol=symbol,
                    analysis=analysis,
                    thinking_level=thinking_level
                )

                # Save to Local Workspace
                from workspace_manager import workspace_mgr
                prefix = "Fallback_" if is_fallback else "Analysis_"
                report_title = f"{prefix}{symbol}_{stock.name}"
                md_report = f"# {'【ローカルAI代行】' if is_fallback else '【AI個別銘柄分析レポート】'} {stock.name} ({symbol})\n"
                md_report += f"**分析日時:** {datetime.now(jst).strftime('%Y-%m-%d %H:%M')} (JST)\n"
                md_report += f"**AIスコア:** {analysis.get('score')}/10\n"
                md_report += f"**センチメント:** {analysis.get('sentiment')}\n\n"
                md_report += f"## 結論・要約\n{analysis.get('summary')}\n\n"
                md_report += f"## 分析詳細・根拠\n{analysis.get('reasoning')}\n"
                
                if is_fallback:
                    md_report += "\n---\n> [!IMPORTANT]\n> Gemini APIの実行制限により、ローカルAIによる暫定分析が実行されました。詳細な分析が必要な場合は、しばらく時間をおいてから再実行してください。\n"
                
                workspace_mgr.save_report(report_title, md_report)

                return {
                    "status": "success", 
                    "score": analysis.get("score"), 
                    "summary": analysis.get("summary"),
                    "is_fallback": is_fallback
                }
        except Exception as e:
            logger.error(f"Analysis process failed for {symbol}: {e}", exc_info=True)
            # Try to save a minimal failure report
            try:
                from workspace_manager import workspace_mgr
                fail_content = f"# Analysis Failed: {symbol}\nDate: {datetime.now()}\n\nError: {str(e)}\n\n申し訳ありませんが、分析処理中にエラーが発生しました。"
                workspace_mgr.save_report(f"Error_{symbol}", fail_content)
            except:
                pass
            return {"status": "error", "message": str(e)}
        finally:
            if "analysis" in locals() and "error" in analysis:
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
        
        return format_report(report)

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
        "report_content": report.report_content,
        "score": report.score,
        "summary": report.summary,
        "sentiment": report.sentiment,
        "persona_views": json.loads(report.persona_views) if report.persona_views else None,
        "catalysts": json.loads(report.catalysts) if report.catalysts else None,
        "created_at": report.created_at.isoformat(),
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
async def save_manual_report(symbol: str, report: ManualReportRequest, username: str = Depends(authenticate)):
    """
    Saves a manually pasted report from Gemini Web to the DB.
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        content_text = report.content
        score = float(report.score)
        
        # Wrap plain text in a JSON structure if it's not already
        structured_content = json.dumps({"text": content_text}, ensure_ascii=False)
        
        await repo.save_analysis(
            symbol=symbol,
            analysis={"summary": "Manual Paste Report", "score": score, "reasoning": content_text},
            thinking_level="manual_paste"
        )
        
        # Also save as physical file in Local Hub
        from workspace_manager import workspace_mgr
        # Use sanitized name for file
        safe_name = "".join([c for c in symbol if c.isalnum()])
        report_title = f"Manual_Analysis_{safe_name}"
        save_path = workspace_mgr.save_report(report_title, f"# Manual Analysis Report: {symbol}\n\n{content_text}")
        
        return {"status": "success", "file": os.path.basename(save_path)}

@app.post("/api/workspace/move_to_trash")
async def move_file_to_trash(request: dict, username: str = Depends(authenticate)):
    """Moves a file to the Trash folder. Request JSON: {'path': '/workspace/AI_Reports/file.md'}"""
    from workspace_manager import workspace_mgr
    path = request.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    success = workspace_mgr.move_to_trash(path)
    if success:
        return {"status": "success", "message": f"Moved {path} to trash"}
    else:
        raise HTTPException(status_code=404, detail="File not found or invalid path")

@app.delete("/api/workspace/delete_permanent")
async def delete_file_permanent(path: str, username: str = Depends(authenticate)):
    """Permanently deletes a file. Query param: ?path=/workspace/Trash/file.md"""
    from workspace_manager import workspace_mgr
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    
    success = workspace_mgr.delete_file(path)
    if success:
        return {"status": "success", "message": f"Deleted {path} permanently"}
    else:
        raise HTTPException(status_code=404, detail="File not found or invalid path")

@app.post("/api/workspace/bulk_move_to_trash")
async def bulk_move_to_trash(request: dict, username: str = Depends(authenticate)):
    """Moves multiple files to trash. Request JSON: {'paths': ['/workspace/AI_Reports/f1.md', ...]}"""
    from workspace_manager import workspace_mgr
    paths = request.get("paths", [])
    if not paths:
        raise HTTPException(status_code=400, detail="Paths are required")
    results = workspace_mgr.bulk_move_to_trash(paths)
    return results

@app.post("/api/workspace/bulk_delete_permanent")
async def bulk_delete_permanent(request: dict, username: str = Depends(authenticate)):
    """Permanently deletes multiple files. Request JSON: {'paths': ['/workspace/Trash/f1.md', ...]}"""
    from workspace_manager import workspace_mgr
    paths = request.get("paths", [])
    if not paths:
        raise HTTPException(status_code=400, detail="Paths are required")
    results = workspace_mgr.bulk_delete(paths)
    return results

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

# Mount workspace for local hub access
if not os.path.exists("workspace"):
    os.makedirs("workspace")
app.mount("/workspace", StaticFiles(directory="workspace"), name="workspace")

@app.get("/explorer", response_class=HTMLResponse)
async def get_explorer_page(username: str = Depends(authenticate)):
    """Serves the dedicated workspace file explorer page."""
    with open("templates/explorer.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/workspace/files")
async def list_workspace_files(category: str = None, username: str = Depends(authenticate)):
    """Returns a list of local files in the workspace hub."""
    from workspace_manager import workspace_mgr
    return workspace_mgr.list_files(category)

@app.get("/api/workspace/structure")
async def get_workspace_structure(username: str = Depends(authenticate)):
    """Returns the full hierarchical structure of the workspace."""
    from workspace_manager import workspace_mgr
    # Use absolute path for workspace directory
    base_dir = os.path.abspath("workspace")
    
    def get_dir_tree(path, base_url):
        tree = []
        if not os.path.exists(path): return tree
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            node = {
                "name": item,
                "is_dir": is_dir,
                "path": f"{base_url}/{item}"
            }
            if is_dir:
                node["children"] = get_dir_tree(full_path, f"{base_url}/{item}")
            else:
                stats = os.stat(full_path)
                # Apply JST timezone to the timestamp
                mtime_jst = datetime.fromtimestamp(stats.st_mtime, tz=jst)
                node["mtime"] = mtime_jst.isoformat()
                node["size"] = stats.st_size
            tree.append(node)
        return sorted(tree, key=lambda x: (not x["is_dir"], x["name"]))

    return get_dir_tree(base_dir, "/workspace")

@app.get("/api/workspace/links")
async def get_workspace_links(username: str = Depends(authenticate)):
    """Legacy endpoint. Redirects logic to local files."""
    return {"root": "/workspace/Market_Data", "reports": "/workspace/AI_Reports", "sheet": "/workspace/Market_Data/Master_Watchlist.csv"}
    try:
        # Try to get specific links
        root_link = drive_mgr.get_web_link(drive_mgr.root_folder_name)
        if not root_link:
            print("Workspace folders not found. Initializing...")
            root_link, _ = drive_mgr.setup_system_folders()
            
        # Get sheet link by name
        sheet_link = drive_mgr.get_web_link("Master_Watchlist")
        if not sheet_link:
            # Try searching for any spreadsheet if specific name fails
            results = drive_mgr.service.files().list(q="mimeType = 'application/vnd.google-apps.spreadsheet' and name contains 'Master_Watchlist' and trashed = false", fields="files(webViewLink)").execute()
            items = results.get('files', [])
            if items: sheet_link = items[0].get('webViewLink')

        reports_link = drive_mgr.get_web_link("02_AI_Daily_Reports")
    except Exception as e:
        print(f"Error fetching workspace links (possibly API disabled): {e}")
        return {"root": None, "sheet": None, "reports": None, "error": str(e)}
    
    return {
        "root": root_link,
        "sheet": sheet_link,
        "reports": reports_link
    }

import math


@app.get("/api/market_scanner")
async def get_scanner_results(type: str = "ranking", exchange: str = "ALL", username: str = Depends(authenticate)):
    """
    Returns stocks based on ranking type or top AI scores.
    1: Price Up, 2: Price Down, 3: Value Spike, 4: Volume Spike
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # 1. New: "last_scan" based on CSV
        if type == "last_scan":
            try:
                from workspace_manager import workspace_mgr
                csv_path = workspace_mgr.get_path("market", "Market_Scan_Results.csv")
                
                if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
                    logger.info("Market_Scan_Results.csv not found or empty, falling back to ranking type 1.")
                    type = "1"
                else:
                    df = pd.read_csv(csv_path)
                    
                    # 🔍 Check minimum requirements for the UI (Symbol and Name)
                    # Column names in bulk_screener: 銘柄コード, 銘柄名, 終値, 騰落率, 出来高, RSI, PER, PBR, 利回り, AIスコア, AI要約, ソース
                    required_cols = ["銘柄コード", "銘柄名"]
                    if not all(c in df.columns for c in required_cols):
                        logger.warning(f"CSV missing required columns. Found: {df.columns.tolist()}")
                        type = "1"
                    else:
                        results = []
                        for _, row in df.iterrows():
                            symbol = str(row["銘柄コード"])
                            # Enrich with AI data from DB if exists
                            report = await repo.get_latest_analysis(symbol)
                            
                            stock_dict = {
                                "symbol": symbol,
                                "symbolname": str(row.get("銘柄名", "Unknown")),
                                "currentprice": _safe_float(row.get("終値")) or 0.0,
                                "change_percent": _safe_float(row.get("騰落率")) or 0.0,
                                "volume": _safe_int(row.get("出来高")),
                                "rsi": _safe_float(row.get("RSI")),
                                "per": _safe_float(row.get("PER")),
                                "pbr": _safe_float(row.get("PBR")),
                                "dividend_yield": _safe_float(row.get("利回り")),
                                "ai_score": report.score if report else (_safe_float(row.get("AIスコア")) or 0.0),
                                "ai_summary": report.summary if report else str(row.get("AI要約", "")),
                                "is_watched": False 
                            }
                            results.append(stock_dict)
                        
                        if not results:
                            type = "1"
                        else:
                            return results
            except Exception as e:
                logger.error(f"Failed to read last scan CSV: {e}", exc_info=True)
                type = "1" # Fallback on error

        # 2. If type is a numeric ranking type, fetch live from API
        if type in ["1", "2", "3", "4", "13", "14", "15"]:
            try:
                # Fetch ranking from API with targeted Strategy/Exchange
                ranking_stocks = api_client.get_ranking(type, exchange=exchange)
                results = []
                for s in ranking_stocks:
                    # Enrich with AI data from DB if exists
                    report = await repo.get_latest_analysis(s.symbol)
                    
                    # Ensure name is not Unknown
                    if s.symbolname == "Unknown" or not s.symbolname:
                        # Attempt to get better name
                        if s.symbol in api_client.stock_name_map:
                            s.symbolname = api_client.stock_name_map[s.symbol]
                        else:
                            # Try DB
                            master = await repo.get_or_create_stock(s.symbol)
                            if master.name != "Unknown":
                                s.symbolname = master.name

                    stock_dict = s.dict()
                    if report:
                        stock_dict["ai_score"] = report.score
                        stock_dict["ai_summary"] = report.summary
                        stock_dict["ai_sentiment"] = report.sentiment
                    
                    results.append(stock_dict)
                return results
            except Exception as e:
                logger.error(f"Failed to fetch live ranking for scanner: {e}")
                # Fallback to Top AI stocks

        
        # 2. Default/Fallback: Fetch top 50 stocks sorted by AI score
        stocks = await repo.get_top_ai_stocks(limit=50)
        return stocks

@app.get("/api/admin/scan-status")
async def get_scan_status(username: str = Depends(authenticate)):
    """Returns the current market scan status."""
    return market_screener.get_status()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/api/health/local_ai")
async def check_local_ai_health():
    """Verifies connectivity to Ollama."""
    from local_agent import LocalAgent
    agent = LocalAgent()
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Check if Ollama is responding (Tags endpoint is lightweight)
            url = agent.BASE_URL.replace("/api", "/api/tags")
            async with session.get(url, timeout=2.0) as resp:
                if resp.status == 200:
                    return {"status": "online", "url": agent.BASE_URL}
                return {"status": "error", "message": f"HTTP {resp.status}"}
    except Exception as e:
        return {"status": "offline", "message": str(e), "url": agent.BASE_URL}

@app.get("/api/notes/{symbol}")
async def get_stock_notes(symbol: str, username: str = Depends(authenticate)):
    """Returns local LLM (EDINET) notes for a stock."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, desc
        from models_db import StockNote
        stmt = select(StockNote).where(StockNote.symbol == symbol).order_by(desc(StockNote.created_at))
        result = await session.execute(stmt)
        notes = result.scalars().all()
        return [
            {
                "id": n.id,
                "note": n.note,
                "priority": n.priority,
                "created_at": n.created_at.isoformat()
            }
            for n in notes
        ]

@app.post("/api/admin/scan-edinet")
async def trigger_edinet_scan(background_tasks: BackgroundTasks):
    """
    Triggers the EDINET scan and Local LLM screening manually.
    """
    from scheduler import run_edinet_scan
    background_tasks.add_task(run_edinet_scan)
    return {"status": "EDINET scan started in background"}

@app.post("/api/admin/scan-technical")
async def trigger_technical_scan(background_tasks: BackgroundTasks, strategy: str = "short"):
    """
    Fast technical scan based on strategy (short, long, undervalued).
    """
    background_tasks.add_task(market_screener.run_technical_scan, strategy=strategy)
    return {"message": f"Technical market scan ({strategy}) started in background."}

@app.post("/api/admin/scan-ai")
async def trigger_ai_scan(background_tasks: BackgroundTasks, request: Optional[ScanAIRequest] = None):
    """
    Local AI screening for specific symbols or results found by technical scan.
    """
    symbols = request.symbols if request else None
    scope = request.scope if request else "scanner"
    background_tasks.add_task(market_screener.run_ai_screening, symbols=symbols, scope=scope)
    return {"message": f"Local AI screening ({scope}) started in background."}


@app.post("/api/admin/scan-market")
async def trigger_full_scan(background_tasks: BackgroundTasks):
    """
    Legacy/Full scan (Tech + AI sequentially).
    """
    background_tasks.add_task(market_screener.run_market_scan)
    return {"message": "Full hybrid scan started in background."}

@app.post("/api/admin/scan-cancel")
async def cancel_scan():
    """
    Cancels the ongoing AI screening.
    """
    market_screener.cancel_requested = True
    return {"message": "Cancellation request sent to the screener."}

@app.get("/api/analysis/trade/{symbol}")
async def get_trade_analysis(symbol: str):
    """
    Generate a detailed trade analysis (Entry/Exit/Stop) using Gemini.
    """
    prompt = f"""銘柄コード: {symbol} について、具体的な売買戦略（トレードプラン）を提案してください。
以下の構成で日本語で回答してください：
1. 【エントリー基準】どの価格帯、またはどのようなシグナルで買うべきか
2. 【利確ポイント】期待できる目標価格とその理由
3. 【損切りライン】リスク許容範囲としての撤退価格
4. 【総合コメント】このトレードの期待値とリスクのバランス

出力はMarkdown形式でお願いします。"""
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        stock = await repo.get_or_create_stock(symbol)
        
        # Latest data context
        data = await get_stock_data_with_fallback(symbol, repo)
        context = f"現在値: {data.currentprice}, 前日比: {data.change_percent}%, RSI: {data.rsi}, 出来高: {data.volume}"
        
        full_prompt = f"{prompt}\n\n[参考データ]\n{context}"

    try:
        # Use existing Gemini agent
        from analyzer_agent import GeminiAgent
        agent = GeminiAgent(model_id="gemini-2.0-flash") # Use standard flash
        # Pass stock object and context
        report_data = await agent.analyze(stock, full_prompt)
        
        # If it returned a dict (structured), extract reasoning or summary
        if isinstance(report_data, dict):
            if "analysis" in report_data:
                return {"symbol": symbol, "analysis": report_data["analysis"]}
            if "reasoning" in report_data:
                 return {"symbol": symbol, "analysis": report_data["reasoning"]}
            return {"symbol": symbol, "analysis": json.dumps(report_data, ensure_ascii=False)}
        
        return {"symbol": symbol, "analysis": report_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/trade_prompt/{symbol}")
async def get_trade_strategy_prompt(symbol: str, username: str = Depends(authenticate)):
    """
    Returns a manual prompt for trade strategy (Entry/Exit/Stop).
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        stock = await repo.get_or_create_stock(symbol)
        data = await get_stock_data_with_fallback(symbol, repo)
        
        # Fetch some history for better prompt
        history = await repo.get_latest_prices(symbol, limit=10)
        history_str = ""
        if history:
            history_str = "\n".join([f"- {p.time.strftime('%m/%d')}: {p.close} (RSI:{p.rsi_14})" for p in reversed(history)])

        prompt = f"""あなたはプロのトレーダーです。以下の銘柄について、具体的かつ実戦的な売買戦略（トレードプラン）を日本語で提案してください。

銘柄: {stock.name} ({symbol})
現在値: {data.currentprice}
騰落率: {data.change_percent}%
RSI: {data.rsi}
出来高: {data.volume}

[直近の株価推移]
{history_str}

以下の構成で回答してください：
1. 【エントリー基準】どの価格帯、またはどのようなシグナルで買うべきか
2. 【利確ポイント】期待できる目標価格とその理由
3. 【損切りライン】リスク許容範囲としての撤退価格
4. 【総合コメント】このトレードの期待値とリスクのバランス

出力はMarkdown形式でお願いします。"""
        
        return {"symbol": symbol, "prompt": prompt}

@app.get("/api/analysis/local_trade/{symbol}")
async def get_local_trade_analysis(symbol: str, username: str = Depends(authenticate)):
    """
    Generate trade strategy using Local LLM (Ollama).
    """
    # 1. Reuse the prompt generation logic (internal call or refactor)
    prompt_data = await get_trade_strategy_prompt(symbol, username)
    prompt = prompt_data["prompt"]
    
    try:
        from local_agent import LocalAgent
        agent = LocalAgent()
        
        # 2. Call Local AI
        analysis = await agent.generate_response(prompt)
        
        return {
            "symbol": symbol,
            "analysis": analysis,
            "source": f"Local AI ({agent.model})"
        }
    except Exception as e:
        logger.error(f"Local trade analysis failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Local AI Error: {str(e)}")

async def run_bulk_local_trade_analysis(symbols: list[str]):
    """
    Background worker for bulk local trade analysis.
    Uses per-symbol DB sessions to isolate transaction failures.
    """
    from local_agent import LocalAgent
    agent = LocalAgent()
    
    total = len(symbols)
    logger.info(f"Starting bulk local trade analysis for {total} stocks...")
    
    for i, symbol in enumerate(symbols):
        try:
            # 1. Generate Prompt
            prompt_data = await get_trade_strategy_prompt(symbol, "admin")
            prompt = prompt_data["prompt"]
            
            # 2. Call Local AI
            analysis = await agent.generate_response(prompt)
            
            # 3. Save to DB (Use a fresh session per symbol to avoid poisoned transactions)
            async with AsyncSessionLocal() as session:
                repo = StockRepository(session)
                await repo.update_latest_trade_strategy(symbol, analysis)
            logger.info(f"[{i+1}/{total}] Local trade analysis saved for {symbol}")
            
        except Exception as e:
            logger.error(f"Failed bulk trade analysis for {symbol}: {e}")
        
        # Rate limit/Load relief for Local AI
        await asyncio.sleep(1)

@app.post("/api/admin/bulk-local-trade")
async def trigger_bulk_local_trade(background_tasks: BackgroundTasks, username: str = Depends(authenticate)):
    """
    Triggers local AI analysis for all watchlist stocks.
    """
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        symbols = await repo.get_watchlist_symbols()
        if not symbols:
            symbols = settings.WATCHLIST
    
    background_tasks.add_task(run_bulk_local_trade_analysis, symbols)
    return {"message": f"Bulk local AI trade analysis started for {len(symbols)} stocks."}

@app.get("/api/consolidated_prompt")
async def get_consolidated_prompt(username: str = Depends(authenticate)):
    """
    Generates (or returns cached) massive synthesis prompt for all watchlist stocks.
    """
    import os
    from workspace_manager import workspace_mgr
    
    # 1. Check for background-generated cache (from overnight scan)
    cache_path = workspace_mgr.get_path("config", "Consolidated_Prompt.txt")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content:
                print(f"[API] Returning cached consolidated prompt from {cache_path}")
                return {"prompt": content, "cached": True}
        except Exception as e:
            print(f"Error reading prompt cache: {e}")

    # 2. Fallback to on-demand generation
    print("[API] No cache found. Generating consolidated prompt on-demand...")
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        symbols = await repo.get_watchlist_symbols()
        if not symbols:
            symbols = settings.WATCHLIST
            
        stocks_data = []
        for symbol in symbols:
            # 1. Current Market Data
            stock_data = await get_stock_data_with_fallback(symbol, repo)
            
            # 2. Latest AI Report (contains Gemini score/summary AND Local Trade Strategy)
            report = await repo.get_latest_analysis(symbol)
            
            # 3. EDINET/Disclosure Notes
            from sqlalchemy import select, desc
            from models_db import StockNote
            stmt = select(StockNote).where(StockNote.symbol == symbol).order_by(desc(StockNote.created_at)).limit(3)
            res = await session.execute(stmt)
            notes = res.scalars().all()
            
            stocks_data.append({
                "stock": stock_data,
                "report": report,
                "notes": notes
            })
            
        prompt = prompts.generate_consolidated_gemini_prompt(stocks_data)
        return {"prompt": prompt, "count": len(stocks_data)}
