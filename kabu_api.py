import random
import time
from typing import Dict, Optional
from models import StockData

class KabuApiClient:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.last_check: Dict[str, float] = {}
        # Simple cache to simulate API limit compliance
        self.cache: Dict[str, StockData] = {}
        self.mock_stocks = ["7203", "9984", "6758", "8035", "5401"] # Toyota, Softbank, Sony, Tokyo Electron, Nippon Steel

    def get_board(self, symbol: str) -> StockData:
        current_time = time.time()
        
        # In a real scenario, use this to limit API calls
        # if symbol in self.last_check and current_time - self.last_check[symbol] < 1.0:
        #     return self.cache[symbol]

        if self.mock_mode:
            data = self._generate_mock_data(symbol)
        else:
            # TODO: Implement real API call here
            data = self._generate_mock_data(symbol) # Fallback for now

        self.cache[symbol] = data
        self.last_check[symbol] = current_time
        return data

    def _generate_mock_data(self, symbol: str) -> StockData:
        """Generates realistic-looking random stock data with fundamentals."""
        base_price = random.randint(1000, 10000)
        change_raw = random.uniform(-0.06, 0.06) # -6% to +6%
        
        # Simulate Trend for Mock
        # Some stocks are crashing (Rebound candidates)
        if random.random() < 0.2: 
            change_raw = random.uniform(-0.15, -0.05)
        
        current_price = base_price * (1 + change_raw)
        change_percent = round(change_raw * 100, 2)
        
        volume = random.randint(10000, 1000000)
        is_spike = random.random() > 0.8 

        # Mock Fundamentals / Technicals
        per = round(random.uniform(5.0, 40.0), 1)
        pbr = round(random.uniform(0.5, 5.0), 2)
        dividend_yield = round(random.uniform(0.0, 6.0), 2)
        equity_ratio = round(random.uniform(20.0, 90.0), 1)
        
        # Technicals correlation with price change
        rsi = random.uniform(20, 80)
        deviation_rate = random.uniform(-15.0, 15.0)
        
        if change_percent < -5:
            rsi = random.uniform(10, 30) # Oversold
            deviation_rate = random.uniform(-20.0, -10.0)
        elif change_percent > 5:
            rsi = random.uniform(70, 90) # Overbought
            deviation_rate = random.uniform(10.0, 20.0)

        # Credit data
        credit_ratio = round(random.uniform(0.1, 10.0), 2)
        short_selling_cost = False
        if credit_ratio < 1.0 and random.random() > 0.7:
             short_selling_cost = True # 逆日歩発生
        
        # Board Info
        over_under_ratio = round(random.uniform(0.5, 2.0), 2)
        has_large_order = random.random() > 0.9

        return StockData(
            symbol=symbol,
            symbolname=f"Mock Corp {symbol}",
            currentprice=round(current_price, 1),
            previousclose=base_price,
            change_percent=change_percent,
            volume=volume * (5 if is_spike else 1),
            volume_spike=is_spike,
            high=round(current_price * 1.01, 1),
            low=round(current_price * 0.99, 1),
            vwap=round(current_price, 1),
            # New Data
            per=per,
            pbr=pbr,
            dividend_yield=dividend_yield,
            equity_ratio=equity_ratio,
            rsi=round(rsi, 1),
            deviation_rate=round(deviation_rate, 2),
            credit_ratio=credit_ratio,
            short_selling_cost=short_selling_cost,
            over_under_ratio=over_under_ratio,
            has_large_order=has_large_order
        )
