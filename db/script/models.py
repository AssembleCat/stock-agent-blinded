from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    BigInteger,
    Index,
    DateTime,
    Boolean,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, unique=True, index=True)
    name = Column(String)
    market = Column(String)


class OHLCV(Base):
    __tablename__ = "ohlcv"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)
    volume = Column(BigInteger)
    value = Column(BigInteger)
    change_rate = Column(Float)


class MarketIndexOHLCV(Base):
    __tablename__ = "market_index_ohlcv"
    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    value = Column(
        BigInteger
    )  # 거래대금(=close*volume) 필드, yfinance에서 직접 계산하여 저장


class TechnicalSignal(Base):
    __tablename__ = "technical_signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    date = Column(Date, index=True)
    indicator = Column(String)
    value = Column(Float)


class QuizHistory(Base):
    """퀴즈 이력을 저장하는 테이블"""

    __tablename__ = "quiz_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(100), nullable=False)  # 사용자 요청 고유 ID
    quiz_id = Column(Integer, nullable=False)
    quiz_question = Column(Text, nullable=False)
    correct_answer = Column(String(100), nullable=False)
    user_answer = Column(String(100), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    hint_used = Column(Boolean, default=False)
    reward_stock = Column(String(100), nullable=False)
    reward_amount = Column(Float, nullable=False)
    completed_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("idx_quiz_request_id", "request_id"),
        Index("idx_quiz_completed_at", "completed_at"),
        Index("idx_quiz_id", "quiz_id"),
        Index("idx_quiz_is_correct", "is_correct"),
    )

    def __repr__(self):
        return f"<QuizHistory(quiz_id={self.quiz_id}, correct={self.is_correct}, reward={self.reward_amount})>"
