from google import genai
from google.genai import types
from config import settings
from models_db import AnalysisReport, StockMaster
import json
import asyncio

class GeminiAgent:
    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            print("Warning: GEMINI_API_KEY not found. AI analysis will be unavailable.")
        
        self.model_id = settings.GEMINI_MODEL_ID

    async def analyze(self, stock: StockMaster, context_data: str, thinking_level: str = "standard") -> dict:
        """
        Analyzes stock data and returns a structured JSON report.
        """
        if not self.client:
            return {"error": "Gemini API key not configured", "symbol": stock.symbol, "score": 0}

        prompt = self._build_prompt(stock.symbol, stock.name, context_data, thinking_level)
        
        try:
            # Run in executor to avoid blocking async loop
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            
            return json.loads(response.text)
        except Exception as e:
            print(f"Gemini Analysis Failed: {e}")
            return {
                "error": str(e),
                "symbol": stock.symbol,
                "score": 0
            }

    def _build_prompt(self, symbol: str, name: str, context: str, level: str) -> str:
        base_instruction = f"""
        You are an AI Investment Analyst acting as a 'co-pilot' for a professional trader.
        Analyze the stock {name} ({symbol}) based on the provided technical and fundamental data.
        
        Focus on identifying short-term momentum shifts and supply-demand imbalances.
        
        Output format: JSON
        Schema:
        {{
            "summary": "Key takeaways (1 sentence)",
            "score": float (0-10, 10 is strong buy),
            "sentiment": "Bullish | Neutral | Bearish",
            "reasoning": "Detailed markdown explanation highlighting technical and fundamental confluence",
            "risks": ["Specific risk 1", "Specific risk 2"],
            "opportunities": ["Specific opportunity 1", "Specific opportunity 2"]
        }}
        """

        if level == "high":
            return f"""
            {base_instruction}
            
            [THINKING MARKER: HIGH]
            Perform a deep-dive analysis.
            1. Evaluate the synergy between technical indicators (RSI, Moving Average Deviation) and market structure (Board Balance, Credit Ratio).
            2. Infer potential institutional behavior if 'Large Orders' are detected.
            3. Consider the impact of 'Short Squeeze' potential if credit ratios are low or negative.
            4. Provide a 'Non-Consensus' view - what is the market missing?
            
            Context Data (Historical Prices & Indicators):
            {context}
            """
        else:
            return f"""
            {base_instruction}
            
            [THINKING MARKER: STANDARD]
            Focus on immediate trend and supply-demand balance.
            
            Context Data (Historical Prices & Indicators):
            {context}
            """
