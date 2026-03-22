import asyncio
import os
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from kabu_api import KabuApiClient
from repository import StockRepository
from local_agent import LocalAgent
from analyzer_agent import GeminiAgent
from config import settings
from database import AsyncSessionLocal
from workspace_manager import workspace_mgr
import pandas as pd

logger = logging.getLogger(__name__)
jst = timezone(timedelta(hours=9))

class BulkScreener:
    """
    Automates scanning of the entire market using a hybrid AI pipeline.
    Tier 1: Local LLM (Ollama) filters nodes based on raw data/titles.
    Tier 2: Gemini 2.0 Flash (Free API) performs semantic analysis on filtered candidates.
    """
    
    def __init__(self):
        self.api_client = KabuApiClient()
        self.local_agent = LocalAgent()
        self.cancel_requested = False
        # Ensure we use Gemini 2.0 Flash for efficiency/free tier
        self.gemini_agent = GeminiAgent(model_id="gemini-2.0-flash-exp") 
        self.is_running = False
        self.state_file = "workspace/System_Config/scan_state.json"
        self._ensure_state_dir()

    def _ensure_state_dir(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

    def get_status(self):
        """Returns the current status and last run time."""
        state = self._load_state()
        return {
            "is_running": self.is_running,
            "last_scan_at": state.get("last_scan_at"),
            "last_scan_count": state.get("last_scan_count", 0)
        }

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_state(self, last_at, count, last_ai_at=None):
        state = self._load_state()
        state.update({"last_scan_at": last_at, "last_scan_count": count})
        if last_ai_at:
            state["last_ai_scan_at"] = last_ai_at
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    async def run_technical_scan(self, strategy: str = "short"):
        """
        Fast scan for active stocks based on strategy.
        short: Price Up / Volume Spike
        long: low PER / High Dividend
        undervalued: low PBR
        """
        if self.is_running:
            return {"error": "Scan already in progress."}
        
        self.is_running = True
        logger.info(f"Starting Technical Market Scan (Strategy: {strategy})...")
        jst = timezone(timedelta(hours=9))
        start_time = datetime.now(jst)
        
        try:
            # 1. Map strategy to ranking types and exchanges
            exchange = "ALL"
            if strategy == "long":
                rank_types = ["13", "15"] # low PER, High Dividend
            elif strategy == "undervalued":
                rank_types = ["14"] # low PBR
            elif strategy == "growth":
                rank_types = ["1", "4"] # Price Up + Volume Spike
                exchange = "G"
            elif strategy == "standard":
                rank_types = ["1", "4"] # Price Up + Volume Spike
                exchange = "S"
            else: # short (default)
                rank_types = ["1", "3", "4"] # Price Up, Value Spike, Volume Spike
            
            all_ranking_stocks = []
            for r_type in rank_types:
                try:
                    logger.info(f"Fetching ranking type {r_type} for exchange {exchange}...")
                    stocks = self.api_client.get_ranking(r_type, exchange=exchange)
                    if stocks:
                        logger.info(f"Found {len(stocks)} stocks for ranking type {r_type}")
                        all_ranking_stocks.extend(stocks)
                    else:
                        logger.warning(f"No stocks found for ranking type {r_type}")
                except Exception as e:
                    logger.error(f"Failed to fetch ranking type {r_type} for {exchange}: {e}")
            
            # De-duplicate
            unique_stocks = {s.symbol: s for s in all_ranking_stocks}.values()
            
            scan_results = []
            for stock in unique_stocks:
                scan_results.append({
                    "銘柄コード": stock.symbol,
                    "銘柄名": stock.symbolname,
                    "終値": stock.currentprice,
                    "騰落率": stock.change_percent,
                    "出来高": stock.volume,
                    "RSI": stock.rsi,
                    "PER": stock.per,
                    "PBR": stock.pbr,
                    "利回り": stock.dividend_yield,
                    "AIスコア": 0.0,
                    "AI要約": f"未実行 (戦略: {strategy})",
                    "ソース": f"Technical-{strategy}"
                })
            
            if scan_results:
                df = pd.DataFrame(scan_results)
                workspace_mgr.save_csv(df, "Market_Scan_Results.csv")
                logger.info(f"Technical scan found {len(scan_results)} stocks and saved to CSV.")
            
            self._save_state(start_time.isoformat(), len(scan_results))
            return {"count": len(scan_results), "time": start_time.isoformat()}
        except Exception as e:
            logger.error(f"Technical scan failed: {e}")
            return {"error": str(e)}
        finally:
            self.is_running = False

    async def run_ai_screening(self, symbols: List[str] = None, scope: str = "scanner"):
        """
        Runs Local LLM on specific symbols OR those listed in Market_Scan_Results.csv / Watchlist.
        """
        if self.is_running:
            return {"error": "AI screening already in progress."}
        
        try:
            target_stocks = []
            
            if symbols:
                # 1. Manual source: provided symbols
                logger.info(f"Targeting {len(symbols)} specifically requested symbols.")
                for s in symbols:
                    target_stocks.append({
                        "銘柄コード": s,
                        "銘柄名": "Unknown",
                        "ソース": "Manual-Selection"
                    })
            elif scope == "watchlist":
                # 2. Watchlist source
                async with AsyncSessionLocal() as session:
                    repo = StockRepository(session)
                    watchlist_symbols = await repo.get_watchlist_symbols()
                    logger.info(f"Targeting {len(watchlist_symbols)} symbols from watchlist.")
                    for s in watchlist_symbols:
                        target_stocks.append({
                            "銘柄コード": s,
                            "銘柄名": "Unknown",
                            "ソース": "Watchlist"
                        })
            else:
                # 3. Scanner results source (default)
                csv_path = workspace_mgr.get_path("market", "Market_Scan_Results.csv")
                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    logger.info(f"Loaded {len(df)} stocks from CSV (Scanner Results).")
                    # Expanded to 100 for more comprehensive screening if requested
                    for _, row in df.head(100).iterrows():
                        target_stocks.append(row.to_dict())
                else:
                    return {"error": "Technical scan results not found. Run SCAN first."}

            
            self.is_running = True
            logger.info(f"Starting Local AI Screening for {len(target_stocks)} items...")
            jst = timezone(timedelta(hours=9))
            
            updated_results = []
            total_processed = 0
            
            self.cancel_requested = False
            for row in target_stocks:
                if self.cancel_requested:
                    logger.info("AI Screening cancelled by user.")
                    break
                
                symbol = str(row["銘柄コード"])
                name = row["銘柄名"]
                source_val = str(row.get("ソース", "short"))
                strategy = source_val.split("-")[-1] if "-" in source_val else "short"
                
                context = f"Ticker: {symbol}, Name: {name}, Price: {row['終値']}, Chg%: {row['騰落率']}, RSI: {row['RSI']}"
                if "PER" in row: context += f", PER: {row['PER']}, PBR: {row['PBR']}, Yield: {row['利回り']}"
                
                screening = await self.local_agent.screen_document(symbol, f"Market Screening: {name}", context, strategy=strategy)
                
                analysis = {
                    "score": 5.0 if screening.get("priority") == "medium" else (7.0 if screening.get("priority") == "high" else 3.0),
                    "summary": screening.get("reason"),
                    "reasoning": screening.get("reason"), # Use reason as reasoning too for local agent
                    "source": "Local LLM (Scan)"
                }
                
                async with AsyncSessionLocal() as session:
                    repo = StockRepository(session)
                    await repo.save_analysis(symbol, analysis, "low")
                
                report_title = f"ScanAI_{symbol}_{name}"
                md_content = f"# 【AIスクリーニング】 {name} ({symbol})\n"
                md_content += f"**分析日時:** {datetime.now(jst).strftime('%Y-%m-%d %H:%M')} (JST)\n"
                md_content += f"**AIスコア:** {analysis['score']}/10\n"
                md_content += f"## 判定理由\n{analysis['summary']}\n\n"
                md_content += f"## データ根拠\n{context}\n"
                workspace_mgr.save_report(report_title, md_content)
                
                row["AIスコア"] = analysis["score"]
                row["AI要約"] = analysis["summary"]
                row["ソース"] = "Local-AI"
                updated_results.append(row)
                total_processed += 1
                await asyncio.sleep(0.01)
                
            if updated_results:
                new_df = pd.DataFrame(updated_results)
                workspace_mgr.save_csv(new_df, "Market_Scan_Results.csv")
                
            last_ai_at = datetime.now(jst).isoformat()
            self._save_state(datetime.now(jst).isoformat(), total_processed, last_ai_at=last_ai_at)
            return {"count": total_processed, "time": last_ai_at}
        except Exception as e:
            logger.error(f"AI screening failed: {e}")
            return {"error": str(e)}
        finally:
            self.is_running = False

    async def run_market_scan(self, thinking_level: str = "standard"):
        """
        Scheduled Full Scan: Technical then AI automatically.
        """
        logger.info("[Scheduled] Starting Full Hybrid Scan...")
        tech_res = await self.run_technical_scan()
        if "error" in tech_res: return
        
        await asyncio.sleep(1)
        await self.run_ai_screening()

if __name__ == "__main__":
    # Test stub
    async def test_run():
        screener = BulkScreener()
        await screener.run_market_scan()
    
    asyncio.run(test_run())
