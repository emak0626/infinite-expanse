from models import StockData

def generate_analysis_prompt(stock: StockData) -> str:
    """Generates a detailed prompt for Gemini analysis."""
    trend = "UP" if stock.change_percent > 0 else "DOWN"
    short_sq_alert = "【逆日歩発生中】" if stock.short_selling_cost else ""
    
    return f"""
# 株価分析依頼: {stock.symbolname} ({stock.symbol})

## 1. 市場データ
- 現在値: {stock.currentprice}円 ({stock.change_percent}% {trend})
- 出来高: {stock.volume}株 {"(🔥急増中)" if stock.volume_spike else ""}
- VWAP: {stock.vwap}円
- PER: {stock.per if stock.per else 'N/A'}倍 / PBR: {stock.pbr if stock.pbr else 'N/A'}倍
- 配当利回り: {stock.dividend_yield if stock.dividend_yield else 'N/A'}% / 自己資本比率: {stock.equity_ratio if stock.equity_ratio else 'N/A'}%

## 2. 需給・板情報
- 信用倍率: {stock.credit_ratio}倍 {short_sq_alert}
- 板バランス(Over/Under): {stock.over_under_ratio}倍 (1.0超は上値重い)
- 大口注文: {"あり" if stock.has_large_order else "なし"}

## 3. テクニカル
- RSI(14): {stock.rsi}
- 乖離率(25日線想定): {stock.deviation_rate}%

## 4. コンテキスト
VWAPに対して{"上" if stock.currentprice > (stock.vwap or 0) else "下"}に位置しています。

## 依頼内容
あなたはプロの投資アナリストおよびデイトレーダーとして、提供されたデータに基づき以下の分析を行ってください：
1. **需給バランスの判定**: 信用取り組み（信用倍率、逆日歩）と板バランスから、現在の需給の「健全性」と「上値の重さ/軽さ」を評価してください。
2. **期待される値動き**: RSIや乖離率、VWAPとの位置関係から、数分〜数十分のスパンで「反発/続伸」の可能性が高いか判断してください。
3. **具体的な戦略**: 具体的な押し目買いや戻り売りの水準、あるいは見送りすべき状況かを示唆してください。
4. **リスク要因**: 信用需給の悪化やテクニカル的な過熱感など、注意すべき下値リスクを具体的に指摘してください。

※簡潔なMarkdown形式で出力してください。
"""

def generate_bulk_analysis_prompt(stocks: list[StockData]) -> str:
    """Generates a prompt for bulk stock screening and ranking."""
    stock_rows = []
    for s in stocks:
        row = f"| {s.symbol} | {s.symbolname} | {s.currentprice} | {s.change_percent}% | {s.per or 'N/A'} | {s.pbr or 'N/A'} | {s.rsi or 'N/A'} | {s.credit_ratio or 'N/A'} |"
        stock_rows.append(row)
    
    table_header = "| 銘柄コード | 銘柄名 | 現在値 | 前日比 | PER | PBR | RSI | 信用倍率 |\n|---|---|---|---|---|---|---|---|"
    stock_table = "\n".join(stock_rows)
    
    return f"""
# 大量銘柄の一括スクリーニング依頼

以下の銘柄リスト（計{len(stocks)}銘柄）のマーケットデータを分析し、テクニカル・ファンダメンタルの両面から「今、最も投資妙味がある銘柄」を**上位5位まで**選別・ランク付けしてください。

## 銘柄データリスト
{table_header}
{stock_table}

## 分析の指針
1. **総合評価**: ボラティリティ、需給（信用倍率）、割安性（PER/PBR）、過熱感（RSI）を総合的に判断してください。
2. **短期的な期待値**: 単なる値上がり率ではなく、需給の軽さやテクニカル的な反発の兆しなどを重視してください。
3. **リスクの指摘**: 上位に選んだ銘柄について、注意すべき下値リスクも簡潔に併記してください。

## 出力形式
- 1位〜5位までのランキング形式
- 各銘柄について「選定理由」と「短期的な目標/注意点」をMarkdown形式で簡潔に出力してください。
"""

def generate_quick_alert(stock: StockData) -> str:
    """Generates a short alert message."""
    reason = "急騰/急落" if abs(stock.change_percent) > 3 else "出来高急増"
    return f"【{stock.symbolname}】{reason}検知！ 現在:{stock.currentprice}円 ({stock.change_percent}%)"
