from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Text, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from database import Base
from pgvector.sqlalchemy import Vector

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
    
    report_content: Mapped[str] = mapped_column(Text) # Detailed Markdown content
    score: Mapped[Optional[float]] = mapped_column(Float)
    thinking_level: Mapped[str] = mapped_column(String(20), default="standard") # low, standard, high
    
    # Summary fields for quick display
    summary: Mapped[Optional[str]] = mapped_column(Text)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20)) # bullish, bearish, neutral
    
    # New Phase 1 fields
    persona_views: Mapped[Optional[str]] = mapped_column(Text) # JSON string of persona perspectives
    catalysts: Mapped[Optional[str]] = mapped_column(Text)    # JSON string of lists
    
    stock: Mapped["StockMaster"] = relationship(back_populates="reports")

class UserWatchlist(Base):
    __tablename__ = "user_watchlists"
    
    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)

class MarketOverview(Base):
    """
    Stores snapshots of market-wide data for trend analysis.
    """
    __tablename__ = "market_overviews"
    
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    
    advancing_count: Mapped[int] = mapped_column(Integer)
    declining_count: Mapped[int] = mapped_column(Integer)
    unchanged_count: Mapped[int] = mapped_column(Integer)
    
    total_volume: Mapped[int] = mapped_column(BigInteger)
    market_sentiment_score: Mapped[Optional[float]] = mapped_column(Float) # AI derived 0-10
    
    notes: Mapped[Optional[str]] = mapped_column(Text)

class DocumentChunk(Base):
    """
    Stores chunks of documents (reports, filings) with vector embeddings for RAG.
    """
    __tablename__ = "document_chunks"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("stock_masters.symbol"), index=True)
    content: Mapped[str] = mapped_column(Text)
    
    # 768 is the dimension for Gemini Text Embedding (004)
    # 384 for Ollama's all-minilm
    embedding: Mapped[Vector] = mapped_column(Vector(768), nullable=True) 
    
    metadata_json: Mapped[Optional[str]] = mapped_column(Text) # Source (Annual Report 2024, etc.)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
class StockNote(Base):
    """
    Stores findings from Local LLM (e.g., EDINET screening).
    """
    __tablename__ = "stock_notes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("stock_masters.symbol"), index=True)
    note: Mapped[str] = mapped_column(Text)
    priority: Mapped[Optional[str]] = mapped_column(String(20)) # low, medium, high
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stock: Mapped["StockMaster"] = relationship()
