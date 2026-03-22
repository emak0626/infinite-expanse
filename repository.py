from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models_db import StockMaster, StockPrice, AnalysisReport, UserWatchlist, MarketOverview, StockNote
from datetime import datetime
import json

class StockRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_stock(self, symbol: str, name: str = "Unknown"):
        from models_db import StockMaster
        
        # Guard against saving error messages as stock names
        invalid_keywords = ["[Local AI Fallback]", "【接続エラー】", "【モデル未取得】", "【Ollamaエラー】"]
        if name and any(k in name for k in invalid_keywords):
            name = "Unknown"

        # Try to get best name from local map if Unknown
        if name == "Unknown" or not name:
            import json
            import os
            try:
                mapping_path = os.path.join(os.path.dirname(__file__), "stock_names.json")
                if os.path.exists(mapping_path):
                    with open(mapping_path, "r", encoding="utf-8") as f:
                        name_map = json.load(f)
                        if symbol in name_map:
                            name = name_map[symbol]
            except:
                pass

        stmt = select(StockMaster).where(StockMaster.symbol == symbol)
        result = await self.session.execute(stmt)
        stock = result.scalar_one_or_none()
        
        if not stock:
            stock = StockMaster(symbol=symbol, name=name if name else "Unknown")
            self.session.add(stock)
            await self.session.commit()
            await self.session.refresh(stock)
        elif name != "Unknown" and (stock.name == "Unknown" or "Mock" in stock.name or stock.name.startswith("銘柄")):
            stock.name = name
            await self.session.commit()
            await self.session.refresh(stock)
        return stock

    async def get_all_stocks(self) -> list[StockMaster]:
        from models_db import StockMaster
        stmt = select(StockMaster).order_by(StockMaster.symbol)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_price(self, symbol: str, price_data: dict):
        # Ensure stock exists
        await self.get_or_create_stock(symbol)
        from models_db import StockPrice
        new_price = StockPrice(
            symbol=symbol,
            time=datetime.now(),
            **price_data
        )
        self.session.add(new_price)
        await self.session.commit()

    async def get_latest_prices(self, symbol: str, limit: int = 100):
        from models_db import StockPrice
        stmt = select(StockPrice).where(StockPrice.symbol == symbol).order_by(desc(StockPrice.time)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_analysis(self, symbol: str) -> AnalysisReport:
        from models_db import AnalysisReport
        stmt = select(AnalysisReport).where(AnalysisReport.symbol == symbol).order_by(desc(AnalysisReport.created_at)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_watchlist_symbols(self) -> list[str]:
        from models_db import UserWatchlist
        stmt = select(UserWatchlist.symbol)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_to_watchlist(self, symbol: str):
        # Additional step to ensure stock exists
        await self.get_or_create_stock(symbol)
        from models_db import UserWatchlist
        watchlist_item = UserWatchlist(symbol=symbol)
        self.session.add(watchlist_item)
        await self.session.commit()

    async def remove_from_watchlist(self, symbol: str):
        from models_db import UserWatchlist
        stmt = select(UserWatchlist).where(UserWatchlist.symbol == symbol)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item:
            await self.session.delete(item)
            await self.session.commit()

    async def save_analysis(self, symbol: str, analysis: dict, thinking_level: str = "standard"):
        from models_db import AnalysisReport
        import json
        await self.get_or_create_stock(symbol)
        report = AnalysisReport(
            symbol=symbol,
            report_content=json.dumps(analysis, ensure_ascii=False),
            score=analysis.get("score"),
            summary=analysis.get("summary"),
            sentiment=analysis.get("sentiment", "Neutral"),
            persona_views=json.dumps(analysis.get("persona_views")) if "persona_views" in analysis else None,
            catalysts=json.dumps(analysis.get("catalysts")) if "catalysts" in analysis else None,
            thinking_level=thinking_level,
            created_at=datetime.now()
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def update_latest_trade_strategy(self, symbol: str, strategy_text: str):
        from models_db import AnalysisReport
        from datetime import datetime
        report = await self.get_latest_analysis(symbol)
        if report:
            report.trade_strategy = strategy_text
            # Also update thinking level if needed? No, let's keep it.
        else:
            # Create a new stub report if none exists
            report = AnalysisReport(
                symbol=symbol,
                report_content="# Local AI Trade Strategy\n(Detailed analysis not yet performed)",
                trade_strategy=strategy_text,
                created_at=datetime.now()
            )
            self.session.add(report)
        
        await self.session.commit()
        return report

    async def get_analysis_by_id(self, report_id: int):
        from models_db import AnalysisReport
        stmt = select(AnalysisReport).where(AnalysisReport.id == report_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_analysis_history(self, symbol: str):
        from models_db import AnalysisReport
        stmt = select(AnalysisReport).where(AnalysisReport.symbol == symbol).order_by(desc(AnalysisReport.created_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_top_ai_stocks(self, limit: int = 50):
        """
        Fetches stocks with their LATEST AI analysis, avoiding duplicates.
        """
        from sqlalchemy import func, and_
        
        # 1. Subquery for the LATEST report per symbol
        latest_report_sub = select(
            AnalysisReport.symbol,
            func.max(AnalysisReport.created_at).label("max_created_at")
        ).group_by(AnalysisReport.symbol).subquery()

        # 2. Subquery for the LATEST price per symbol
        latest_price_sub = select(
            StockPrice.symbol,
            func.max(StockPrice.time).label("max_time")
        ).group_by(StockPrice.symbol).subquery()

        # 3. Main join query
        stmt = (
            select(
                AnalysisReport.symbol,
                StockMaster.name.label("symbolname"),
                AnalysisReport.score.label("ai_score"),
                AnalysisReport.summary.label("ai_summary"),
                AnalysisReport.sentiment.label("ai_sentiment"),
                AnalysisReport.created_at,
                StockPrice.close.label("currentprice")
            )
            .join(latest_report_sub, and_(
                AnalysisReport.symbol == latest_report_sub.c.symbol,
                AnalysisReport.created_at == latest_report_sub.c.max_created_at
            ))
            .join(StockMaster, AnalysisReport.symbol == StockMaster.symbol)
            .outerjoin(latest_price_sub, AnalysisReport.symbol == latest_price_sub.c.symbol)
            .outerjoin(StockPrice, and_(
                StockPrice.symbol == latest_price_sub.c.symbol,
                StockPrice.time == latest_price_sub.c.max_time
            ))
            .order_by(desc(AnalysisReport.score), desc(AnalysisReport.created_at))
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        rows = result.all()
        
        results = []
        for r in rows:
            results.append({
                "symbol": r.symbol,
                "symbolname": r.symbolname if r.symbolname else f"銘柄 {r.symbol}",
                "ai_score": r.ai_score,
                "ai_summary": r.ai_summary,
                "ai_sentiment": r.ai_sentiment,
                "currentprice": r.currentprice if r.currentprice else 0,
                "change_percent": 0.0,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
        return results

    async def add_stock_note(self, symbol: str, note: str, priority: str = "low"):
        """
        Adds a note for a stock (e.g., from local LLM screening).
        """
        # Ensure stock exists
        await self.get_or_create_stock(symbol)
        
        from models_db import StockNote
        new_note = StockNote(
            symbol=symbol,
            note=note,
            priority=priority,
            created_at=datetime.now()
        )
        self.session.add(new_note)
        await self.session.commit()

    async def save_market_overview(self, overview_data: dict):
        new_overview = MarketOverview(
            time=datetime.now(),
            **overview_data
        )
        self.session.add(new_overview)
        await self.session.commit()
        return new_overview

    async def get_latest_market_overview(self) -> MarketOverview:
        stmt = select(MarketOverview).order_by(desc(MarketOverview.time)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
