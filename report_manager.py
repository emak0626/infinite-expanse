import os
import datetime
from models import StockData

# Report Storage Directory
REPORT_DIR = "trade_reports"

def _ensure_dir(date_str: str):
    """Ensures the directory for the specific date exists."""
    path = os.path.join(REPORT_DIR, date_str)
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def save_report(stock: StockData, context_type: str = "manual") -> str:
    """
    Generates and saves a markdown report for the stock.
    Returns the absolute path of the saved file.
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H:%M:%S")
    
    # Directory Setup
    save_dir = _ensure_dir(date_str)
    filename = f"{stock.symbol}_report.md"
    filepath = os.path.join(save_dir, filename)
    
    # Context Logic (Append mode if exists to keep history of the day)
    mode = "a" if os.path.exists(filepath) else "w"
    
    # Calculate derived metrics
    trend = "UP" if stock.change_percent > 0 else "DOWN"
    balance_ratio = 0.0
    if stock.over_under_ratio:
        balance_ratio = stock.over_under_ratio
    
    short_squeeze_alert = "【⚠️ 逆日歩発生中】" if stock.short_selling_cost else ""
    
    # Markdown Content Construction (User's Draft Base)
    content = f"""
# 銘柄分析レポート: {stock.symbolname} ({stock.symbol})
**日時**: {now.strftime('%Y-%m-%d')} {time_str} | **トリガー**: {context_type}

## 【基本指標】
- 現在値: {stock.currentprice}円 (前日比: {stock.change_percent}% {trend})
- 出来高: {stock.volume}株 {"(🔥急増中)" if stock.volume_spike else ""}
- VWAP: {stock.vwap}円
- PER: {stock.per if stock.per else 'N/A'} / PBR: {stock.pbr if stock.pbr else 'N/A'}

## 【需給・テクニカル】
- 板バランス(Over/Under): {balance_ratio}倍 (1.0超は上値重い)
- 信用倍率: {stock.credit_ratio}倍 {short_squeeze_alert}
- RSI(14): {stock.rsi}
- 乖離率: {stock.deviation_rate}%

## 【AIへの問いかけ (Context)】
この銘柄は現在、VWAPに対して{"上" if stock.currentprice > stock.vwap else "下"}に位置しています。
直近の板の厚み({balance_ratio}倍)と、信用需給({stock.credit_ratio}倍)を考慮し、
**数分〜数十分スパンでの反発（または続伸）の可能性**を分析してください。
また、下値のリスク要因があれば具体的に指摘してください。

---
"""
    
    with open(filepath, mode, encoding="utf-8") as f:
        f.write(content)
        
    print(f">>> Report saved to {filepath}")
    return filepath
