from google import genai
from google.genai import types
from config import settings
from knowledge_base import KnowledgeBase
from models_db import AnalysisReport, StockMaster
import json
import asyncio
from typing import Dict, Any

class GeminiAgent:
    def __init__(self, model_id: str = None):
        self.client = None
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            print("Warning: GEMINI_API_KEY not found. AI analysis will be unavailable.")
        
        self.model_id = model_id or settings.GEMINI_MODEL_ID
        self.kb = KnowledgeBase()

    async def analyze(self, stock: StockMaster, context_data: str, thinking_level: str = "standard") -> dict:
        """
        Analyzes stock data and returns a structured JSON report using multi-persona reasoning and RAG.
        """
        if not self.client:
            return {"error": "Gemini API key not configured", "symbol": stock.symbol, "score": 0}

        # Phase 2: Long-term Memory Retrieval
        semantic_context = await self.kb.search_relevant_context(stock.symbol, "最近の業績、リスク、特筆すべき開示事項について")
        full_context = f"{context_data}\n\n[LONG-TERM MEMORY / HISTORICAL CONTEXT]\n{semantic_context}" if semantic_context else context_data

        prompt = self._build_prompt(stock.symbol, stock.name, full_context, thinking_level)
        
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
        あなたは、プロの投資家チームを統括するリード・アナリストです。
        以下の銘柄 {name} ({symbol}) について、提供されたデータ（最新の価格データおよび過去の文脈）に基づき、複数の専門的視点から分析を行ってください。
        
        以下の3つのペルソナによる合議制（推論プロセス）をシミュレートしてください：
        1. **バリュー投資家**: 資産価値、配当、キャッシュフロー、PER/PBR等の指標から「安全域」を評価する。
        2. **デビルズ・アドボケート（逆説家）**: 投資仮説に対するリスク、地政学、需給の悪化、競合の脅威を強調する。
        3. **テクニカル・ストラテジスト**: RSI、乖離率、板情報、出来高の変化から、価格変動のエネルギーと方向性を判定する。

        最終的に、これら三者の意見を統合し、バイアスのない客観的な評価を出力してください。

        Output format: JSON
        Schema:
        {{
            "summary": "Key takeaways (1 sentence in Japanese)",
            "score": float (0-10, 10 is strong buy),
            "sentiment": "Bullish | Neutral | Bearish",
            "reasoning": "Markdown explanation integrating multi-persona discussion (in Japanese)",
            "persona_views": {{
                "value": "Value investor's perspective",
                "risk": "Devil's advocate's perspective",
                "technical": "Strategist's perspective"
            }},
            "risks": ["Specific risk 1", "Specific risk 2"],
            "opportunities": ["Specific opportunity 1", "Specific opportunity 2"],
            "catalysts": ["Potential spark for price movement"]
        }}
        """

        if level == "high":
            return f"""
            {base_instruction}
            
            [THINKING MODE: DEEP MULTI-PERSONA]
            - バリュー投資家は、現在のバリュエーションが歴史的水準と比べてどうあるかを指摘してください。
            - デビルズ・アドボケートは、最も悲観的なシナリオ（倒産や暴落のリスク）をあえて強調してください。
            - ストラテジストは、現在の出来高急増が「買い」か「投げ」かを板情報から推測してください。
            
            Context Data:
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
