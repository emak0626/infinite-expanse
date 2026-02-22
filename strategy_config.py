from typing import Dict, Any

# Default Screening Parameters
DEFAULT_STRATEGIES = {
    "value_invest": {
        "name": "割安株発掘 (Value)",
        "description": "企業の本来の価値より安く放置されている銘柄",
        "params": {
            "per_max": 15.0,
            "pbr_max": 1.0,
            "psr_max": 1.1,
        },
        "guides": {
            "per_max": "目安: 15倍以下 (市場平均より割安)",
            "pbr_max": "目安: 1倍以下 (解散価値割れ)",
        },
    },
    "high_dividend": {
        "name": "高配当・優良株 (Yield)",
        "description": "安定した配当と財務健全性を持つ銘柄",
        "params": {
            "yield_min": 3.0,
            "payout_ratio_max": 50.0,
            "equity_ratio_min": 40.0,
        },
        "guides": {
            "yield_min": "目安: 3%以上 (銀行利息より圧倒的)",
            "equity_ratio_min": "目安: 40%以上 (倒産リスク低)",
        },
    },
    "short_squeeze": {
        "name": "需給・踏み上げ (Squeeze)",
        "description": "売り残が多く、買い戻しによる急騰が狙える銘柄",
        "params": {
            "credit_ratio_max": 1.0,
        },
        "guides": {
            "credit_ratio_max": "目安: 1倍未満 (売り長状態)",
        },
    },
    "rebound": {
        "name": "リバウンド (Rebound)",
        "description": "売られすぎからの自律反発狙い",
        "params": {
            "rsi_max": 30.0,
            "deviation_min": -10.0, # 乖離率
        },
        "guides": {
            "rsi_max": "目安: 30%以下 (売られすぎ)",
        },
    }
}
