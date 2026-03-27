import json
import asyncio
from google import genai
from google.genai import types
from config import settings

class BatchScreener:
    def __init__(self):
        self.client = None
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = settings.GEMINI_MODEL_ID

    async def screen_batch(self, stocks_data: list) -> list:
        """
        Screens a batch of stocks (e.g., 20-50) in a single Gemini request.
        stocks_data: List of dicts containing stock info and recent price trends.
        """
        if not self.client:
            return []

        prompt = self._build_batch_prompt(stocks_data)
        
        try:
            # Respect rate limits: one batch request every X seconds
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            
            results = json.loads(response.text)
            # Ensure it's a list
            if isinstance(results, dict) and "results" in results:
                return results["results"]
            return results
        except Exception as e:
            print(f"Batch Screening Failed: {e}")
            return []

    def _build_batch_prompt(self, stocks_data: list) -> str:
        stocks_json = json.dumps(stocks_data, ensure_ascii=False, indent=2)
        
        return f"""
        あなたはプロのアルゴリズムトレーダー兼マーケットアナリストです。
        提供された銘柄リストを分析し、投資妙味の高い候補を選別・ランク付けしてください。
        
        入力データ (JSON形式):
        {stocks_json}
        
        各銘柄について、トレンドとファンダメンタルズを評価し、以下を決定してください：
        1. スコア: 0-10 (10が最も有望)
        2. タグ: '長期投資', '短期トレード', または '監視'
        3. 詳細コメント: 選定理由を具体的かつ簡潔な日本語で記述してください（最大50文字）。
        
        結果は以下のJSONフォーマットで、リスト形式で返してください。
        スキーマ:
        {{
            "results": [
                {{
                    "symbol": "string",
                    "name": "string",
                    "score": float,
                    "tag": "string",
                    "comment": "string"
                }}
            ]
        }}
        """

if __name__ == "__main__":
    # Quick test logic
    async def test():
        screener = BatchScreener()
        dummy_data = [
            {"symbol": "7203", "name": "Toyota", "latest_price": 2500, "change_5d": "+2.5%"},
            {"symbol": "9984", "name": "SoftBank", "latest_price": 8000, "change_5d": "-1.2%"},
        ]
        results = await screener.screen_batch(dummy_data)
        print(json.dumps(results, indent=2))

    # asyncio.run(test())
