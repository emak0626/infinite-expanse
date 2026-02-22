from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Text, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from database import Base

class StockMaster(Base):
    __tablename__ = "stock_masters"
    
    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    prices: Mapped[List["StockPrice"]] = relationship(back_populates="stock")
    reports: Mapped[List["AnalysisReport"]] = relationship(back_populates="stock")

class StockPrice(Base):
    """
    Intended to be converted to a TimescaleDB Hypertable.
    """
    __tablename__ = "stock_prices"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True) # Hypertable partitioning key
    symbol: Mapped[str] = mapped_column(ForeignKey("stock_masters.symbol"), primary_key=True)
    
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    
    # Technical Indicators (Pre-calculated)
    rsi_14: Mapped[Optional[float]] = mapped_column(Float)
    ma_25: Mapped[Optional[float]] = mapped_column(Float)
    ma_75: Mapped[Optional[float]] = mapped_column(Float)

    stock: Mapped["StockMaster"] = relationship(back_populates="prices")

class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("stock_masters.symbol"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    report_content: Mapped[str] = mapped_column(Text) # Markdown or Structured Text
    score: Mapped[Optional[float]] = mapped_column(Float)
    thinking_level: Mapped[str] = mapped_column(String(20), default="standard") # low, standard, high
    
    stock: Mapped["StockMaster"] = relationship(back_populates="reports")
