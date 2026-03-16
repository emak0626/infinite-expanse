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
from edinet_client import EdinetClient
from local_agent import LocalAgent
from workspace_manager import workspace_mgr

# Initialize Clients
real_client = KabucomClient()
mock_client = MockClient(mock_mode=True)
agent = GeminiAgent()
drive_mgr = DriveManager()
sheets_mgr = SheetsManager()
batch_screener = BatchScreener()
docs_mgr = DocsManager()
edinet_client = EdinetClient()
local_agent = LocalAgent()

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

        # 3. Save to Local Workspace (replacing Sheets)
        if fetched_data_list:
            df = pd.DataFrame(fetched_data_list)
            try:
                path = workspace_mgr.save_csv(df, "Master_Watchlist.csv")
                print(f"Data synced to local workspace: {path}")
            except Exception as e:
                print(f"Failed to save data to workspace: {e}")

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

                    # Save to Local Workspace
                    path = workspace_mgr.save_report(report_title, md_report)
                    print(f"Report saved to local workspace: {path}")

                    # Phase 2: Index into Long-Term Memory (RAG)
                    await agent.kb.add_knowledge(symbol, analysis.get("reasoning", ""), "Daily AI Analysis Report")
                    print(f"Indexed {symbol} analysis into long-term memory.")
                
                # Delay to respect rate limits
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Error in deep-dive/reporting for {symbol}: {e}")

async def run_edinet_scan():
    """
    Daily job: Scan EDINET for relevant documents.
    """
    print(f"[{datetime.now()}] Starting EDINET Scan Job...")
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        target_symbols = await repo.get_watchlist_symbols()
        
        docs = await edinet_client.get_documents_on_date()
        relevant = await edinet_client.filter_relevant_documents(docs, target_symbols)
        
        for doc in relevant:
            print(f"New Document Found: {doc['symbol']} - {doc['title']}")
            # Phase 1.5: Local LLM Screening
            screening = await local_agent.screen_document(doc['symbol'], doc['title'])
            
            if screening.get("is_important"):
                print(f"-> [IMPORTANT] Local LLM tagged for deep analysis: {screening.get('reason')}")
                # Save Detailed Disclosure Report to Workspace
                report_content = f"# 重要開示レポート: {doc['title']}\n\n"
                report_content += f"**銘柄**: {doc['symbol']}\n"
                report_content += f"**タイトル**: {doc['title']}\n"
                report_content += f"**判定理由**: {screening.get('reason')}\n\n"
                report_content += "---"
                workspace_mgr.save_report(f"Disclosure_{doc['symbol']}", report_content)
                
                await repo.add_stock_note(doc['symbol'], f"重要開示({screening.get('priority')}): {doc['title']} - {screening.get('reason')}")
                # In next step, we could trigger agent.analyze with higher priority here
            else:
                print(f"-> [SKIP] Local LLM deemed not urgent: {screening.get('reason')}")
                await repo.add_stock_note(doc['symbol'], f"開示: {doc['title']} (AI判定: 低優先)")

def start_scheduler():
    # Fetch & Sync to Sheets: Every 10 minutes (for production realism)
    trigger_fetch = CronTrigger(minute="*/10") 
    scheduler.add_job(fetch_stock_data_job, trigger_fetch)
    
    # AI Analysis Pipeline: Every day at 16:00
    trigger_analyze = CronTrigger(hour=16, minute=10)
    scheduler.add_job(run_daily_analysis, trigger_analyze)

    # EDINET Scan: Every day at 17:00
    trigger_edinet = CronTrigger(hour=17, minute=0)
    scheduler.add_job(run_edinet_scan, trigger_edinet)
    
    scheduler.start()
    print("Scheduler Started with Google Workspace Sync and AI Pipeline.")
    
    # Trigger initial scan on startup to ensure data exists
    asyncio.create_task(run_edinet_scan())
