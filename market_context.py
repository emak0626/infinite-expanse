import yfinance as yf
import feedparser
import json
import os
from datetime import datetime
from workspace_manager import workspace_mgr

class MarketContextFetcher:
    def __init__(self):
        # Major indices for Japanese market context
        self.indices = {
            "日経225": "^N225",
            "VIX指数": "^VIX",
            "USD/JPY": "JPY=X",
            "S&P500": "^GSPC"
        }
        # RSS feeds for news
        self.news_feeds = [
            "https://www.reutersagency.com/feed/?best-topics=business&post_type=best",
            "https://www.nhk.or.jp/rss/news/cat0.xml", # Top news
            "https://shikiho.toyokeizai.net/rss/shikiho" # Stock specific
        ]

    def fetch_indices(self) -> dict:
        results = {}
        for name, ticker in self.indices.items():
            try:
                data = yf.Ticker(ticker)
                hist = data.history(period="2d")
                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                    change = current - prev
                    change_pct = (change / prev) * 100 if prev != 0 else 0
                    results[name] = {
                        "value": round(current, 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2)
                    }
            except Exception as e:
                print(f"Failed to fetch {name}: {e}")
        return results

    def fetch_news(self) -> list:
        news_items = []
        for url in self.news_feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]: # Top 5 from each feed
                    news_items.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", "")
                    })
            except Exception as e:
                print(f"Failed to fetch news from {url}: {e}")
        return news_items

    def save_context(self):
        """Fetches all data and saves to workspace/Market_Context/"""
        indices = self.fetch_indices()
        news = self.fetch_news()
        
        context = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "indices": indices,
            "news": news,
            "trends": ["半導体", "円安メリット", "新興株物色"] # Placeholder for now
        }
        
        filename = f"context_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path = workspace_mgr.get_path("context", filename)
        
        # Ensure directory exists (workspace_mgr should handle this but to be safe)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "w", encoding="utf-8-sig") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
            
        # Also update a 'latest' symlink or file for easy access
        latest_path = workspace_mgr.get_path("context", "latest_context.json")
        with open(latest_path, "w", encoding="utf-8-sig") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
            
        print(f"Market context saved to {path}")
        return context

    def get_latest_context(self) -> dict:
        """Loads the latest available context from workspace."""
        latest_path = workspace_mgr.get_path("context", "latest_context.json")
        if os.path.exists(latest_path):
            try:
                with open(latest_path, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except:
                pass
        return None

market_fetcher = MarketContextFetcher()
