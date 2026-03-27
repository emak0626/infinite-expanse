import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from screener import Screener
from models import StockData

def test_filter_logic():
    screener = Screener()
    
    # Test cases: Some data missing
    stocks = [
        # 1. PER and PBR missing, but change_percent high (Squeeze/Momentum)
        StockData(symbol="1111", symbolname="HighMomentum", currentprice=1000.0, previousclose=950.0, change_percent=5.2, volume=1000000, is_real_data=True),
        # 2. RSI very low (Rebound)
        StockData(symbol="2222", symbolname="Oversold", currentprice=500.0, previousclose=510.0, change_percent=-2.0, volume=100000, rsi=25.0, is_real_data=True),
        # 3. High dividend yield
        StockData(symbol="3333", symbolname="HighYield", currentprice=2000.0, previousclose=2000.0, change_percent=0.0, volume=50000, dividend_yield=4.5, is_real_data=True),
        # 4. Low PBR but PER missing (Value)
        StockData(symbol="4444", symbolname="DeepValue", currentprice=3000.0, previousclose=3000.0, change_percent=0.0, volume=10000, pbr=0.5, is_real_data=True),
        # 5. Generic stock (Should be in 'all' only)
        StockData(symbol="5555", symbolname="Normal", currentprice=1500.0, previousclose=1500.0, change_percent=0.0, volume=10000, is_real_data=True),
    ]
    
    results = screener.filter_stocks(stocks)
    
    for r in results:
        print(f"Symbol: {r['symbol']}, Name: {r['symbolname']}, Strategies: {r['matched_strategies']}")
        
    # Validations
    assert "short_squeeze" in results[0]["matched_strategies"], "1111 should be short_squeeze due to 5.2% high change"
    assert "rebound" in results[1]["matched_strategies"], "2222 should be rebound due to RSI 25"
    assert "high_dividend" in results[2]["matched_strategies"], "3333 should be high_dividend"
    assert "value_invest" in results[3]["matched_strategies"], "4444 should be value_invest due to PBR 0.5"
    assert len(results[4]["matched_strategies"]) == 0, "5555 should have no specific strategies"
    
    print("\n✅ Filter logic verification passed!")

if __name__ == "__main__":
    try:
        test_filter_logic()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
