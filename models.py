from pydantic import BaseModel
from typing import Optional, List

class StockData(BaseModel):
    symbol: str
    symbolname: str
    currentprice: float
    previousclose: float
    change_percent: float
    volume: int
    volume_spike: bool = False  # Alert Flag
    
    # Additional fields useful for analysis
    high: Optional[float] = None
    low: Optional[float] = None
    vwap: Optional[float] = None
    
    # Fundamentals
    per: Optional[float] = None
    pbr: Optional[float] = None
    dividend_yield: Optional[float] = None
    equity_ratio: Optional[float] = None
    
    # Technicals / Supply-Demand
    rsi: Optional[float] = None
    deviation_rate: Optional[float] = None # 移動平均乖離率
    credit_ratio: Optional[float] = None # 信用倍率
    short_selling_cost: bool = False # 逆日歩発生中か
    over_under_ratio: Optional[float] = None # 板の需給 (Over ÷ Under)
    has_large_order: bool = False # 大口約定フラグ
    
    # AI Results
    ai_score: Optional[float] = None
    ai_sentiment: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_thinking: Optional[str] = None # low, standard, high
    
    is_real_data: bool = True # Flag to indicate if data is from live API or DB fallback
    is_watched: bool = False # Flag for UI to show heart icon

class AnalysisRequest(BaseModel):
    symbol: str

class ManualReportRequest(BaseModel):
    content: str
    score: float
