from datetime import datetime, date, timedelta
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from langchain.tools import tool
import yfinance as yf
import pandas as pd
from db.sqlite_db import SqliteDBClient
from pykrx import stock as krx
import functools

# 영업일 캐시
_business_days_cache = {}


@functools.lru_cache(maxsize=128)
def get_previous_business_day_cached(target_date: str) -> str:
    """
    주어진 날짜의 직전 영업일을 반환합니다. (캐시 적용)
    """
    try:
        # YYYY-MM-DD를 YYYYMMDD로 변환
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        date_str = date_obj.strftime("%Y%m%d")

        # 캐시에서 확인
        cache_key = f"{date_str}"
        if cache_key in _business_days_cache:
            return _business_days_cache[cache_key]

        # pykrx를 사용해서 영업일 리스트 가져오기 (충분히 넓은 범위)
        start_date = (date_obj - timedelta(days=30)).strftime("%Y%m%d")
        end_date = date_str

        business_days = krx.get_previous_business_days(
            fromdate=start_date, todate=end_date
        )

        if not business_days:
            result = target_date
        else:
            # target_date보다 이전의 가장 최근 영업일 찾기
            target_date_obj = date_obj.date()
            previous_business_day = None

            for business_day in business_days:
                if business_day.date() < target_date_obj:
                    previous_business_day = business_day.date()
                else:
                    break

            if previous_business_day:
                result = previous_business_day.strftime("%Y-%m-%d")
            else:
                result = target_date

        # 캐시에 저장
        _business_days_cache[cache_key] = result
        return result

    except Exception as e:
        # 오류 발생시 단순히 하루 전으로 계산
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
            prev_date = date_obj - timedelta(days=1)
            return prev_date.strftime("%Y-%m-%d")
        except:
            return target_date


def get_previous_business_day(target_date: str) -> str:
    """
    주어진 날짜의 직전 영업일을 반환합니다.
    """
    return get_previous_business_day_cached(target_date)


class PriceRangeInput(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        ..., description="시장 구분 (KOSPI, KOSDAQ, ALL)"
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD 형식)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD 형식)")
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD 형식) - 단일 날짜 조회 시 사용"
    )
    min_price: Optional[float] = Field(None, description="최소 주가 (원)")
    max_price: Optional[float] = Field(None, description="최대 주가 (원)")
    order_by_col: Literal["close"] = Field(
        "close", description="정렬 기준 컬럼 (close: 종가)"
    )
    order_by: Literal["ASC", "DESC"] = Field(
        "DESC", description="정렬 방향 (ASC: 오름차순, DESC: 내림차순)"
    )

    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")


@tool(args_schema=PriceRangeInput)
def get_stocks_by_price_range(
    market: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    order_by_col: Literal["close"] = "close",
    order_by: Literal["ASC", "DESC"] = "DESC",
) -> dict:
    """
    특정 날짜 또는 기간에 주어진 가격 범위에 해당하는 종목들을 조회합니다.
    """
    db_client = SqliteDBClient()

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
        return {"results": [], "total_count": 0}

    # 시장별 종목 필터링
    market_filter = ""
    if market == "KOSPI":
        market_filter = "AND s.market = ?"
        params.append("KOSPI")
    elif market == "KOSDAQ":
        market_filter = "AND s.market = ?"
        params.append("KOSDAQ")

    # 가격 조건 구성
    price_conditions = []
    if min_price is not None:
        price_conditions.append("o.close >= ?")
        params.append(min_price)
    if max_price is not None:
        price_conditions.append("o.close <= ?")
        params.append(max_price)

    price_filter = " AND ".join(price_conditions) if price_conditions else "1=1"

    query = f"""
        SELECT s.name, o.close
        FROM stocks s
        JOIN ohlcv o ON s.ticker = o.ticker
        WHERE {date_condition} {market_filter} AND {price_filter}
        ORDER BY o.{order_by_col} {order_by}
    """

    results, columns = db_client.fetch_query(query, params=params)

    if results and columns:
        all_results = []
        seen_stocks = set()  # 중복 제거를 위한 set

        for row in results:
            row_dict = dict(zip(columns, row))
            stock_name = row_dict.get("name")

            # 중복 제거: 각 종목은 한 번만 표시 (최신 데이터)
            if stock_name in seen_stocks:
                continue
            seen_stocks.add(stock_name)

            # close를 float로 변환하여 일관성 확보
            if row_dict.get("close") is not None:
                try:
                    row_dict["close"] = float(row_dict["close"])
                except (ValueError, TypeError):
                    row_dict["close"] = 0.0
            else:
                row_dict["close"] = 0.0
            all_results.append(row_dict)

        # 최종 정렬 (가격 기준)
        if order_by == "ASC":
            all_results.sort(key=lambda x: x["close"])
        else:
            all_results.sort(key=lambda x: x["close"], reverse=True)

        return {"results": all_results[:10], "total_count": len(all_results)}
    return {"results": [], "total_count": 0}


class VolumeThresholdInput(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        ..., description="시장 구분 (KOSPI, KOSDAQ, ALL)"
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD 형식)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD 형식)")
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD 형식) - 단일 날짜 조회 시 사용"
    )
    min_volume: Optional[int] = Field(
        0, description="최소 거래량 (주), 0으로 설정하면 모든 종목 조회"
    )
    order_by_col: Literal["volume"] = Field(
        "volume", description="정렬 기준 컬럼 (volume: 거래량)"
    )
    order_by: Literal["ASC", "DESC"] = Field(
        "DESC", description="정렬 방향 (ASC: 오름차순, DESC: 내림차순)"
    )

    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")


@tool(args_schema=VolumeThresholdInput)
def get_stocks_by_volume(
    market: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    min_volume: Optional[int] = 0,
    order_by_col: Literal["volume"] = "volume",
    order_by: Literal["ASC", "DESC"] = "DESC",
) -> dict:
    """
    특정 날짜 또는 기간에 거래량이 기준 이상인 종목들을 조회합니다.
    """
    db_client = SqliteDBClient()

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
        return {"results": [], "total_count": 0}

    # 시장별 종목 필터링
    market_filter = ""
    if market == "KOSPI":
        market_filter = "AND s.market = ?"
        params.append("KOSPI")
    elif market == "KOSDAQ":
        market_filter = "AND s.market = ?"
        params.append("KOSDAQ")

    # 거래량 조건 구성
    volume_condition = ""
    if min_volume is not None and min_volume > 0:
        volume_condition = "AND o.volume >= ?"
        params.append(min_volume)

    query = f"""
        SELECT s.name, o.close, o.volume
        FROM stocks s
        JOIN ohlcv o ON s.ticker = o.ticker
        WHERE {date_condition} {market_filter} {volume_condition}
        ORDER BY o.{order_by_col} {order_by}
    """

    print(f"=========================== get_stocks_by_volume 쿼리: {query} == {params}")
    results, columns = db_client.fetch_query(query, params=params)

    if results and columns:
        all_results = []
        for row in results:
            row_dict = dict(zip(columns, row))
            # 데이터 타입 변환하여 일관성 확보
            if row_dict.get("close") is not None:
                try:
                    row_dict["close"] = float(row_dict["close"])
                except (ValueError, TypeError):
                    row_dict["close"] = 0.0
            else:
                row_dict["close"] = 0.0

            if row_dict.get("volume") is not None:
                try:
                    row_dict["volume"] = int(row_dict["volume"])
                except (ValueError, TypeError):
                    row_dict["volume"] = 0
            else:
                row_dict["volume"] = 0

            all_results.append(row_dict)

        return {"results": all_results[:10], "total_count": len(all_results)}
    return {"results": [], "total_count": 0}


class ChangeRateInput(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        ..., description="시장 구분 (KOSPI, KOSDAQ, ALL)"
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD 형식)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD 형식)")
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD 형식) - 단일 날짜 조회 시 사용"
    )
    min_change_rate: Optional[float] = Field(None, description="최소 등락률 (%)")
    max_change_rate: Optional[float] = Field(None, description="최대 등락률 (%)")
    order_by: Literal["ASC", "DESC"] = Field(
        "DESC", description="정렬 방향 (ASC: 오름차순, DESC: 내림차순)"
    )

    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")


@tool(args_schema=ChangeRateInput)
def get_stocks_by_change_rate(
    market: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    min_change_rate: Optional[float] = None,
    max_change_rate: Optional[float] = None,
    order_by: Literal["ASC", "DESC"] = "DESC",
) -> dict:
    """
    특정 날짜 또는 기간에 등락률이 기준 범위에 해당하는 종목들을 조회합니다.
    """
    db_client = SqliteDBClient()

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
        return {"results": [], "total_count": 0}

    # 시장별 종목 필터링
    market_filter = ""
    if market == "KOSPI":
        market_filter = "AND s.market = ?"
        params.append("KOSPI")
    elif market == "KOSDAQ":
        market_filter = "AND s.market = ?"
        params.append("KOSDAQ")

    # 등락률 조건 구성
    change_conditions = []
    if min_change_rate is not None:
        change_conditions.append("o.change_rate >= ?")
        params.append(min_change_rate)
    if max_change_rate is not None:
        change_conditions.append("o.change_rate <= ?")
        params.append(max_change_rate)

    # 단일 날짜 조회 시 등락률 절댓값 30% 제한 적용 (한국 주식시장 일일 등락률 제한)
    if date and not (start_date and end_date):
        change_conditions.append("ABS(o.change_rate) <= 30")
        # 파라미터는 추가하지 않음 (상수 조건이므로)

    change_filter = " AND ".join(change_conditions) if change_conditions else "1=1"

    # 하락률 높은 종목 조회 시 절댓값 기준 정렬
    if order_by == "DESC" and max_change_rate is not None and max_change_rate < 0:
        # 하락률 높은 종목은 절댓값이 큰 음수가 상위에 오도록
        order_clause = "ORDER BY ABS(o.change_rate) DESC"
    else:
        order_clause = f"ORDER BY o.change_rate {order_by}"

    query = f"""
        SELECT s.name, o.close, o.change_rate
        FROM stocks s
        JOIN ohlcv o ON s.ticker = o.ticker
        WHERE {date_condition} {market_filter} AND {change_filter} AND o.close > 0
        {order_clause}
    """

    results, columns = db_client.fetch_query(query, params=params)

    if results and columns:
        all_results = []
        for row in results:
            row_dict = dict(zip(columns, row))
            # change_rate를 float로 변환하여 일관성 확보
            if row_dict.get("change_rate") is not None:
                try:
                    row_dict["change_rate"] = float(row_dict["change_rate"])
                except (ValueError, TypeError):
                    row_dict["change_rate"] = 0.0
            else:
                row_dict["change_rate"] = 0.0

            # close도 float로 변환
            if row_dict.get("close") is not None:
                try:
                    row_dict["close"] = float(row_dict["close"])
                except (ValueError, TypeError):
                    row_dict["close"] = 0.0
            else:
                row_dict["close"] = 0.0

            all_results.append(row_dict)

        return {"results": all_results[:10], "total_count": len(all_results)}
    return {"results": [], "total_count": 0}


class VolumeChangeInput(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        ..., description="시장 구분 (KOSPI, KOSDAQ, ALL)"
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD 형식)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD 형식)")
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD 형식) - 단일 날짜 조회 시 사용"
    )
    min_volume_ratio: float = Field(
        ..., description="전일 대비 최소 거래량 비율 (예: 2.0 = 200%)"
    )
    order_by: Literal["ASC", "DESC"] = Field(
        "DESC", description="정렬 방향 (ASC: 오름차순, DESC: 내림차순)"
    )

    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")


@tool(args_schema=VolumeChangeInput)
def get_stocks_by_volume_change(
    market: str,
    min_volume_ratio: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    order_by: Literal["ASC", "DESC"] = "DESC",
) -> dict:
    """
    특정 날짜 또는 기간에 전일 대비 거래량이 기준 비율 이상 증가한 종목들을 조회합니다.
    """
    db_client = SqliteDBClient()

    # 날짜 조건 결정 (기간 또는 단일 날짜)
    if start_date and end_date:
        # 기간 조회 - 기간 내 각 날짜에 대해 조건을 만족하는 종목들을 찾음
        date_condition = "o1.date BETWEEN ? AND ?"
        params = [start_date, end_date, min_volume_ratio]
    elif date:
        # 단일 날짜 조회
        date_condition = "o1.date = ?"
        params = [date, min_volume_ratio]
    else:
        return {"results": [], "total_count": 0}

    # 시장별 종목 필터링
    market_filter = ""
    if market == "KOSPI":
        market_filter = "AND s.market = ?"
        params.append("KOSPI")
    elif market == "KOSDAQ":
        market_filter = "AND s.market = ?"
        params.append("KOSDAQ")

    query = f"""
        SELECT s.name, s.market, 
               o1.close, o1.change_rate,
               o1.volume as current_volume,
               o2.volume as prev_volume,
               CAST(o1.volume AS FLOAT) / CAST(o2.volume AS FLOAT) as volume_ratio
        FROM stocks s
        JOIN ohlcv o1 ON s.ticker = o1.ticker AND {date_condition}
        JOIN ohlcv o2 ON s.ticker = o2.ticker AND o2.date = (
            SELECT MAX(o3.date) 
            FROM ohlcv o3 
            WHERE o3.ticker = s.ticker AND o3.date < o1.date
        )
        WHERE o2.volume > 0 
        AND (CAST(o1.volume AS FLOAT) / CAST(o2.volume AS FLOAT)) >= ?
        {market_filter}
        ORDER BY volume_ratio {order_by}
    """

    results, columns = db_client.fetch_query(query, params=params)

    if results and columns:
        all_results = []
        for row in results:
            row_dict = dict(zip(columns, row))
            # 데이터 타입 변환하여 일관성 확보
            if row_dict.get("current_volume") is not None:
                try:
                    row_dict["current_volume"] = int(row_dict["current_volume"])
                except (ValueError, TypeError):
                    row_dict["current_volume"] = 0
            else:
                row_dict["current_volume"] = 0

            if row_dict.get("prev_volume") is not None:
                try:
                    row_dict["prev_volume"] = int(row_dict["prev_volume"])
                except (ValueError, TypeError):
                    row_dict["prev_volume"] = 0
            else:
                row_dict["prev_volume"] = 0

            if row_dict.get("volume_ratio") is not None:
                try:
                    volume_ratio = float(row_dict["volume_ratio"])
                    # 백분율 계산 (예: 2.0 -> 100%, 3.0 -> 200%, 14.4 -> 1340%)
                    volume_change_percent = (volume_ratio - 1) * 100
                    # volume_ratio를 백분율로 대체
                    row_dict["volume_change_percent"] = volume_change_percent
                    # volume_ratio 필드 제거 (혼란 방지)
                    if "volume_ratio" in row_dict:
                        del row_dict["volume_ratio"]
                except (ValueError, TypeError):
                    row_dict["volume_change_percent"] = 0.0
                    if "volume_ratio" in row_dict:
                        del row_dict["volume_ratio"]
            else:
                row_dict["volume_change_percent"] = 0.0

            all_results.append(row_dict)

        return {"results": all_results[:10], "total_count": len(all_results)}
    return {"results": [], "total_count": 0}


class CombinedConditionInput(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        ..., description="시장 구분 (KOSPI, KOSDAQ, ALL)"
    )
    start_date: Optional[str] = Field(None, description="시작 날짜 (YYYY-MM-DD 형식)")
    end_date: Optional[str] = Field(None, description="종료 날짜 (YYYY-MM-DD 형식)")
    date: Optional[str] = Field(
        None, description="조회 날짜 (YYYY-MM-DD 형식) - 단일 날짜 조회 시 사용"
    )
    min_price: Optional[float] = Field(None, description="최소 주가 (원)")
    max_price: Optional[float] = Field(None, description="최대 주가 (원)")
    min_volume: Optional[int] = Field(None, description="최소 거래량 (주)")
    max_volume: Optional[int] = Field(None, description="최대 거래량 (주)")
    min_change_rate: Optional[float] = Field(None, description="최소 등락률 (%)")
    max_change_rate: Optional[float] = Field(None, description="최대 등락률 (%)")
    min_volume_ratio: Optional[float] = Field(
        None, description="전일 대비 최소 거래량 비율"
    )
    order_by_col: Optional[Literal["change_rate", "volume", "close"]] = Field(
        None, description="정렬 기준 컬럼 (change_rate, volume, close)"
    )
    order_by: Literal["ASC", "DESC"] = Field(
        "DESC", description="정렬 방향 (ASC: 오름차순, DESC: 내림차순)"
    )

    @field_validator("start_date", "end_date", "date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")


@tool(args_schema=CombinedConditionInput)
def get_stocks_by_combined_conditions(
    market: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    date: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_volume: Optional[int] = None,
    max_volume: Optional[int] = None,
    min_change_rate: Optional[float] = None,
    max_change_rate: Optional[float] = None,
    min_volume_ratio: Optional[float] = None,
    order_by_col: Optional[Literal["change_rate", "volume", "close"]] = None,
    order_by: Literal["ASC", "DESC"] = "DESC",
) -> dict:
    """
    여러 조건을 조합하여 종목들을 필터링합니다. 기간 또는 단일 날짜 조회를 지원합니다.
    """
    db_client = SqliteDBClient()

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
        return {"results": [], "total_count": 0}

    # 시장별 종목 필터링
    market_filter = ""
    if market == "KOSPI":
        market_filter = "s.market = ?"
        params.append("KOSPI")
    elif market == "KOSDAQ":
        market_filter = "s.market = ?"
        params.append("KOSDAQ")

    # 조건들 구성
    conditions = []
    select_columns = ["s.name", "s.market", "o.close"]
    has_change_rate = False
    has_volume = False

    # 가격 조건이 있으면 close 컬럼 추가
    if min_price is not None:
        conditions.append("o.close >= ?")
        params.append(min_price)
    if max_price is not None:
        conditions.append("o.close <= ?")
        params.append(max_price)

    # 거래량 조건이 있으면 volume 컬럼 추가
    if min_volume is not None or max_volume is not None:
        select_columns.append("o.volume")
        has_volume = True
        if min_volume is not None:
            conditions.append("o.volume >= ?")
            params.append(min_volume)
        if max_volume is not None:
            conditions.append("o.volume <= ?")
            params.append(max_volume)

    # 등락률 조건이 있으면 change_rate 컬럼 추가
    if min_change_rate is not None or max_change_rate is not None:
        select_columns.append("o.change_rate")
        has_change_rate = True
        if min_change_rate is not None:
            conditions.append("o.change_rate >= ?")
            params.append(min_change_rate)
        if max_change_rate is not None:
            conditions.append("o.change_rate <= ?")
            params.append(max_change_rate)

    # 정렬 컬럼 자동 결정
    auto_order_by_col = "close"
    if order_by_col is not None:
        final_order_by_col = order_by_col
    elif has_change_rate:
        final_order_by_col = "change_rate"
    elif has_volume:
        final_order_by_col = "volume"
    else:
        final_order_by_col = "close"

    # 거래량 비율 조건이 있는 경우 전일 데이터와 조인
    if min_volume_ratio is not None:
        # 거래량 비율 조건은 단일 날짜 조회만 지원
        if not date:
            return {
                "results": [],
                "total_count": 0,
                "error": "거래량 비율 조건은 단일 날짜 조회만 지원합니다.",
            }

        # 직전 영업일 계산
        prev_date = get_previous_business_day(date)

        if prev_date == date:
            return {"results": [], "total_count": 0}  # 직전 영업일을 찾을 수 없는 경우

        # 거래량 관련 컬럼들 추가
        select_columns.extend(
            [
                "o.volume as current_volume",
                "o2.volume as prev_volume",
                "CAST(o.volume AS FLOAT) / CAST(o2.volume AS FLOAT) as volume_ratio",
            ]
        )

        conditions.append("o2.volume > 0")
        conditions.append("(CAST(o.volume AS FLOAT) / CAST(o2.volume AS FLOAT)) >= ?")
        params.append(min_volume_ratio)

        # params에 prev_date 추가
        params.insert(1, prev_date)

        # WHERE 절 구성
        where_conditions = []
        if market_filter:
            where_conditions.append(market_filter)
        if conditions:
            where_conditions.extend(conditions)
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT {', '.join(select_columns)}
            FROM stocks s
            JOIN ohlcv o ON s.ticker = o.ticker AND o.date = ?
            JOIN ohlcv o2 ON s.ticker = o2.ticker AND o2.date = ?
            WHERE {where_clause}
            ORDER BY o.{final_order_by_col} {order_by}
        """
    else:
        # 기간 또는 단일 날짜 조건 사용
        # WHERE 절 구성 - 조건들이 있을 때 AND 추가
        where_conditions = [date_condition]
        if market_filter:
            where_conditions.append(market_filter)
        if conditions:
            where_conditions.extend(conditions)
        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT {', '.join(select_columns)}
            FROM stocks s
            JOIN ohlcv o ON s.ticker = o.ticker
            WHERE {where_clause}
            ORDER BY o.{final_order_by_col} {order_by}
        """

    print(f"======= 생성된 쿼리 ==========")
    print(query)
    print(f"======= 파라미터 ==========")
    print(params)
    results, columns = db_client.fetch_query(query, params=params)

    if results and columns:
        all_results = []
        for row in results:
            row_dict = dict(zip(columns, row))

            # 거래량 비율이 있는 경우 백분율 계산 추가
            if "volume_ratio" in row_dict and row_dict.get("volume_ratio") is not None:
                try:
                    volume_ratio = float(row_dict["volume_ratio"])
                    # 백분율 계산 (예: 2.0 -> 100%, 3.0 -> 200%, 14.4 -> 1340%)
                    volume_change_percent = (volume_ratio - 1) * 100
                    # volume_ratio를 백분율로 대체
                    row_dict["volume_change_percent"] = volume_change_percent
                    # volume_ratio 필드 제거 (혼란 방지)
                    del row_dict["volume_ratio"]
                except (ValueError, TypeError):
                    row_dict["volume_change_percent"] = 0.0
                    if "volume_ratio" in row_dict:
                        del row_dict["volume_ratio"]

            all_results.append(row_dict)

        return {"results": all_results[:10], "total_count": len(all_results)}
    return {"results": [], "total_count": 0}


class TopStocksInput(BaseModel):
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        ..., description="시장 구분 (KOSPI, KOSDAQ, ALL)"
    )
    date: str = Field(..., description="조회 날짜 (YYYY-MM-DD 형식)")
    top_n: int = Field(default=1, description="상위 몇 개 종목 (기본값: 1)")
    order_by: Literal["close", "volume", "change_rate"] = Field(
        default="close",
        description="정렬 기준 (close: 종가, volume: 거래량, change_rate: 등락률)",
    )
    order_direction: Literal["ASC", "DESC"] = Field(
        default="DESC", description="정렬 방향 (ASC: 오름차순, DESC: 내림차순)"
    )

    @field_validator("date", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None:
            return v
        formats = ["%Y-%m-%d", "%Y%m%d"]
        for fmt in formats:
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"날짜 변환 실패: {v}")


@tool(args_schema=TopStocksInput)
def get_top_stocks_by_price(
    market: str,
    date: str,
    top_n: int = 1,
    order_by: Literal["close", "volume", "change_rate"] = "close",
    order_direction: Literal["ASC", "DESC"] = "DESC",
) -> dict:
    """
    특정 시장에서 종가/거래량/등락률 기준 상위 N개 종목을 조회합니다.
    """
    db_client = SqliteDBClient()

    # 시장별 종목 필터링
    market_filter = ""
    params = [date]

    if market == "KOSPI":
        market_filter = "AND s.market = ?"
        params.append("KOSPI")
    elif market == "KOSDAQ":
        market_filter = "AND s.market = ?"
        params.append("KOSDAQ")

    # 정렬 기준에 따른 컬럼 선택
    if order_by == "close":
        select_columns = ["s.name", "s.market", "o.close", "o.volume", "o.change_rate"]
    elif order_by == "volume":
        select_columns = ["s.name", "s.market", "o.close", "o.volume", "o.change_rate"]
    elif order_by == "change_rate":
        select_columns = ["s.name", "s.market", "o.close", "o.volume", "o.change_rate"]
    else:
        select_columns = ["s.name", "s.market", "o.close", "o.volume", "o.change_rate"]

    query = f"""
        SELECT {', '.join(select_columns)}
        FROM stocks s
        JOIN ohlcv o ON s.ticker = o.ticker
        WHERE o.date = ? {market_filter} AND o.{order_by} IS NOT NULL
        ORDER BY o.{order_by} {order_direction}
        LIMIT ?
    """

    params.append(top_n)

    results, columns = db_client.fetch_query(query, params=params)

    if results and columns:
        all_results = []
        for row in results:
            row_dict = dict(zip(columns, row))

            # 데이터 타입 변환하여 일관성 확보
            if row_dict.get("close") is not None:
                try:
                    row_dict["close"] = float(row_dict["close"])
                except (ValueError, TypeError):
                    row_dict["close"] = 0.0
            else:
                row_dict["close"] = 0.0

            if row_dict.get("volume") is not None:
                try:
                    row_dict["volume"] = int(row_dict["volume"])
                except (ValueError, TypeError):
                    row_dict["volume"] = 0
            else:
                row_dict["volume"] = 0

            if row_dict.get("change_rate") is not None:
                try:
                    row_dict["change_rate"] = float(row_dict["change_rate"])
                except (ValueError, TypeError):
                    row_dict["change_rate"] = 0.0
            else:
                row_dict["change_rate"] = 0.0

            all_results.append(row_dict)

        return {"results": all_results, "total_count": len(all_results)}
    return {"results": [], "total_count": 0}


if __name__ == "__main__":
    # 테스트
    print("가격 범위 검색 테스트:")
    result = get_stocks_by_price_range.invoke(
        {
            "market": "KOSPI",
            "date": "2024-11-04",
            "min_price": 10000,
            "max_price": 50000,
        }
    )
    print(result[:3])
    print("")  # 처음 3개만 출력

    print("거래량 검색 테스트:")
    result = get_stocks_by_volume.invoke(
        {"market": "KOSPI", "date": "2024-11-04", "min_volume": 1000000}
    )
    print(result[:3])

    print("거래량 비율 검색 테스트:")
    result = get_stocks_by_volume_change.invoke(
        {"market": "KOSPI", "date": "2024-11-04", "min_volume_ratio": 2.0}
    )
    print(result[:3])

    print("조합 조건 검색 테스트 (등락률 상승):")
    result = get_stocks_by_combined_conditions.invoke(
        {
            "market": "KOSPI",
            "date": "2024-11-04",
            "min_volume_ratio": 2.0,
            "min_change_rate": 3.0,
        }
    )
    print(f"등락률 3% 이상 + 거래량 200% 이상 증가: {len(result['results'])}개")

    print("조합 조건 검색 테스트 (등락률 하락):")
    result = get_stocks_by_combined_conditions.invoke(
        {
            "market": "KOSPI",
            "date": "2024-11-04",
            "max_change_rate": -3.0,
            "min_volume": 1000000,
        }
    )
    print(f"등락률 -3% 이하 + 거래량 100만주 이상: {len(result['results'])}개")

    print("등락률 범위 검색 테스트:")
    result = get_stocks_by_change_rate.invoke(
        {
            "market": "KOSPI",
            "date": "2024-11-04",
            "min_change_rate": -5.0,
            "max_change_rate": -2.0,
        }
    )
    print(f"등락률 -5% ~ -2% 범위: {len(result)}개")
