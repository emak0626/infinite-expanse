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
        You are an expert Algorithmic Trader and Market Analyst.
        Your task is to perform an initial screening of the following stocks to identify high-potential candidates.
        
        Input Data (JSON List):
        {stocks_json}
        
        For each stock, evaluate the trend and determine:
        1. Score: 0-10 (10 is high potential)
        2. Tag: 'Long-term', 'Short-term', or 'Watch'
        3. Simple Comment: Reason for the score (max 15 words)
        
        Return the results in JSON format as a list of objects.
        Schema:
        {{
            "results": [
                {{
                    "symbol": "string",
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
