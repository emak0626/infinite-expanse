from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
import json
import pandas as pd
from config import settings
from database import AsyncSessionLocal
from repository import StockRepository
from kabu_com_client import KabucomClient
from kabu_api import KabuApiClient as MockClient

from analyzer_agent import GeminiAgent
from drive_manager import DriveManager
from sheets_manager import SheetsManager
from batch_screener import BatchScreener
from docs_manager import DocsManager

# Initialize Clients
real_client = KabucomClient()
mock_client = MockClient(mock_mode=True)
agent = GeminiAgent()
drive_mgr = DriveManager()
sheets_mgr = SheetsManager()
batch_screener = BatchScreener()
docs_mgr = DocsManager()

scheduler = AsyncIOScheduler()

async def fetch_stock_data_job():
    """
    Periodic job to fetch stock data, save to DB, and sync to Sheets.
    """
    print(f"[{datetime.now()}] Starting Data Fetch Job...")
    
    fetched_data_list = []
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # Fetch dynamic watchlist from DB
        db_watchlist = await repo.get_watchlist_symbols()
        if not db_watchlist:
            db_watchlist = settings.WATCHLIST
        
        for symbol in db_watchlist:
            try:
                # 1. Fetch Data
                if settings.MOCK_MODE:
                    data = mock_client.get_board(symbol)
                    p_close = data.currentprice
                    row_data = {
                        "symbol": symbol,
                        "open": data.currentprice,
                        "high": data.high,
                        "low": data.low,
                        "close": data.currentprice,
                        "volume": data.volume,
                        "rsi_14": data.rsi
                    }
                else:
                    board = real_client.get_board(symbol)
                    if not board:
                        continue
                        
                    p_close = float(board.get("CurrentPrice", 0))
                    row_data = {
                        "symbol": symbol,
                        "open": float(board.get("OpeningPrice", 0)),
                        "high": float(board.get("HighPrice", 0)),
                        "low": float(board.get("LowPrice", 0)),
                        "close": p_close,
                        "volume": int(board.get("TradingVolume", 0)),
                        "rsi_14": 50.0 # Placeholder
                    }
                
                # 2. Save to DB
                await repo.add_price(symbol, {k: v for k, v in row_data.items() if k != "symbol"})
                fetched_data_list.append(row_data)
                print(f"Saved {symbol}: {p_close}")
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")

        # 3. Sync to Google Sheets (Master Watchlist)
        if fetched_data_list:
            df = pd.DataFrame(fetched_data_list)
            try:
                # Ensure folder structure exists
                _, folder_map = drive_mgr.setup_system_folders()
                market_data_folder_id = folder_map.get("01_Market_Data")
                
                sheets_mgr.write_dataframe(
                    spreadsheet_title="Master_Watchlist",
                    sheet_name="Realtime_Data",
                    df=df,
                    folder_id=market_data_folder_id
                )
            except Exception as e:
                print(f"Skipping sync to Sheets (API might be disabled): {e}")

async def run_daily_analysis():
    """
    Daily job: Batch Screening -> Sync Results -> Deep-dive Top Stocks -> Create Docs.
    """
    print(f"[{datetime.now()}] Starting Daily AI Pipeline...")
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # 1. Prepare data for Batch Screening
        db_watchlist = await repo.get_watchlist_symbols()
        if not db_watchlist: db_watchlist = settings.WATCHLIST
        
        batch_input = []
        for symbol in db_watchlist:
            history = await repo.get_latest_prices(symbol, limit=5)
            if history:
                latest = history[0]
                batch_input.append({
                    "symbol": symbol,
                    "price": latest.close,
                    "volume": latest.volume,
                    "rsi": latest.rsi_14
                })
        
        if not batch_input:
            print("No data available for batch screening.")
            return

        # 2. Batch Screening
        print(f"Running batch screening for {len(batch_input)} stocks...")
        screen_results = await batch_screener.screen_batch(batch_input)
        
        if not screen_results:
            print("Batch screening returned no results.")
            return

        # 3. Sync Screening Results to Sheets
        results_df = pd.DataFrame(screen_results)
        try:
            root_id, folder_map = drive_mgr.setup_system_folders()
            sheets_mgr.write_dataframe(
                spreadsheet_title="Master_Watchlist",
                sheet_name="AI_Screening_Results",
                df=results_df,
                folder_id=folder_map.get("01_Market_Data")
            )
            print("Batch results synced to Google Sheets.")
        except Exception as e:
            print(f"Skipping Workspace Sync (API might be disabled): {e}")
            folder_map = {} # Fallback

        # 4. Selective Deep-dive & Google Docs Reporting
        # Sort by score descending
        sorted_results = sorted(screen_results, key=lambda x: x.get('score', 0), reverse=True)
        top_candidates = sorted_results[:3]
        
        reports_folder_id = folder_map.get("02_AI_Daily_Reports")
        
        print(f"Starting deep-dive analysis and reporting for top {len(top_candidates)} candidates...")
        
        for candidate in top_candidates:
            symbol = candidate['symbol']
            tag = candidate.get('tag', 'Watch')
            try:
                stock = await repo.get_or_create_stock(symbol)
                history = await repo.get_latest_prices(symbol, limit=20)
                
                history_str = "\n".join([
                    f"{p.time.strftime('%Y-%m-%d')}: Close={p.close}, RSI={p.rsi_14}"
                    for p in reversed(history)
                ])
                
                # Detailed Analysis
                analysis = await agent.analyze(stock, history_str, thinking_level="high")
                
                if "error" not in analysis:
                    # Save to DB
                    await repo.save_analysis(
                        symbol=symbol,
                        content=json.dumps(analysis, indent=2, ensure_ascii=False),
                        score=float(analysis.get("score", 0)),
                        thinking_level="high",
                        summary=analysis.get("summary"),
                        sentiment=analysis.get("sentiment")
                    )
                    
                    # Generate Google Doc Report
                    report_title = f"{datetime.now().strftime('%Y-%m-%d')} AI Report: {symbol} ({tag})"
                    md_report = f"# AI Deep Analysis Report: {symbol}\n"
                    md_report += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    md_report += f"**Category:** {tag}\n"
                    md_report += f"**AI Score:** {analysis.get('score')}/10\n\n"
                    md_report += f"## Summary\n{analysis.get('summary')}\n\n"
                    md_report += f"## Reasoning\n{analysis.get('reasoning')}\n\n"
                    md_report += f"## Risks\n" + "\n".join([f"- {r}" for r in analysis.get('risks', [])]) + "\n\n"
                    md_report += f"## Opportunities\n" + "\n".join([f"- {o}" for o in analysis.get('opportunities', [])]) + "\n"

                    # Determine subfolder
                    subfolder_name = "Long_Term" if tag == "Long-term" else "Short_Term_Swing"
                    sub_folder_id = drive_mgr.get_folder_id(subfolder_name, parent_id=reports_folder_id)
                    if not sub_folder_id:
                        sub_folder_id = drive_mgr.create_folder(subfolder_name, parent_id=reports_folder_id)

                    docs_mgr.create_doc_from_markdown(report_title, md_report, folder_id=sub_folder_id)
                    print(f"Report and Doc created for {symbol}")
                
                # Delay to respect rate limits
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Error in deep-dive/reporting for {symbol}: {e}")

def start_scheduler():
    # Fetch & Sync to Sheets: Every 10 minutes (for production realism)
    trigger_fetch = CronTrigger(minute="*/10") 
    scheduler.add_job(fetch_stock_data_job, trigger_fetch)
    
    # AI Analysis Pipeline: Every day at 16:00
    trigger_analyze = CronTrigger(hour=16, minute=10)
    scheduler.add_job(run_daily_analysis, trigger_analyze)
    
    scheduler.start()
    print("Scheduler Started with Google Workspace Sync and AI Pipeline.")
