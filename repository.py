from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models_db import StockMaster, StockPrice, AnalysisReport, UserWatchlist, MarketOverview
from datetime import datetime

class StockRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_stock(self, symbol: str, name: str = "Unknown"):
        stmt = select(StockMaster).where(StockMaster.symbol == symbol)
        result = await self.session.execute(stmt)
        stock = result.scalar_one_or_none()
        
        if not stock:
            stock = StockMaster(symbol=symbol, name=name)
            self.session.add(stock)
            await self.session.commit()
            await self.session.refresh(stock)
        elif stock.name == "Unknown" and name != "Unknown":
            stock.name = name
            await self.session.commit()
            await self.session.refresh(stock)
        return stock

    async def add_price(self, symbol: str, price_data: dict):
        """
        Adds a single price record.
        price_data must match StockPrice columns.
        """
        # Ensure stock exists
        await self.get_or_create_stock(symbol)
        
        new_price = StockPrice(
            symbol=symbol,
            time=datetime.now(), # In real app, use timestamp from API
            **price_data
        )
        self.session.add(new_price)
        await self.session.commit()

    async def get_latest_prices(self, symbol: str, limit: int = 100):
        stmt = select(StockPrice).where(StockPrice.symbol == symbol).order_by(desc(StockPrice.time)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_latest_analysis(self, symbol: str) -> AnalysisReport:
        stmt = select(AnalysisReport).where(AnalysisReport.symbol == symbol).order_by(desc(AnalysisReport.created_at)).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_analysis_history(self, symbol: str) -> list[AnalysisReport]:
        stmt = select(AnalysisReport).where(AnalysisReport.symbol == symbol).order_by(desc(AnalysisReport.created_at))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_analysis_by_id(self, report_id: int) -> AnalysisReport:
        stmt = select(AnalysisReport).where(AnalysisReport.id == report_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_analysis(self, symbol: str, content: str, score: float, thinking_level: str, summary: str = None, sentiment: str = None):
        new_report = AnalysisReport(
            symbol=symbol,
            report_content=content,
            score=score,
            thinking_level=thinking_level,
            summary=summary,
            sentiment=sentiment,
            created_at=datetime.now()
        )
        self.session.add(new_report)
        await self.session.commit()

    # --- Watchlist Management ---
    async def get_watchlist_symbols(self) -> list[str]:
        stmt = select(UserWatchlist.symbol).order_by(UserWatchlist.added_at.desc())
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def add_to_watchlist(self, symbol: str, notes: str = None):
        # First ensure stock master exists
        await self.get_or_create_stock(symbol)
        
        stmt = select(UserWatchlist).where(UserWatchlist.symbol == symbol)
        result = await self.session.execute(stmt)
        if not result.scalar_one_or_none():
            new_item = UserWatchlist(symbol=symbol, notes=notes)
            self.session.add(new_item)
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
        # Join AnalysisReport with StockMaster to get names
        stmt = select(
            AnalysisReport.symbol,
            StockMaster.name.label("symbolname"),
            AnalysisReport.score.label("ai_score"),
            AnalysisReport.summary.label("ai_summary"),
            AnalysisReport.created_at
        ).join(
            StockMaster, AnalysisReport.symbol == StockMaster.symbol
        ).order_by(
            desc(AnalysisReport.created_at)
        ).limit(limit)
        
        result = await self.session.execute(stmt)
        # Convert to dict for convenience in API
        return [
            {
                "symbol": r.symbol,
                "symbolname": r.symbolname,
                "ai_score": r.ai_score,
                "ai_summary": r.ai_summary,
                "currentprice": 0, # Placeholder or fetch latest price if needed
                "change_percent": 0 # Placeholder
            }
            for r in result.all()
        ]
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
