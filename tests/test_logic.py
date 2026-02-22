import pytest
from models import StockData
from screener import Screener

# Mock Data fixture
@pytest.fixture
def mock_stocks():
    return [
        StockData(
            symbol="1111", symbolname="Value Corp",
            currentprice=1000, previousclose=1000, change_percent=0, volume=1000,
            per=10.0, pbr=0.8, dividend_yield=2.0, equity_ratio=50.0, # Value Stock
            rsi=50, deviation_rate=0
        ),
        StockData(
            symbol="2222", symbolname="Yield Corp",
            currentprice=2000, previousclose=2000, change_percent=0, volume=1000,
            per=20.0, pbr=1.5, dividend_yield=5.0, equity_ratio=60.0, # High Yield
            rsi=50, deviation_rate=0
        ),
        StockData(
            symbol="3333", symbolname="Rebound Corp",
            currentprice=500, previousclose=600, change_percent=-16.6, volume=1000,
            per=15.0, pbr=1.0, dividend_yield=1.0, equity_ratio=40.0,
            rsi=15.0, deviation_rate=-25.0 # Oversold / Rebound
        )
    ]

def test_screener_value(mock_stocks):
    screener = Screener()
    results = screener.filter_stocks(mock_stocks)
    
    value_stocks = [s for s in results if "value_invest" in s["matched_strategies"]]
    assert len(value_stocks) == 1
    assert value_stocks[0]["symbol"] == "1111"

def test_screener_yield(mock_stocks):
    screener = Screener()
    results = screener.filter_stocks(mock_stocks)
    
    yield_stocks = [s for s in results if "high_dividend" in s["matched_strategies"]]
    assert len(yield_stocks) == 1
    assert yield_stocks[0]["symbol"] == "2222"

def test_screener_rebound(mock_stocks):
    screener = Screener()
    results = screener.filter_stocks(mock_stocks)
    
    rebound_stocks = [s for s in results if "rebound" in s["matched_strategies"]]
    assert len(rebound_stocks) == 1
    assert rebound_stocks[0]["symbol"] == "3333"

def test_stock_data_validation():
    # Test valid creation
    s = StockData(
        symbol="9999", symbolname="Test", currentprice=100, previousclose=90, 
        change_percent=11.1, volume=100
    )
    assert s.symbol == "9999"

    # Pydantic should handle types, but strict validation might raise errors if types are clearly wrong
    with pytest.raises(ValueError):
        StockData(
            symbol="9999", symbolname="Test", currentprice="Not a Number", previousclose=90, 
            change_percent=11.1, volume=100
        )
