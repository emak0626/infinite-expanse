from typing import List, Dict
from models import StockData
from strategy_config import DEFAULT_STRATEGIES

class Screener:
    def __init__(self):
        # In a real app, load from DB/Config file. Using defaults for now.
        self.strategies = DEFAULT_STRATEGIES

    def filter_stocks(self, stocks: List[StockData], active_strategies: List[str] = None) -> List[Dict]:
        """
        Applies active strategies to the stock list.
        Returns a list of results with 'matched_strategies' meta-data.
        """
        results = []
        
        for stock in stocks:
            matched = []
            
            # --- 1. Value Strategy (割安株) ---
            # Criteria: PER <= 15 OR PBR <= 1.0
            params = self.strategies["value_invest"]["params"]
            has_value_data = stock.per is not None or stock.pbr is not None
            
            if has_value_data:
                # Be lenient: if either PER or PBR meets the criteria, consider it.
                is_per_ok = stock.per is not None and stock.per <= params.get("per_max", 15.0)
                is_pbr_ok = stock.pbr is not None and stock.pbr <= params.get("pbr_max", 1.0)
                if is_per_ok or is_pbr_ok:
                    matched.append("value_invest")
            elif not stock.is_real_data:
                # Mock fallback
                if stock.change_percent >= 0: matched.append("value_invest")

            # --- 2. High Dividend Strategy (高配当) ---
            # Criteria: Yield >= 3.0%
            params = self.strategies["high_dividend"]["params"]
            if stock.dividend_yield is not None:
                if stock.dividend_yield >= params.get("yield_min", 3.0):
                    matched.append("high_dividend")
            elif not stock.is_real_data:
                # Mock fallback
                if stock.change_percent < 0: matched.append("high_dividend")

            # --- 3. Short Squeeze Strategy (モメンタム) ---
            # Criteria: Squeeze params OR high volume ratio OR positive change (loosened)
            params = self.strategies["short_squeeze"]["params"]
            is_momentum = False
            
            # Lowered from 3.0 to 1.5 to be more inclusive
            if stock.change_percent is not None and stock.change_percent >= 1.5:
                is_momentum = True
            if stock.credit_ratio is not None and stock.credit_ratio <= params.get("credit_ratio_max", 1.0):
                is_momentum = True
            if stock.volume_spike:
                is_momentum = True
            
            if is_momentum:
                matched.append("short_squeeze")
            elif not stock.is_real_data and stock.volume > 500000:
                matched.append("short_squeeze")

            # --- 4. Rebound Strategy (反発期待) ---
            # Criteria: RSI <= 30 OR heavy drop (loosened)
            params = self.strategies["rebound"]["params"]
            is_rebound = False
            if stock.rsi is not None and stock.rsi <= params.get("rsi_max", 35.0): # 30->35
                is_rebound = True
            # Lowered from -3.0 to -1.5
            if stock.change_percent is not None and stock.change_percent <= -1.5:
                is_rebound = True
                
            if is_rebound:
                matched.append("rebound")
            elif not stock.is_real_data and stock.change_percent <= -2.0:
                matched.append("rebound")
            
            # Always add to results, with tags
            stock_dict = stock.dict()
            stock_dict["matched_strategies"] = matched
            
            # Debugging: Only print if it's watchlist data to avoid flooding logs
            if matched or stock.symbol in ["7203", "9984", "6758"]:
                print(f"[SCREENER DEBUG] {stock.symbol} ({stock.symbolname}): Change={stock.change_percent}%, RSI={stock.rsi}, PBR={stock.pbr}, Matches={matched}")
            
            results.append(stock_dict)
                
        return results

    def get_strategy_config(self):
        return self.strategies
