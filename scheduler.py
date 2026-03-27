from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date, timedelta
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

# Initialize timezone
from datetime import timezone, timedelta
jst = timezone(timedelta(hours=9), name='JST')

scheduler = AsyncIOScheduler(timezone=jst)

async def calculate_rsi_14(repo, symbol: str, current_close: float) -> float:
    # 簡易RSI計算
    history = await repo.get_latest_prices(symbol, limit=14)
    if not history:
        return 50.0
    
    prices = [p.close for p in reversed(history)] + [current_close]
    if len(prices) < 2:
        return 50.0
    
    gains = 0.0
    losses = 0.0
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
            
    avg_gain = gains / 14.0
    avg_loss = losses / 14.0
    
    if avg_loss == 0:
        return 100.0 if gains > 0 else 50.0
        
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)

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
                stock_master = await repo.get_or_create_stock(symbol)
                if settings.MOCK_MODE:
                    data = mock_client.get_board(symbol)
                    p_close = data.currentprice
                    row_data = {
                        "symbol": symbol,
                        "name": stock_master.name,
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
                        "name": stock_master.name,
                        "open": float(board.get("OpeningPrice", 0)),
                        "high": float(board.get("HighPrice", 0)),
                        "low": float(board.get("LowPrice", 0)),
                        "close": p_close,
                        "volume": int(board.get("TradingVolume", 0)),
                        "rsi_14": await calculate_rsi_14(repo, symbol, p_close)
                    }
                
                # 2. Save to DB (exclude name as it's not in prices table)
                await repo.add_price(symbol, {k: v for k, v in row_data.items() if k not in ("symbol", "name")})
                fetched_data_list.append(row_data)
                print(f"Saved {symbol}: {p_close}")
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")

        # 3. Save to Local Workspace
        if fetched_data_list:
            df = pd.DataFrame(fetched_data_list)
            # Translate columns for user-facing CSV
            df_display = df.rename(columns={
                "symbol": "銘柄コード",
                "name": "銘柄名",
                "open": "始値",
                "high": "高値",
                "low": "安値",
                "close": "終値",
                "volume": "出来高",
                "rsi_14": "RSI(14)"
            })
            try:
                path = workspace_mgr.save_csv(df_display, "Master_Watchlist.csv")
                print(f"Data synced to local workspace (Japanese CSV): {path}")
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
            stock_master = await repo.get_or_create_stock(symbol) # Get name
            history = await repo.get_latest_prices(symbol, limit=5)
            if history:
                latest = history[0]
                batch_input.append({
                    "symbol": symbol,
                    "name": stock_master.name,
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
        # カラム名を日本語に変換して保存
        df_display = results_df.rename(columns={
            "symbol": "銘柄コード",
            "name": "銘柄名",
            "score": "AIスコア",
            "tag": "判定",
            "comment": "分析コメント"
        })
        
        try:
            root_id, folder_map = drive_mgr.setup_system_folders()
            sheets_mgr.write_dataframe(
                spreadsheet_title="Master_Watchlist",
                sheet_name="AI_Screening_Results",
                df=df_display,
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

async def run_overnight_scan():
    """
    Scheduled midnight job: Technical Scan + AI Screening.
    """
    from main import market_screener
    print(f"[{datetime.now()}] Starting Overnight Full Hybrid Scan...")
    await market_screener.run_market_scan()
    
    # 🔍 New: After scan, pre-generate the consolidated prompt for the user
    print(f"[{datetime.now()}] Pre-generating consolidated prompt for tomorrow...")
    await generate_daily_consolidated_prompt()

async def generate_daily_consolidated_prompt():
    """
    Background job to pre-calculate the massive 'Comprehensive Consultation' prompt.
    Saved to workspace/System_Config/Consolidated_Prompt.txt
    """
    from main import get_stock_data_with_fallback
    import prompts
    
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        symbols = await repo.get_watchlist_symbols()
        if not symbols:
            symbols = settings.WATCHLIST
            
        stocks_data = []
        for symbol in symbols:
            try:
                stock_data = await get_stock_data_with_fallback(symbol, repo)
                report = await repo.get_latest_analysis(symbol)
                
                from sqlalchemy import select, desc
                from models_db import StockNote
                stmt = select(StockNote).where(StockNote.symbol == symbol).order_by(desc(StockNote.created_at)).limit(5)
                res = await session.execute(stmt)
                notes = res.scalars().all()
                
                stocks_data.append({
                    "stock": stock_data,
                    "report": report,
                    "notes": notes
                })
            except Exception as e:
                print(f"Error gathering data for prompt ({symbol}): {e}")
                
        if stocks_data:
            prompt = prompts.generate_consolidated_gemini_prompt(stocks_data)
            
            # Save to local workspace
            save_path = workspace_mgr.get_path("config", "Consolidated_Prompt.txt")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(prompt)
            print(f"Consolidated prompt cached at: {save_path}")

async def run_edinet_scan():
    """
    Daily job: Scan EDINET for relevant documents.
    Now expanded to include Watchlist + Top 50 AI-scored stocks.
    """
    print(f"[{datetime.now()}] Starting EDINET Scan Job...")
    async with AsyncSessionLocal() as session:
        repo = StockRepository(session)
        
        # 1. Target Symbols: Watchlist + Recent Top Performers
        watchlist_symbols = await repo.get_watchlist_symbols()
        top_ai_data = await repo.get_top_ai_stocks(limit=50)
        top_ai_symbols = [s['symbol'] for s in top_ai_data if s['ai_score'] >= 6.5]
        
        target_symbols = list(set(watchlist_symbols + top_ai_symbols))
        print(f"EDINET Watchlist: {len(target_symbols)} symbols (Watchlist:{len(watchlist_symbols)}, TopAI:{len(top_ai_symbols)})")
        
        # 2. Date check: Try Today, fallback to Yesterday if today yields nothing
        # (Useful for early morning runs or late submissions)
        search_dates = [date.today(), date.today() - timedelta(days=1)]
        
        from edinet_client import EdinetClient
        e_client = EdinetClient()
        
        any_found = False
        for target_date in search_dates:
            print(f"Checking EDINET for date: {target_date}...")
            docs = await e_client.get_documents_on_date(target_date)
            if not docs:
                print(f"No documents found on {target_date}.")
                continue
                
            relevant = await e_client.filter_relevant_documents(docs, target_symbols)
            if not relevant:
                print(f"No relevant disclosures for target stocks on {target_date} among {len(docs)} documents.")
                continue

            for doc in relevant:
                any_found = True
                print(f"New Document Found: {doc['symbol']} - {doc['title']}")
                
                # Fetch actual document text for deeper content analysis
                doc_text = await e_client.get_document_text(doc['docID'])
                snippet = (doc['title'] + "\n" + doc_text)[:4000] 
                
                # Local LLM Screening with full context
                screening = await local_agent.screen_document(doc['symbol'], doc['title'], content_snippet=snippet)
                
                if screening.get("is_important") or screening.get("priority") in ["high", "medium"]:
                    print(f"-> [IMPORTANT] AI tagged for report: {screening.get('reason')}")
                    # Save Detailed Disclosure Report to Workspace
                    report_content = f"# 重要開示レポート: {doc['title']}\n\n"
                    report_content += f"**銘柄**: {doc['symbol']}\n"
                    report_content += f"**判定日時**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    report_content += f"**判定理由**: {screening.get('reason')}\n\n"
                    report_content += "---"
                    workspace_mgr.save_report(f"Disclosure_{doc['symbol']}", report_content)
                    
                    await repo.add_stock_note(doc['symbol'], f"重要開示({screening.get('priority')}): {doc['title']}")
                else:
                    print(f"-> [SKIP] AI deemed not urgent for {doc['symbol']}: {screening.get('reason')}")
                    await repo.add_stock_note(doc['symbol'], f"開示: {doc['title']} (AI判定: {screening.get('priority')})")
            
            if any_found:
                break # Found stuff for today/yesterday, stop searching back

        if not any_found:
            print("EDINET Scan finished: No relevant important documents found.")

async def full_sync_job():
    """
    Daily job to sync the entire local workspace to Google Drive.
    """
    print(f"[{datetime.now()}] Starting Full Workspace Sync to Drive...")
    try:
        from drive_manager import drive_mgr
        drive_mgr.full_workspace_sync()
        print("Full workspace sync completed.")
    except Exception as e:
        print(f"Full workspace sync failed: {e}")

from market_context import market_fetcher

async def update_market_context_job():
    """Fetches and saves latest market indices and news (2x per day)."""
    print(f"[{datetime.now()}] Updating Market Context...")
    try:
        market_fetcher.save_context()
        print("Market Context updated successfully.")
    except Exception as e:
        print(f"Failed to update market context: {e}")

def start_scheduler():
    # Fetch & Sync to Sheets: Every 10 minutes (for production realism)
    trigger_fetch = CronTrigger(minute="*/10", timezone=jst) 
    scheduler.add_job(fetch_stock_data_job, trigger_fetch)
    
    # Market Context Update (Indices/News): 08:30 and 12:30 JST
    scheduler.add_job(update_market_context_job, CronTrigger(hour=8, minute=30, timezone=jst))
    scheduler.add_job(update_market_context_job, CronTrigger(hour=12, minute=30, timezone=jst))

    # AI Analysis Pipeline: Every day at 16:10 JST
    trigger_analyze = CronTrigger(hour=16, minute=10, timezone=jst)
    scheduler.add_job(run_daily_analysis, trigger_analyze)

    # EDINET Scan: Every day at 17:00 JST
    trigger_edinet = CronTrigger(hour=17, minute=0, timezone=jst)
    scheduler.add_job(run_edinet_scan, trigger_edinet)
    
    # Overnight Full Scan: Every day at 02:00 JST
    trigger_overnight = CronTrigger(hour=2, minute=0, timezone=jst)
    scheduler.add_job(run_overnight_scan, trigger_overnight)
    
    # Full Workspace Sync: Every day at 18:00 JST
    trigger_sync = CronTrigger(hour=18, minute=0, timezone=jst)
    scheduler.add_job(full_sync_job, trigger_sync)
    
    scheduler.start()
    print("Scheduler Started with Market Context Updates and AI Pipeline.")
    
    # Trigger initial scans on startup to ensure data exists
    asyncio.create_task(update_market_context_job())
    asyncio.create_task(run_edinet_scan())
