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
        self._load_stock_names()

    def _load_stock_names(self):
        self.stock_name_map = {}
        try:
            import os
            import json
            mapping_path = os.path.join(os.path.dirname(__file__), "stock_names.json")
            if os.path.exists(mapping_path):
                with open(mapping_path, "r", encoding="utf-8") as f:
                    self.stock_name_map = json.load(f)
            else:
                # Create empty if not exists
                with open(mapping_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
        except Exception as e:
            print(f"Error loading stock_names.json: {e}")

    def _save_stock_name(self, symbol: str, name: str):
        """Dynamically learns and persists a stock name."""
        if not name or name == "Unknown" or name.startswith("銘柄") or name == symbol:
            return
        
        # Guard against error messages
        invalid_keywords = ["[Local AI Fallback]", "【接続エラー】", "【モデル未取得】", "【Ollamaエラー】"]
        if any(k in name for k in invalid_keywords):
            return

        if self.stock_name_map.get(symbol) == name:
            return

        self.stock_name_map[symbol] = name
        try:
            import os
            import json
            mapping_path = os.path.join(os.path.dirname(__file__), "stock_names.json")
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(self.stock_name_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to persist stock name {symbol}: {e}")

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

    def get_ranking(self, type: str = "1", exchange: str = "ALL") -> list[StockData]:
        """
        指定されたタイプのランキングを取得。
        1: 値上がり率, 2: 値下がり率, 3: 出来高, 4: 出来高急増
        13: 低PER, 14: 低PBR, 15: 高配当利回り
        exchange: ALL, ALLP (Prime), ALLS (Standard), ALLG (Growth)
        """
        if self.mock_mode:
            self._current_type = type 
            import random
            
            all_codes = list(self.stock_name_map.keys())
            if not all_codes:
                # フェールセーフ
                all_codes = ["7203", "9984", "6758", "8035", "5401", "9101"]
                
            # モック時は実在する名簿からランダムに50銘柄（ALLは100銘柄）抽出してシミュレート
            sample_size = 50 if exchange in ["G", "S", "P"] else 100
            scan_pool = random.sample(all_codes, min(sample_size, len(all_codes)))
            
            return [self._generate_mock_data(s) for s in scan_pool]

        try:
            token = self._get_token()
            market_suffix = f"&exchange={exchange}" if exchange != "ALL" else ""
            url = f"{self.base_url}/ranking?type={type}{market_suffix}"
            headers = {"X-API-KEY": token, "Host": self.host_header}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            ranking_data = response.json().get("Ranking", [])
            
            results = []
            for item in ranking_data[:50]: # より広く取得（上位50銘柄）
                symbol = item.get("Symbol")
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
        
        symbol = data.get("Symbol", "")
        symbol_name = data.get("SymbolName", "")
        
        # 1. Try to get name from detailed symbol info if board was lacking it
        if info and (not symbol_name or symbol_name == "Unknown"):
            info_name = info.get("SymbolName")
            if info_name and info_name != "Unknown":
                symbol_name = info_name

        # 2. 強制的にローカルの綺麗な名簿（stock_names.json）を優先する
        if symbol in self.stock_name_map:
            symbol_name = self.stock_name_map[symbol]
        else:
            # 辞書にない場合はフォールバック
            is_invalid = not symbol_name or symbol_name == "Unknown" or str(symbol_name).isdigit() or symbol_name == symbol
            if is_invalid:
                symbol_name = f"銘柄 {symbol}"
            else:
                # APIのレスポンスに自身のコードが含まれている場合は除去
                symbol_name = symbol_name.replace(symbol, "").strip()
                # 3. Valid name found! Learn it.
                self._save_stock_name(symbol, symbol_name)

        return StockData(
            symbol=symbol,
            symbolname=symbol_name,
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
            rsi=None, # board/symbolにはないため別途取得が必要
            deviation_rate=0.0,
            credit_ratio=info.get("MarginBuyRatio"),
            short_selling_cost=False,
            over_under_ratio=1.0,
            has_large_order=False,
            is_real_data=True
        )

    def _get_fallback_name(self, symbol: str) -> str:
        return self.stock_name_map.get(symbol, f"銘柄 {symbol}")

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
        
        # 名前マップから取得、なければデフォルト名
        symbol_name = self._get_fallback_name(symbol)

        # Adjust mock data based on ranking type if needed
        # (For simplicity, we just keep the randomized values, but we could bias them here)
        return StockData(
            symbol=symbol,
            symbolname=symbol_name,
            currentprice=float(base_price),
            previousclose=float(base_price / (1 + change/100)),
            change_percent=round(change, 2),
            volume=random.randint(10000, 1000000),
            volume_spike=random.random() > 0.8,
            high=float(base_price * 1.02),
            low=float(base_price * 0.98),
            vwap=float(base_price * 0.99),
            per=round(2 + random.random() * 8, 1) if "13" in str(getattr(self, '_current_type', '')) else round(10 + random.random() * 20, 1),
            pbr=round(0.3 + random.random() * 0.7, 2) if "14" in str(getattr(self, '_current_type', '')) else round(0.5 + random.random() * 3, 2),
            dividend_yield=round(3 + random.random() * 5, 2) if "15" in str(getattr(self, '_current_type', '')) else round(random.random() * 5, 2),
            equity_ratio=round(20 + random.random() * 60, 1),
            rsi=round(rsi, 1),
            deviation_rate=round(random.uniform(-10, 10), 1),
            credit_ratio=round(0.5 + random.random() * 5, 2),
            short_selling_cost=random.random() > 0.9,
            over_under_ratio=round(0.5 + random.random() * 1.5, 2),
            has_large_order=random.random() > 0.7,
            is_real_data=False
        )
