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
            
            # 1. Value Strategy
            params = self.strategies["value_invest"]["params"]
            if (stock.per is not None and stock.per <= params["per_max"] and
                stock.pbr is not None and stock.pbr <= params["pbr_max"]):
                matched.append("value_invest")

            # 2. High Dividend Strategy
            params = self.strategies["high_dividend"]["params"]
            if (stock.dividend_yield is not None and stock.dividend_yield >= params["yield_min"] and
                stock.equity_ratio is not None and stock.equity_ratio >= params["equity_ratio_min"]):
                matched.append("high_dividend")

            # 3. Short Squeeze Strategy
            params = self.strategies["short_squeeze"]["params"]
            if (stock.credit_ratio is not None and stock.credit_ratio <= params["credit_ratio_max"] and
                stock.short_selling_cost is True): # 逆日歩発生中
                matched.append("short_squeeze")

            # 4. Rebound Strategy
            params = self.strategies["rebound"]["params"]
            if (stock.rsi is not None and stock.rsi <= params["rsi_max"]):
                matched.append("rebound")
            
            # If any strategy matched, add to results with tags
            if matched:
                stock_dict = stock.dict()
                stock_dict["matched_strategies"] = matched
                results.append(stock_dict)
                
        return results

    def get_strategy_config(self):
        return self.strategies
