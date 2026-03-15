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
from database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class BulkScreener:
    """
    Automates scanning of the entire market using a hybrid AI pipeline.
    Tier 1: Local LLM (Ollama) filters nodes based on raw data/titles.
    Tier 2: Gemini 2.0 Flash (Free API) performs semantic analysis on filtered candidates.
    """
    
    def __init__(self):
        self.api_client = KabuApiClient()
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
            async with AsyncSessionLocal() as session:
                repo = StockRepository(session)
                # 1. Get all symbols from Master
                stocks = await repo.get_all_stocks()
                logger.info(f"Targeting {len(stocks)} symbols.")

            candidates = []

            # 2. Tier 1: Local Pre-screening (Favor Local LLM)
            for stock in stocks:
                # Optimized prompt to be even stricter to save Gemini quota
                context = f"Company: {stock.name}. Recent performance check."
                screening = await self.local_agent.screen_document(stock.symbol, f"Market Status Check: {stock.name}", context)
                
                # Only pass 'high' priority to Gemini, handle others locally or watch
                if screening.get("is_important") and screening.get("priority") == "high":
                    logger.info(f"Local Filter -> [PASS to Gemini] {stock.symbol} ({stock.name}): {screening['reason']}")
                    candidates.append(stock)
                elif screening.get("is_important"):
                    # Save a medium-confidence screening directly using local analysis
                    logger.info(f"Local Filter -> [LOCAL SAVE] {stock.symbol} ({stock.name})")
                    analysis = {
                        "score": 5.0 if screening.get("priority") == "medium" else 3.0,
                        "summary": screening.get("reason"),
                        "reasoning": f"Local LLM determined moderate importance: {screening['reason']}",
                        "persona_views": {"value": "Local screening pass", "risk": "Moderate priority"},
                        "source": "Local LLM"
                    }
                    async with AsyncSessionLocal() as session:
                        repo = StockRepository(session)
                        await repo.save_analysis(stock.symbol, analysis, thinking_level)
                
                await asyncio.sleep(0.05)

            logger.info(f"Tier 1 completed. {len(candidates)} high-priority candidates passed to Gemini.")

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
                        async with AsyncSessionLocal() as session:
                            repo = StockRepository(session)
                            await repo.save_analysis(stock.symbol, analysis, thinking_level)
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
