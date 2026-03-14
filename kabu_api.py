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
        self.host_header = f"localhost:{settings.KABU_API_PORT}"

    def _get_token(self) -> str:
        """取得したトークンを返し、無効なら再取得する。"""
        if self.token:
            return self.token
        
        url = f"{self.base_url}/token"
        payload = {"APIPassword": settings.KABU_API_PASSWORD}
        
        headers = {
            "Content-Type": "application/json",
            "Host": self.host_header
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                print(f"Token generation failed: {response.status_code} {response.text}")
            response.raise_for_status()
            self.token = response.json().get("Token")
            return self.token
        except Exception as e:
            # print(f"Token generation failed: {e}")
            raise

    def get_symbol_info(self, symbol: str) -> dict:
        """銘柄詳細情報（PER/PBR/信用倍率等）を取得。"""
        if self.mock_mode:
            return {}
        try:
            token = self._get_token()
            url = f"{self.base_url}/symbol/{symbol}@1"
            headers = {"X-API-KEY": token, "Host": self.host_header}
            response = requests.get(url, headers=headers)
            return response.json() if response.status_code == 200 else {}
        except:
            return {}

    def get_board(self, symbol: str) -> StockData:
        if self.mock_mode:
            return self._generate_mock_data(symbol)

        # 実API呼び出し
        time.sleep(0.2) # Rate limit avoidance
        try:
            token = self._get_token()
            url = f"{self.base_url}/board/{symbol}@1"
            headers = {"X-API-KEY": token, "Host": self.host_header}
            
            response = requests.get(url, headers=headers)
            if response.status_code == 401:
                self.token = None
                return self.get_board(symbol)
                
            response.raise_for_status()
            res_data = response.json()
            
            # 詳細情報（PER/PBR等）を結合
            symbol_info = self.get_symbol_info(symbol)
            
            return self._parse_api_response(res_data, symbol_info)
        except Exception as e:
            print(f"API Call Failed for {symbol}: {e}")
            return self._generate_mock_data(symbol)

    def get_ranking(self, type: str = "1") -> list[StockData]:
        """
        指定されたタイプのランキングを取得。
        1: 値上がり率, 2: 値下がり率, 3: 出来高, 4: 出来高急増
        """
        if self.mock_mode:
            # モック時はウォッチリストを返す
            return [self._generate_mock_data(s) for s in settings.WATCHLIST]

        try:
            token = self._get_token()
            url = f"{self.base_url}/ranking?type={type}"
            headers = {"X-API-KEY": token, "Host": self.host_header}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            ranking_data = response.json().get("Ranking", [])
            
            results = []
            for item in ranking_data[:30]: # 上位30銘柄
                symbol = item.get("Symbol")
                # ランキングデータには詳細がないため、boardとsymbol_infoを補完（時間はかかるが確実）
                try:
                    data = self.get_board(symbol)
                    results.append(data)
                except:
                    continue
            return results
        except Exception as e:
            print(f"Ranking Fetch Failed: {e}")
            return []

    def _parse_api_response(self, data: dict, info: dict = None) -> StockData:
        """APIのレスポンスをStockDataモデルに変換。"""
        if info is None: info = {}
        
        return StockData(
            symbol=data.get("Symbol", ""),
            symbolname=data.get("SymbolName", ""),
            currentprice=data.get("CurrentPrice"),
            previousclose=data.get("PreviousClose"),
            change_percent=data.get("ChangePreviousClosePer"),
            volume=int(data.get("TradingVolume", 0)) if data.get("TradingVolume") else 0,
            volume_spike=False,
            high=data.get("HighPrice"),
            low=data.get("LowPrice"),
            vwap=data.get("VWAP"),
            # symbol info から取得
            per=info.get("PER"),
            pbr=info.get("PBR"),
            dividend_yield=info.get("DividendYield"),
            equity_ratio=info.get("EquityRatio"),
            rsi=50.0, # board/symbolにはないため別途計算が必要だが一旦デフォルト
            deviation_rate=0.0,
            credit_ratio=info.get("MarginBuyRatio"),
            short_selling_cost=False,
            over_under_ratio=1.0,
            has_large_order=False
        )

    def _generate_mock_data(self, symbol: str) -> StockData:
        """生成するモックデータを銘柄ごとにユニークにする。"""
        import random
        import hashlib
        
        # 銘柄コードをシードにして値を固定しつつ、銘柄ごとに変える
        seed = int(hashlib.md5(symbol.encode()).hexdigest(), 16) % 10000
        random.seed(seed)
        
        base_price = random.randint(1000, 10000)
        change = random.uniform(-5.0, 5.0)
        rsi = 30 + (seed % 40) + random.uniform(-5, 5) # 25-75の範囲でバラつかせる
        
        return StockData(
            symbol=symbol,
            symbolname=f"Mock Corp {symbol}",
            currentprice=float(base_price),
            previousclose=float(base_price / (1 + change/100)),
            change_percent=round(change, 2),
            volume=random.randint(10000, 1000000),
            volume_spike=random.random() > 0.8,
            high=float(base_price * 1.02),
            low=float(base_price * 0.98),
            vwap=float(base_price * 0.99),
            per=round(10 + random.random() * 20, 1),
            pbr=round(0.5 + random.random() * 3, 2),
            dividend_yield=round(random.random() * 5, 2),
            equity_ratio=round(20 + random.random() * 60, 1),
            rsi=round(rsi, 1),
            deviation_rate=round(random.uniform(-10, 10), 1),
            credit_ratio=round(0.5 + random.random() * 5, 2),
            short_selling_cost=random.random() > 0.9,
            over_under_ratio=round(0.5 + random.random() * 1.5, 2),
            has_large_order=random.random() > 0.7
        )
