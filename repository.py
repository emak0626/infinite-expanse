from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models_db import StockMaster, StockPrice, AnalysisReport
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
