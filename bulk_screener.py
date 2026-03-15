import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any

from kabu_api import KabuApiClient
from repository import StockRepository
from local_agent import LocalAgent
from analyzer_agent import GeminiAgent
from config import settings

logger = logging.getLogger(__name__)

class BulkScreener:
    """
    Automates scanning of the entire market using a hybrid AI pipeline.
    Tier 1: Local LLM (Ollama) filters nodes based on raw data/titles.
    Tier 2: Gemini 2.0 Flash (Free API) performs semantic analysis on filtered candidates.
    """
    
    def __init__(self):
        self.api_client = KabuApiClient()
        self.repo = StockRepository()
        self.local_agent = LocalAgent()
        # Ensure we use Gemini 2.0 Flash for efficiency/free tier
        self.gemini_agent = GeminiAgent(model_id="gemini-2.0-flash-exp") 
        self.is_running = False

    async def run_market_scan(self, thinking_level: str = "standard"):
        """
        Scans all listed stocks in a multi-stage process.
        """
        if self.is_running:
            logger.warning("Scan already in progress.")
            return
        
        self.is_running = True
        logger.info("Starting Full Market Hybrid Scan...")

        try:
            # 1. Get all symbols from Master
            stocks = await self.repo.get_all_stocks()
            logger.info(f"Targeting {len(stocks)} symbols.")

            candidates = []

            # 2. Tier 1: Local Pre-screening
            for stock in stocks:
                # To be efficient, we might fetch board data here
                # but for bulk, we focus on symbols known for movement from kabu_api's full list if available
                # For this implementation, we filter by simple 'LocalAgent' call on the name/ticker first
                # or just process a batch of them.
                
                # Sample logic: If stock is in Master, we check its importance
                screening = await self.local_agent.screen_document(stock.symbol, f"Market Status Check: {stock.name}")
                
                if screening.get("is_important"):
                    logger.info(f"Local Filter -> [PASS] {stock.symbol} ({stock.name}): {screening['reason']}")
                    candidates.append(stock)
                
                # Sleep a tiny bit for local Ollama throttling if needed
                await asyncio.sleep(0.1)

            logger.info(f"Tier 1 completed. {len(candidates)} candidates passed to Gemini 2.0 Flash.")

            # 3. Tier 2: Gemini 2.0 Flash Deep Analysis (Throttled for Free Tier)
            # Free tier: 15 RPM
            batch_size = 14 
            for i in range(0, len(candidates), batch_size):
                batch = candidates[i:i+batch_size]
                tasks = []
                for stock in batch:
                    # Construct context (Price + Recent History)
                    # Note: repository.get_stock_history or similar should be used here
                    # For brevity, we pass a summary context
                    context = f"Company: {stock.name}. Recent master record check."
                    tasks.append(self.gemini_agent.analyze(stock, context, thinking_level=thinking_level))
                
                results = await asyncio.gather(*tasks)
                
                for stock, analysis in zip(batch, results):
                    if "error" not in analysis:
                        await self.repo.save_analysis(stock.symbol, analysis, thinking_level)
                        logger.info(f"Tier 2 -> [SAVED] {stock.symbol} Score: {analysis.get('score')}")
                        # Index to RAG as well
                        await self.gemini_agent.kb.add_knowledge(stock.symbol, analysis.get("reasoning", ""), "Bulk Market Scan")

                if i + batch_size < len(candidates):
                    logger.info("Throttling Gemini API (Free Tier Limit)...")
                    await asyncio.sleep(65) # 1 minute pause between batches to respect 15 RPM

        except Exception as e:
            logger.error(f"Market scan failed: {e}")
        finally:
            self.is_running = False
            logger.info("Full Market Scan Completed.")

if __name__ == "__main__":
    # Test stub
    async def test_run():
        screener = BulkScreener()
        await screener.run_market_scan()
    
    asyncio.run(test_run())
