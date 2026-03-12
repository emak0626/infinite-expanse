import requests
import time
from typing import Dict, Optional
from models import StockData
from config import settings

class KabuApiClient:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.base_url = f"http://{settings.KABU_API_HOST}:{settings.KABU_API_PORT}/kabusapi"
        self.token: Optional[str] = None
        self.last_check: Dict[str, float] = {}
        self.cache: Dict[str, StockData] = {}

    def _get_token(self) -> str:
        """取得したトークンを返し、無効なら再取得する。"""
        if self.token:
            return self.token
        
        url = f"{self.base_url}/token"
        payload = {"APIPassword": settings.KABU_API_PASSWORD}
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                print(f"Token generation failed: {response.status_code} {response.text}")
            response.raise_for_status()
            self.token = response.json().get("Token")
            return self.token
        except Exception as e:
            # print(f"Token generation failed: {e}")
            raise

    def get_board(self, symbol: str) -> StockData:
        current_time = time.time()
        
        if self.mock_mode:
            return self._generate_mock_data(symbol)

        # 実API呼び出し
        try:
            token = self._get_token()
            url = f"{self.base_url}/board/{symbol}@1" # 1 = 東証
            headers = {"X-API-KEY": token}
            
            response = requests.get(url, headers=headers)
            if response.status_code == 401: # Token expired
                self.token = None
                return self.get_board(symbol)
                
            response.raise_for_status()
            res_data = response.json()
            
            try:
                return self._parse_api_response(res_data)
            except Exception as parse_error:
                # Keep error logging in case of schema changes
                print(f"ERROR: Mapping Failed for {symbol}. Data: {res_data}")
                raise parse_error
            
        except Exception as e:
            print(f"API Call Failed for {symbol}: {e}")
            # Fallback to mock in case of emergency/offline
            return self._generate_mock_data(symbol)

    def _parse_api_response(self, data: dict) -> StockData:
        """APIのレスポンスをStockDataモデルに変換。"""
        return StockData(
            symbol=data.get("Symbol", ""),
            symbolname=data.get("SymbolName", ""),
            currentprice=data.get("CurrentPrice"),
            previousclose=data.get("PreviousClose"),
            change_percent=data.get("ChangePreviousClosePer"),
            volume=int(data.get("TradingVolume", 0)) if data.get("TradingVolume") else 0,
            volume_spike=False, # TODO: ロジック実装
            high=data.get("HighPrice"),
            low=data.get("LowPrice"),
            vwap=data.get("VWAP"),
            # 以下、詳細データが必要な場合は別リクエストか、board情報のパースを強化
            per=0.0,
            pbr=0.0,
            dividend_yield=0.0,
            equity_ratio=0.0,
            rsi=50.0,
            deviation_rate=0.0,
            credit_ratio=1.0,
            short_selling_cost=False,
            over_under_ratio=1.0,
            has_large_order=False
        )

    def _generate_mock_data(self, symbol: str) -> StockData:
        """既存のモック生成ロジック（簡略化）"""
        import random
        base_price = random.randint(1000, 10000)
        return StockData(
            symbol=symbol,
            symbolname=f"Mock Corp {symbol}",
            currentprice=float(base_price),
            previousclose=float(base_price),
            change_percent=0.0,
            volume=1000,
            volume_spike=False,
            high=float(base_price),
            low=float(base_price),
            vwap=float(base_price),
            per=15.0,
            pbr=1.0,
            dividend_yield=2.0,
            equity_ratio=50.0,
            rsi=50.0,
            deviation_rate=0.0,
            credit_ratio=1.0,
            short_selling_cost=False,
            over_under_ratio=1.0,
            has_large_order=False
        )
