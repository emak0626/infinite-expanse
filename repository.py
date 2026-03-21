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

        stmt = select(StockMaster).where(StockMaster.symbol == symbol)
        result = await self.session.execute(stmt)
        stock = result.scalar_one_or_none()
        
        if not stock:
            stock = StockMaster(symbol=symbol, name=name)
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

    async def add_stock_note(self, symbol: str, note: str, priority: str = "low"):
        from models_db import StockNote
        await self.get_or_create_stock(symbol)
        new_note = StockNote(
            symbol=symbol, note=note, priority=priority, created_at=datetime.now()
        )
        self.session.add(new_note)
        await self.session.commit()
    
    async def get_top_ai_stocks(self, limit: int = 50):
        """
        Fetches stocks with latest AI analysis, joined with latest market prices.
        """
        from sqlalchemy import func, outerjoin
        
        # 1. Subquery for latest report
        latest_report_sub = select(
            AnalysisReport.symbol,
            func.max(AnalysisReport.created_at).label("max_created_at")
        ).group_by(AnalysisReport.symbol).subquery()

        # 2. Subquery for latest price
        latest_price_sub = select(
            StockPrice.symbol,
            func.max(StockPrice.time).label("max_time")
        ).group_by(StockPrice.symbol).subquery()

        # 3. Main query
        stmt = (
            select(
                AnalysisReport.symbol,
                StockMaster.name.label("symbolname"),
                AnalysisReport.score.label("ai_score"),
                AnalysisReport.summary.label("ai_summary"),
                AnalysisReport.sentiment.label("ai_sentiment"),
                AnalysisReport.created_at,
                StockPrice.close.label("currentprice"),
                StockPrice.time.label("price_time")
            )
            .join(latest_report_sub, and_(
                AnalysisReport.symbol == latest_report_sub.c.symbol,
                AnalysisReport.created_at == latest_report_sub.c.max_created_at
            ))
            .join(StockMaster, AnalysisReport.symbol == StockMaster.symbol)
            .outerjoin(latest_price_sub, StockMaster.symbol == latest_price_sub.c.symbol)
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
                "change_percent": 0.0, # Will be enriched if needed
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
        return results

    async def get_analysis_by_id(self, report_id: int) -> AnalysisReport:
        stmt = select(AnalysisReport).where(AnalysisReport.id == report_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_analysis(self, symbol: str, analysis: dict, thinking_level: str):
        """Saves a structured analysis dictionary to the database."""
        score_val = analysis.get("score", 0)
        try:
            score_float = float(score_val)
        except (TypeError, ValueError):
            score_float = 0.0

        new_report = AnalysisReport(
            symbol=symbol,
            report_content=json.dumps(analysis, ensure_ascii=False),
            score=score_float,
            summary=analysis.get("summary", "Manual Analysis" if thinking_level=="manual_paste" else ""),
            sentiment=analysis.get("sentiment", "Neutral"),
            persona_views=json.dumps(analysis.get("persona_views"), ensure_ascii=False) if "persona_views" in analysis else None,
            catalysts=json.dumps(analysis.get("catalysts"), ensure_ascii=False) if "catalysts" in analysis else None,
            thinking_level=thinking_level,
            created_at=datetime.now()
        )
        self.session.add(new_report)
        await self.session.commit()

    # --- Watchlist Management ---
    async def get_watchlist_symbols(self) -> list[str]:
        stmt = select(UserWatchlist.symbol).order_by(UserWatchlist.added_at.desc())
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def add_to_watchlist(self, symbol: str):
        # 先にマスタに存在することを確認（Unknownでも良いので作成）
        await self.get_or_create_stock(symbol)
        
        watchlist_item = UserWatchlist(symbol=symbol)
        self.session.add(watchlist_item)
        await self.session.commit()

    async def remove_from_watchlist(self, symbol: str):
        stmt = select(UserWatchlist).where(UserWatchlist.symbol == symbol)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item:
            await self.session.delete(item)
            await self.session.commit()

    # --- Market Overview Accumulation ---
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

    async def get_top_ai_stocks(self, limit: int = 50):
        """
        Fetches stocks with latest AI analysis, joined with latest market prices.
        """
        from sqlalchemy import and_, outerjoin
        
        # Subquery to get the latest price for each symbol
        from sqlalchemy import func
        latest_price_sub = select(
            StockPrice.symbol,
            StockPrice.close,
            StockPrice.time
        ).distinct(StockPrice.symbol).order_by(StockPrice.symbol, desc(StockPrice.time)).subquery()

        # Previous price for change calculation (2nd latest)
        # Note: This is getting complex for a single query, let's simplify by fetching and processing.
        
        stmt = select(
            AnalysisReport.symbol,
            StockMaster.name.label("symbolname"),
            AnalysisReport.score.label("ai_score"),
            AnalysisReport.summary.label("ai_summary"),
            AnalysisReport.created_at,
            latest_price_sub.c.close.label("currentprice")
        ).join(
            StockMaster, AnalysisReport.symbol == StockMaster.symbol
        ).outerjoin(
            latest_price_sub, AnalysisReport.symbol == latest_price_sub.c.symbol
        ).order_by(
            desc(AnalysisReport.created_at)
        ).limit(limit)
        
        result = await self.session.execute(stmt)
        rows = result.all()
        
        results = []
        for r in rows:
            # For each stock, we might want to calculate the change % properly
            # But to keep it efficient, we'll use a simplified version here or 0 if no price data
            results.append({
                "symbol": r.symbol,
                "symbolname": r.symbolname,
                "ai_score": r.ai_score,
                "ai_summary": r.ai_summary,
                "currentprice": r.currentprice or 0,
                "change_percent": 0 # Default to 0, we'll try to improve this if data is available
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

    async def save_analysis(self, symbol: str, analysis: dict, thinking_level: str = "standard"):
        """
        Saves an AI analysis report to the database.
        """
        from models_db import AnalysisReport
        import json
        
        # Ensure stock exists
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
