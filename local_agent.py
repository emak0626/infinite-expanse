import aiohttp
import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

class LocalAgent:
    """
    Client for Local LLM (Ollama) to perform pre-screening and filtering.
    """

    def __init__(self, model_name: str = None):
        self.model = model_name or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.fallback_model = os.getenv("OLLAMA_MODEL_FALLBACK", "llama3.2:3b")
        
        # Priority: Environment variable OLLAMA_BASE_URL
        env_url = os.environ.get("OLLAMA_BASE_URL")
        if env_url:
            self.BASE_URL = env_url.rstrip("/")
            if not self.BASE_URL.endswith("/api"):
                self.BASE_URL += "/api"
        # Intelligent detection
        else:
            # Inside Docker, we almost always want host.docker.internal for Windows Host
            if os.path.exists("/.dockerenv"):
                self.BASE_URL = "http://host.docker.internal:11434/api"
            else:
                self.BASE_URL = "http://localhost:11434/api"
            
        logger.info(f"LocalAgent initialized. Base URL: {self.BASE_URL}, Primary Model: {self.model}")

    async def generate_response(self, prompt: str, format: str = "") -> str:
        """
        Generic method to generate a response from Ollama.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "24h"
        }
        if format:
            payload["format"] = format

        max_retries = 3
        for attempt in range(max_retries):
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.post(f"{self.BASE_URL}/generate", json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("response", "").strip()
                        await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Ollama Error (Attempt {attempt+1}): {e}")
                    await asyncio.sleep(2)
        
        return "【エラー】ローカルAIからの応答取得に失敗しました。"

    async def screen_document(self, symbol: str, title: str, content_snippet: str = "", strategy: str = "short") -> dict:
        """
        Calls local Ollama to analyze data based on investment strategy.
        short: high momentum, volatility.
        long: low risk, high yield, steady growth.
        undervalued: safety margin, deep value.
        """
        strategy_instructions = {
            "short": "短期的な急騰可能性、テクニカルな強さ、出来高増加、モメンタムを重視してください。",
            "long": "長期的な配当利回り、収益の安定性、業界での地位、成長の持続性を重視してください。",
            "undervalued": "PBR/PERの低さ、資産価値、安全域、下げ止まり感を重視してください。"
        }
        instr = strategy_instructions.get(strategy, strategy_instructions["short"])

        prompt = f"""あなたはプロの証券アナリストです。以下の銘柄データを多角的に分析し、投資の優先順位（有望度）を判定してください。

投資戦略: {strategy}
重視ポイント: {instr}
銘柄コード: {symbol}
タイトル: {title}
データ詳細: {content_snippet}

判定基準：
- high: 戦略に強く合致し、テクニカル・ファンダメンタルズ両面で強い買い材料がある
- medium: 合致するが決定打に欠ける、または一時的な過熱感などの懸案事項がある
- low: 戦略に合致しない、またはリスク・不透明感が非常に高い

出力形式（JSONのみ、自然な日本語で回答してください）:
{{
  "priority": "low"|"medium"|"high", 
  "reason": "【詳細分析】分析結果を200〜300文字程度の具体的な日本語で記述してください。根拠となる数値や注目すべき材料、リスク要因を具体的に含めてください。"
}}

余計な装飾や説明は省き、純粋なJSONのみを出力してください。分析結果が途中で切れないよう、簡潔かつ中身の濃い記述を心がけてください。"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": "24h"  # Keep model in memory to avoid loading delays
        }
        
        # Retry configuration
        max_retries = 5
        retry_delay = 3 # initial delay in seconds
        
        for attempt in range(max_retries):
            # Extended timeout for initial load or heavy processing
            timeout = aiohttp.ClientTimeout(total=300)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    logger.info(f"Connecting to Local AI at {self.BASE_URL} (Model: {self.model}, Attempt: {attempt+1}/{max_retries})...")
                    async with session.post(f"{self.BASE_URL}/generate", json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            raw_response = data.get("response", "").strip()
                            
                            try:
                                # 1. Standard parse
                                import json
                                result = json.loads(raw_response)
                                return result
                            except Exception as parse_err:
                                # 2. Extract JSON from potential preamble
                                import re
                                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                                if match:
                                    try:
                                        return json.loads(match.group())
                                    except: pass
                                
                                logger.error(f"Local AI Parse Error: {parse_err}. Raw: {raw_response[:100]}")
                                return {
                                    "priority": "low",
                                    "reason": f"【AI解析エラー】パースに失敗しました。"
                                }
                        elif resp.status in [500, 503, 504]:
                            if attempt >= 1 and self.model != self.fallback_model:
                                logger.warning(f"Ollama consistently returning {resp.status} (Attempt {attempt+1}). Switching to fallback {self.fallback_model}...")
                                orig_model = self.model
                                self.model = self.fallback_model
                                res = await self.screen_document(symbol, title, content_snippet, strategy)
                                self.model = orig_model
                                return res
                            
                            logger.warning(f"Ollama returned {resp.status}. Retrying in {retry_delay}s...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2 # Exponential backoff
                            continue
                        elif resp.status == 404:
                            if self.model != self.fallback_model:
                                logger.warning(f"Model {self.model} not found. Retrying with fallback {self.fallback_model}...")
                                orig_model = self.model
                                self.model = self.fallback_model
                                res = await self.screen_document(symbol, title, content_snippet)
                                self.model = orig_model # Restore for next try
                                return res
                            return { "priority": "low", "reason": f"【モデル未取得】'{self.model}' がありません。" }
                        else:
                            return { "priority": "low", "reason": f"【Ollamaエラー】Status: {resp.status}" }
                except Exception as e:
                    logger.error(f"Local AI Exception for {symbol} (Attempt {attempt+1}): {type(e).__name__}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    
                    error_msg = str(e) if str(e) else type(e).__name__
                    return {
                        "priority": "low", 
                        "reason": f"【接続エラー】Ollama への接続に失敗しました ({error_msg})。"
                    }
        
        return { "priority": "low", "reason": "【エラー】最大試行回数を超えました。" }

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
