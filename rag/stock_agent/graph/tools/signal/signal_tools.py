from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from db.sqlite_db import SqliteDBClient
from db.crud import get_stock_name
from datetime import datetime
import pandas as pd
import sys
import os

# 상위 디렉토리 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from rag.stock_agent.graph.utils import (
    get_result_count,
    create_result_response,
)


# 볼린저 밴드 터치 도구
class BollingerTouchInput(BaseModel):
    start_date: Optional[str] = Field(
        None, description="시작 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    end_date: Optional[str] = Field(
        None, description="종료 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD) - 단일 날짜 조회 시 사용"
    )
    band_type: str = Field(default="LOWER", description="밴드 타입 (UPPER, LOWER)")
    tolerance: float = Field(default=0.5, description="터치 허용 오차 (%)")
    count: Optional[int] = Field(default=None, description="반환할 결과 개수")
    
    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=BollingerTouchInput)
def get_bollinger_touch_stocks(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    band_type: str = "LOWER",
    tolerance: float = 0.5,
    count: Optional[int] = None,
):
    """
    특정 날짜 또는 기간에 볼린저 밴드에 터치한 종목들을 조회합니다.
    """
    db = SqliteDBClient()
    try:
        # 날짜 조건 결정 (기간 또는 단일 날짜)
        if start_date and end_date:
            # 기간 조회
            date_condition = "ts.date BETWEEN ? AND ?"
            params = [start_date, end_date]
        elif date:
            # 단일 날짜 조회
            date_condition = "ts.date = ?"
            params = [date]
        else:
            return create_result_response(
                data=[], total_count=0, sort_key="close", reverse=True
            )

        indicator_map = {
            "UPPER": "BOLLINGER_UPPER",
            "LOWER": "BOLLINGER_LOWER",
        }
        indicator = indicator_map.get(band_type.upper(), "BOLLINGER_LOWER")

        # 성능 최적화: JOIN을 통해 한 번의 쿼리로 모든 데이터 조회
        query = f"""
        SELECT ts.ticker, ts.value as band_value, o.close, o.high, o.low, s.name
        FROM technical_signals ts
        JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
        JOIN stocks s ON ts.ticker = s.ticker
        WHERE {date_condition} AND ts.indicator = ?
        AND o.volume > 0 AND o.close > 0
        """
        params.append(indicator)
        results = db.execute(query, params)
        touch_stocks = []

        for row in results:
            ticker, band_value, close, high, low, stock_name = row
            if band_value is None or not isinstance(band_value, (int, float)):
                continue

            is_touch = False
            if band_type.upper() == "UPPER":
                touch_range = band_value * (1 + tolerance / 100)
                is_touch = high >= band_value and high <= touch_range
            elif band_type.upper() == "LOWER":
                touch_range = band_value * (1 - tolerance / 100)
                is_touch = low <= band_value and low >= touch_range

            if is_touch:
                touch_stocks.append(
                    {
                        "name": stock_name,
                        "close": close,
                        "band_value": round(band_value, 2),
                        "touch_type": band_type.lower(),
                    }
                )

        # 볼린저 밴드 터치 정도 기준으로 정렬 (상단밴드는 높은 터치, 하단밴드는 낮은 터치)
        if band_type.upper() == "UPPER":
            # 상단밴드 터치: 종가가 밴드에 가까울수록 상위
            touch_stocks.sort(
                key=lambda x: (x["close"] / x["band_value"]), reverse=True
            )
        else:
            # 하단밴드 터치: 종가가 밴드에 가까울수록 상위 (낮은 값이 상위)
            touch_stocks.sort(key=lambda x: (x["close"] / x["band_value"]))

        # 표준화된 응답 생성 (정렬 정보 포함)
        sort_key = "close"  # 볼린저 밴드 터치는 종가 기준으로 정렬
        reverse = band_type.upper() == "UPPER"  # 상단밴드는 높은 값이 상위

        return create_result_response(
            data=touch_stocks,
            total_count=len(touch_stocks),
            indicator_type="BOLLINGER_BANDS",
            requested_count=count,
            sort_key=sort_key,
            reverse=reverse,
            date=date,
            band_type=band_type,
            tolerance=tolerance,
        )

    except Exception as e:
        return {"error": f"볼린저 밴드 터치 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()


# 골든/데드 크로스 신호 도구
class CrossSignalInput(BaseModel):
    start_date: str = Field(..., description="시작 날짜 (YYYY-MM-DD)")
    end_date: str = Field(..., description="종료 날짜 (YYYY-MM-DD)")
    signal_type: str = Field(
        default="GOLDEN_CROSS", description="신호 타입 (GOLDEN_CROSS, DEAD_CROSS, ALL)"
    )
    
    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=CrossSignalInput)
def get_cross_signal_stocks(
    start_date: str, end_date: str, signal_type: str = "GOLDEN_CROSS"
):
    """
    특정 기간에 골든/데드 크로스가 발생한 종목들을 조회합니다.
    """
    db = SqliteDBClient()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        cross_stocks = []

        # 특정 날짜 조회인지 기간 조회인지 확인
        is_single_date = start_date == end_date

        if signal_type.upper() == "ALL":
            # GOLDEN_CROSS
            if is_single_date:
                query1 = """
                SELECT ts.ticker, ts.date, 'GOLDEN_CROSS' as signal_type, o.close, o.volume
                FROM technical_signals ts
                JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
                WHERE ts.date = ? AND ts.indicator = 'GOLDEN_CROSS'
                """
                query2 = """
                SELECT ts.ticker, ts.date, 'DEAD_CROSS' as signal_type, o.close, o.volume
                FROM technical_signals ts
                JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
                WHERE ts.date = ? AND ts.indicator = 'DEAD_CROSS'
                """
                results1 = db.execute(query1, (start_dt,))
                results2 = db.execute(query2, (start_dt,))
            else:
                query1 = """
                SELECT ts.ticker, ts.date, 'GOLDEN_CROSS' as signal_type, o.close, o.volume
                FROM technical_signals ts
                JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
                WHERE ts.date BETWEEN ? AND ? AND ts.indicator = 'GOLDEN_CROSS'
                """
                query2 = """
                SELECT ts.ticker, ts.date, 'DEAD_CROSS' as signal_type, o.close, o.volume
                FROM technical_signals ts
                JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
                WHERE ts.date BETWEEN ? AND ? AND ts.indicator = 'DEAD_CROSS'
                """
                results1 = db.execute(query1, (start_dt, end_dt))
                results2 = db.execute(query2, (start_dt, end_dt))

            for row in results1:
                ticker, date, signal, close, volume = row
                stock_name = get_stock_name(ticker)
                # date가 datetime.date 객체인지 문자열인지 확인
                if hasattr(date, "strftime"):
                    date_str = date.strftime("%Y-%m-%d")
                else:
                    date_str = str(date)
                cross_stocks.append(
                    {
                        "name": stock_name,
                        "date": date_str,
                        "signal_type": signal,
                        "close": close,
                        "volume": volume,
                    }
                )
            for row in results2:
                ticker, date, signal, close, volume = row
                stock_name = get_stock_name(ticker)
                # date가 datetime.date 객체인지 문자열인지 확인
                if hasattr(date, "strftime"):
                    date_str = date.strftime("%Y-%m-%d")
                else:
                    date_str = str(date)
                cross_stocks.append(
                    {
                        "name": stock_name,
                        "date": date_str,
                        "signal_type": signal,
                        "close": close,
                        "volume": volume,
                    }
                )
        else:
            indicator = signal_type.upper()
            if is_single_date:
                query = """
                SELECT ts.ticker, ts.date, ? as signal_type, o.close, o.volume
                FROM technical_signals ts
                JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
                WHERE ts.date = ? AND ts.indicator = ?
                """
                results = db.execute(query, (indicator, start_dt, indicator))
            else:
                query = """
                SELECT ts.ticker, ts.date, ? as signal_type, o.close, o.volume
                FROM technical_signals ts
                JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
                WHERE ts.date BETWEEN ? AND ? AND ts.indicator = ?
                """
                results = db.execute(query, (indicator, start_dt, end_dt, indicator))

            for row in results:
                ticker, date, signal, close, volume = row
                stock_name = get_stock_name(ticker)
                # date가 datetime.date 객체인지 문자열인지 확인
                if hasattr(date, "strftime"):
                    date_str = date.strftime("%Y-%m-%d")
                else:
                    date_str = str(date)
                cross_stocks.append(
                    {
                        "name": stock_name,
                        "date": date_str,
                        "signal_type": signal,
                        "close": close,
                        "volume": volume,
                    }
                )

        # 신호 발생 순서와 거래량 기준으로 정렬 (최근 신호와 거래량 많은 순)
        cross_stocks.sort(key=lambda x: (x["date"], x["volume"]), reverse=True)

        # 표준화된 응답 생성 (정렬 정보 포함)
        # 크로스 신호는 날짜와 거래량 기준으로 정렬 (최근 신호와 거래량 많은 순)
        sort_key = "date"  # 날짜 기준 정렬
        reverse = True  # 최근 날짜가 상위

        return create_result_response(
            data=cross_stocks,
            total_count=len(cross_stocks),
            indicator_type="CROSS_SIGNAL",
            requested_count=None,
            sort_key=sort_key,
            reverse=reverse,
            start_date=start_date,
            end_date=end_date,
            signal_type=signal_type,
        )
    except Exception as e:
        return {"error": f"크로스 신호 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()


# 특정 종목 크로스 신호 횟수 도구
class CrossSignalCountInput(BaseModel):
    ticker: str = Field(..., description="종목 코드 (예: 005930.KS)")
    start_date: str = Field(..., description="시작 날짜 (YYYY-MM-DD)")
    end_date: str = Field(..., description="종료 날짜 (YYYY-MM-DD)")
    
    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=CrossSignalCountInput)
def get_cross_signal_count_by_stock(ticker: str, start_date: str, end_date: str):
    """
    특정 종목의 골든/데드 크로스 발생 횟수를 조회합니다.
    """
    db = SqliteDBClient()
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        # ticker가 종목명인 경우 ticker 코드로 변환
        if not ticker.endswith(".KS") and not ticker.endswith(".KQ"):
            # 종목명으로 ticker 찾기
            ticker_query = """
            SELECT ticker FROM stocks WHERE name = ?
            """
            ticker_result = db.execute(ticker_query, (ticker,))
            if ticker_result:
                ticker = ticker_result[0][0]
            else:
                return create_result_response(
                    data=[
                        {
                            "name": ticker,
                            "start_date": start_date,
                            "end_date": end_date,
                            "golden_cross_count": 0,
                            "dead_cross_count": 0,
                            "total_cross_count": 0,
                            "message": "종목을 찾을 수 없습니다.",
                        }
                    ],
                    total_count=1,
                    indicator_type="CROSS_SIGNAL_COUNT",
                    requested_count=None,
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                )

        stock_name = get_stock_name(ticker)

        # 해당 종목의 데이터가 있는지 확인
        data_check_query = """
        SELECT COUNT(*) FROM ohlcv WHERE ticker = ? AND date BETWEEN ? AND ?
        """
        data_count = db.execute(data_check_query, (ticker, start_dt, end_dt))[0][0]

        if data_count == 0:
            return create_result_response(
                data=[
                    {
                        "name": stock_name,
                        "start_date": start_date,
                        "end_date": end_date,
                        "golden_cross_count": 0,
                        "dead_cross_count": 0,
                        "total_cross_count": 0,
                        "message": "해당 기간에 데이터가 없습니다.",
                    }
                ],
                total_count=1,
                indicator_type="CROSS_SIGNAL_COUNT",
                requested_count=None,
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
            )

        # GOLDEN_CROSS 카운트
        query1 = """
        SELECT COUNT(*) FROM technical_signals ts WHERE ts.ticker = ? AND ts.date BETWEEN ? AND ? AND ts.indicator = 'GOLDEN_CROSS'
        """
        # DEAD_CROSS 카운트
        query2 = """
        SELECT COUNT(*) FROM technical_signals ts WHERE ts.ticker = ? AND ts.date BETWEEN ? AND ? AND ts.indicator = 'DEAD_CROSS'
        """
        golden_count = db.execute(query1, (ticker, start_dt, end_dt))[0][0]
        dead_count = db.execute(query2, (ticker, start_dt, end_dt))[0][0]

        # 결과를 create_result_response 형식으로 변환
        result_data = {
            "name": stock_name,
            "start_date": start_date,
            "end_date": end_date,
            "golden_cross_count": golden_count,
            "dead_cross_count": dead_count,
            "total_cross_count": golden_count + dead_count,
        }

        return create_result_response(
            data=[result_data],  # 단일 종목 결과를 리스트로 감싸기
            total_count=1,
            indicator_type="CROSS_SIGNAL_COUNT",
            requested_count=None,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        return {"error": f"크로스 신호 횟수 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()


# 거래량 급증 도구
class VolumeSurgeInput(BaseModel):
    start_date: Optional[str] = Field(
        None, description="시작 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    end_date: Optional[str] = Field(
        None, description="종료 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD) - 단일 날짜 조회 시 사용"
    )
    surge_ratio: float = Field(default=100.0, description="급증 기준 비율 (%)")
    ma_period: int = Field(default=20, description="이동평균 기간")
    count: Optional[int] = Field(default=None, description="반환할 결과 개수")
    
    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=VolumeSurgeInput)
def get_volume_surge_stocks(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    surge_ratio: float = 100.0,
    ma_period: int = 20,
    count: Optional[int] = None,
):
    """
    특정 날짜 또는 기간에 거래량이 급증한 종목들을 조회합니다.
    """
    db = SqliteDBClient()

    try:
        # 날짜 조건 결정 (기간 또는 단일 날짜)
        if start_date and end_date:
            # 기간 조회
            date_condition = "o.date BETWEEN ? AND ?"
            params = [start_date, end_date]
        elif date:
            # 단일 날짜 조회
            date_condition = "o.date = ?"
            params = [date]
        else:
            return create_result_response(
                data=[],
                total_count=0,
                indicator_type="VOLUME_SURGE",
                requested_count=count,
            )

        # 성능 최적화: 서브쿼리를 사용하여 한 번의 쿼리로 모든 데이터 조회
        query = f"""
        SELECT o.ticker, o.volume as current_volume, o.close, s.name,
               (SELECT AVG(prev_o.volume) 
                FROM ohlcv prev_o 
                WHERE prev_o.ticker = o.ticker 
                AND prev_o.date < o.date 
                AND prev_o.date >= date(o.date, '-{ma_period} days')
                AND prev_o.volume > 0) as avg_volume
        FROM ohlcv o
        JOIN stocks s ON o.ticker = s.ticker
        WHERE {date_condition} AND o.volume > 0
        """

        results = db.execute(query, params)
        surge_stocks = []
        for row in results:
            ticker, current_volume, close, stock_name, avg_volume = row

            if avg_volume and avg_volume > 0:
                volume_ratio = (current_volume / avg_volume) * 100

                if volume_ratio >= surge_ratio:
                    surge_stocks.append(
                        {
                            "name": stock_name,
                            "current_volume": current_volume,
                            "avg_volume": round(avg_volume, 0),
                            "volume_ratio": round(volume_ratio, 1),
                            "close": close,
                        }
                    )

        # 거래량 비율 기준으로 정렬 (내림차순)
        surge_stocks.sort(key=lambda x: x["volume_ratio"], reverse=True)

        # 표준화된 응답 생성
        return create_result_response(
            data=surge_stocks,
            total_count=len(surge_stocks),
            indicator_type="VOLUME_SURGE",
            requested_count=count,
            date=date,
            surge_ratio=surge_ratio,
            ma_period=ma_period,
        )

    except Exception as e:
        return {"error": f"거래량 급증 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()


# RSI 도구
class RSIInput(BaseModel):
    start_date: Optional[str] = Field(
        None, description="시작 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    end_date: Optional[str] = Field(
        None, description="종료 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD) - 단일 날짜 조회 시 사용"
    )
    rsi_threshold: float = Field(default=80.0, description="RSI 임계값")
    condition: str = Field(
        default="OVERBOUGHT",
        description="조건 타입 (OVERBOUGHT, OVERSOLD, ABOVE, BELOW)",
    )
    count: Optional[int] = Field(default=None, description="반환할 결과 개수")
    
    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=RSIInput)
def get_rsi_stocks(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    rsi_threshold: float = 80.0,
    condition: str = "OVERBOUGHT",
    count: Optional[int] = None,
):
    """
    특정 날짜 또는 기간에 RSI 조건을 만족하는 종목들을 조회합니다.
    """
    db = SqliteDBClient()

    try:
        # 날짜 조건 결정 (기간 또는 단일 날짜)
        if start_date and end_date:
            # 기간 조회
            date_condition = "ts.date BETWEEN ? AND ?"
            params = [start_date, end_date]
        elif date:
            # 단일 날짜 조회
            date_condition = "ts.date = ?"
            params = [date]
        else:
            return create_result_response(
                data=[], total_count=0, indicator_type="RSI", requested_count=count
            )

        # 성능 최적화: JOIN을 통해 한 번의 쿼리로 모든 데이터 조회
        query = f"""
        SELECT ts.ticker, ts.value as rsi_value, o.close, o.volume, s.name
        FROM technical_signals ts
        JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
        JOIN stocks s ON ts.ticker = s.ticker
        WHERE {date_condition} AND ts.indicator = 'RSI_14'
        AND o.volume > 0 AND o.close > 0
        """

        results = db.execute(query, params)
        rsi_stocks = []
        for row in results:
            ticker, rsi_value, close, volume, stock_name = row

            # rsi_value가 None이거나 유효하지 않은 경우 건너뛰기
            if rsi_value is None or not isinstance(rsi_value, (int, float)):
                continue

            # 조건 확인
            is_match = False
            if condition.upper() == "OVERBOUGHT":
                is_match = rsi_value >= rsi_threshold
            elif condition.upper() == "OVERSOLD":
                is_match = rsi_value <= rsi_threshold
            elif condition.upper() == "ABOVE":
                is_match = rsi_value > rsi_threshold
            elif condition.upper() == "BELOW":
                is_match = rsi_value < rsi_threshold

            if is_match:
                rsi_stocks.append(
                    {
                        "name": stock_name,
                        "rsi": round(rsi_value, 2),
                        "close": close,
                        "volume": volume,
                        "condition": condition.lower(),
                    }
                )

        # RSI 값 기준으로 정렬 (과매수는 내림차순, 과매도는 오름차순)
        if condition.upper() in ["OVERBOUGHT", "ABOVE"]:
            rsi_stocks.sort(key=lambda x: x["rsi"], reverse=True)
        else:
            rsi_stocks.sort(key=lambda x: x["rsi"])

        # 표준화된 응답 생성 (정렬 정보 포함)
        sort_key = "rsi"
        reverse = condition.upper() in ["OVERBOUGHT", "ABOVE"]

        return create_result_response(
            data=rsi_stocks,
            total_count=len(rsi_stocks),
            indicator_type="RSI",
            requested_count=count,
            sort_key=sort_key,
            reverse=reverse,
            date=date,
            rsi_threshold=rsi_threshold,
            condition=condition,
        )

    except Exception as e:
        return {"error": f"RSI 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()


# 이동평균 편차 도구
class MADeviationInput(BaseModel):
    start_date: Optional[str] = Field(
        None, description="시작 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    end_date: Optional[str] = Field(
        None, description="종료 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD) - 단일 날짜 조회 시 사용"
    )
    ma_period: int = Field(default=20, description="이동평균 기간")
    deviation_percent: float = Field(default=10.0, description="편차 기준 퍼센트 (%)")
    condition: str = Field(
        default="ABOVE", description="조건 타입 (ABOVE, BELOW, ABSOLUTE)"
    )
    count: Optional[int] = Field(default=None, description="반환할 결과 개수")
    
    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=MADeviationInput)
def get_ma_deviation_stocks(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    ma_period: int = 20,
    deviation_percent: float = 10.0,
    condition: str = "ABOVE",
    count: Optional[int] = None,
):
    """
    특정 날짜 또는 기간에 이동평균 대비 가격 편차가 있는 종목들을 조회합니다.
    """
    db = SqliteDBClient()

    try:
        # 날짜 조건 결정 (기간 또는 단일 날짜)
        if start_date and end_date:
            # 기간 조회
            date_condition = "ts.date BETWEEN ? AND ?"
            params = [start_date, end_date]
        elif date:
            # 단일 날짜 조회
            date_condition = "ts.date = ?"
            params = [date]
        else:
            return create_result_response(
                data=[],
                total_count=0,
                indicator_type="MA_DEVIATION",
                requested_count=count,
            )

        # 성능 최적화: JOIN을 통해 한 번의 쿼리로 모든 데이터 조회
        query = f"""
        SELECT ts.ticker, ts.value as ma_value, o.close, o.volume, s.name
        FROM technical_signals ts
        JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
        JOIN stocks s ON ts.ticker = s.ticker
        WHERE {date_condition} AND ts.indicator = ?
        AND o.volume > 0 AND o.close > 0
        """

        indicator = f"MA_{ma_period}"
        params.append(indicator)
        results = db.execute(query, params)
        deviation_stocks = []

        for row in results:
            ticker, ma_value, close, volume, stock_name = row

            if (
                ma_value is None
                or not isinstance(ma_value, (int, float))
                or ma_value <= 0
            ):
                continue

            # 편차 계산
            deviation = ((close - ma_value) / ma_value) * 100

            # 조건 확인
            is_match = False
            if condition.upper() == "ABOVE":
                is_match = deviation >= deviation_percent
            elif condition.upper() == "BELOW":
                is_match = deviation <= -deviation_percent
            elif condition.upper() == "ABSOLUTE":
                is_match = abs(deviation) >= deviation_percent

            if is_match:
                deviation_stocks.append(
                    {
                        "name": stock_name,
                        "close": close,
                        "ma_value": round(ma_value, 2),
                        "deviation": round(deviation, 2),
                        "condition": condition.lower(),
                    }
                )

        # 편차 기준으로 정렬 (ABOVE는 내림차순, BELOW는 오름차순)
        if condition.upper() == "ABOVE":
            deviation_stocks.sort(key=lambda x: x["deviation"], reverse=True)
        elif condition.upper() == "BELOW":
            deviation_stocks.sort(key=lambda x: x["deviation"])
        else:  # ABSOLUTE
            deviation_stocks.sort(key=lambda x: abs(x["deviation"]), reverse=True)

        # 표준화된 응답 생성 (정렬 정보 포함)
        sort_key = "deviation"
        if condition.upper() == "ABOVE":
            reverse = True
        elif condition.upper() == "BELOW":
            reverse = False
        else:  # ABSOLUTE
            reverse = True

        return create_result_response(
            data=deviation_stocks,
            total_count=len(deviation_stocks),
            indicator_type="MA_DEVIATION",
            requested_count=count,
            sort_key=sort_key,
            reverse=reverse,
            date=date,
            ma_period=ma_period,
            deviation_percent=deviation_percent,
            condition=condition,
        )

    except Exception as e:
        return {"error": f"이동평균 편차 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()


# 거래량 편차 검색 도구
class VolumeDeviationInput(BaseModel):
    start_date: Optional[str] = Field(
        None, description="시작 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    end_date: Optional[str] = Field(
        None, description="종료 날짜 (YYYY-MM-DD) - 기간 조회 시 사용"
    )
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD) - 단일 날짜 조회 시 사용"
    )
    volume_ma_period: int = Field(
        default=20, description="거래량 이동평균 기간 (5, 20, 60)"
    )
    deviation_percent: float = Field(default=100.0, description="편차 기준 퍼센트 (%)")
    condition: str = Field(
        default="ABOVE", description="조건 타입 (ABOVE: 평균 이상, BELOW: 평균 이하)"
    )
    count: Optional[int] = Field(default=None, description="반환할 결과 개수")
    
    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d",  "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")



@tool(args_schema=VolumeDeviationInput)
def get_volume_deviation_stocks(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    volume_ma_period: int = 20,
    deviation_percent: float = 100.0,
    condition: str = "ABOVE",
    count: Optional[int] = None,
):
    """
    특정 날짜 또는 기간에 거래량이 이동평균 대비 편차가 있는 종목들을 조회합니다.
    """
    db = SqliteDBClient()
    try:
        # 날짜 조건 결정 (기간 또는 단일 날짜)
        if start_date and end_date:
            # 기간 조회
            date_condition = "ts.date BETWEEN ? AND ?"
            params = [start_date, end_date]
        elif date:
            # 단일 날짜 조회
            date_condition = "ts.date = ?"
            params = [date]
        else:
            return create_result_response(
                data=[],
                total_count=0,
                indicator_type="VOLUME_DEVIATION",
                requested_count=count,
            )

        # 거래량 이동평균 기간에 따른 지표명 매핑
        volume_ma_map = {5: "VOLUME_MA_5", 20: "VOLUME_MA_20", 60: "VOLUME_MA_60"}

        if volume_ma_period not in volume_ma_map:
            return {
                "error": f"지원하지 않는 거래량 이동평균 기간입니다: {volume_ma_period}. 지원 기간: 5, 20, 60"
            }

        indicator = volume_ma_map[volume_ma_period]

        # 거래량 편차 계산을 위한 쿼리
        query = f"""
        SELECT ts.ticker, ts.value as volume_ma, o.volume as current_volume, o.close, s.name
        FROM technical_signals ts
        JOIN ohlcv o ON ts.ticker = o.ticker AND ts.date = o.date
        JOIN stocks s ON ts.ticker = s.ticker
        WHERE {date_condition} AND ts.indicator = ?
        AND o.volume > 0 AND ts.value > 0
        """

        params.append(indicator)
        results = db.execute(query, params)
        deviation_stocks = []

        for row in results:
            ticker, volume_ma, current_volume, close, stock_name = row

            if volume_ma is None or current_volume is None:
                continue

            # 거래량 편차 계산
            volume_ratio = current_volume / volume_ma
            deviation = (volume_ratio - 1) * 100  # 퍼센트로 변환

            # 조건에 따른 필터링
            is_match = False
            if condition.upper() == "ABOVE":
                is_match = deviation >= deviation_percent
            elif condition.upper() == "BELOW":
                is_match = deviation <= -deviation_percent

            if is_match:
                deviation_stocks.append(
                    {
                        "name": stock_name,
                        "close": close,
                        "current_volume": current_volume,
                        "volume_ma": round(volume_ma, 0),
                        "deviation_percent": round(deviation, 2),
                        "volume_ratio": round(volume_ratio, 2),
                    }
                )

        # 편차율 기준으로 정렬 (높은 편차가 상위)
        if condition.upper() == "ABOVE":
            deviation_stocks.sort(key=lambda x: x["deviation_percent"], reverse=True)
        else:
            deviation_stocks.sort(key=lambda x: x["deviation_percent"])

        # 표준화된 응답 생성 (정렬 정보 포함)
        sort_key = "deviation_percent"
        reverse = condition.upper() == "ABOVE"

        return create_result_response(
            data=deviation_stocks,
            total_count=len(deviation_stocks),
            indicator_type="VOLUME_DEVIATION",
            requested_count=count,
            sort_key=sort_key,
            reverse=reverse,
            date=date,
            volume_ma_period=volume_ma_period,
            deviation_percent=deviation_percent,
            condition=condition,
        )

    except Exception as e:
        return {"error": f"거래량 편차 조회 중 오류 발생: {str(e)}"}
    finally:
        db.close()
