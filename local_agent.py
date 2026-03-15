import aiohttp
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

class LocalAgent:
    """
    Client for Local LLM (Ollama) to perform pre-screening and filtering.
    """
    BASE_URL = "http://localhost:11434/api"

    def __init__(self, model: str = "llama3.2:3b"):
        self.model = model

    async def screen_document(self, symbol: str, title: str, content_snippet: str = "") -> dict:
        """
        Determines if a document (news or EDINET filing) is important enough for Gemini Pro analysis.
        """
        prompt = f"""
        あなたは、株式市場の「門番（ゲートキーパー）」を務めるAIエージェントです。
        以下の文書を読み、中長期投資の観点から「Gemini 1.5 Proによる詳細分析が必要な重要書類か」を判定してください。

        銘柄: {symbol}
        タイトル: {title}
        内容（一部）: {content_snippet}

        判定基準:
        - 業績に重大な影響を与える（上方/下方修正、買収、提携）。
        - 企業の存続やガバナンスに関わる重大事項。
        - 成長戦略の大きな転換点。
        - 単なる定例の事務的な報告は無視してください。

        出力形式 (JSON):
        {{
            "is_important": boolean,
            "reason": "判断理由（日本語）",
            "priority": "low | medium | high"
        }}
        """

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.BASE_URL}/generate", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return json.loads(data.get("response", "{}"))
                    else:
                        logger.error(f"Ollama API failed with status {resp.status}")
                        return {"is_important": True, "reason": "Error fallback (Local LLM down)", "priority": "high"}
            except Exception as e:
                logger.error(f"Local LLM connection error: {e}")
                # Fallback to important if local LLM is down to avoid missing data
                return {"is_important": True, "reason": "Connection fallback", "priority": "high"}

async def main_test():
    agent = LocalAgent()
    # Test cases
    test_docs = [
        {"symbol": "7203", "title": "通期連結業績予想の修正に関するお知らせ", "snippet": "売上高を従来予想から20%上方修正..."},
        {"symbol": "9984", "title": "非財務情報の開示方針に関する定例報告", "snippet": "サステナビリティ推進の取り組みについて..."},
    ]
    
    for doc in test_docs:
        print(f"Screening: {doc['title']}")
        result = await agent.screen_document(doc['symbol'], doc['title'], doc['snippet'])
        print(f"Result: {result}\n")

if __name__ == "__main__":
    asyncio.run(main_test())
