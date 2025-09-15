from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from langchain.tools import tool
from db.sqlite_db import SqliteDBClient
import yfinance as yf


# Input schema
class HistoricalDataInput(BaseModel):
    ticker: str = Field(
        ...,
        description="The ticker symbol of the stock to fetch historical data for (e.g., 005930.KS, 419120.KQ)",
    )
    start_date: str = Field(
        ..., description="Start date in YYYY-MM-DD format (inclusive)"
    )
    end_date: Optional[str] = Field(
        None,
        description="End date in YYYY-MM-DD format (inclusive). If not provided, only start_date data will be returned.",
    )

    @field_validator("start_date", "end_date", mode="before")
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


@tool(args_schema=HistoricalDataInput)
def get_historical_data(
    ticker: str,
    start_date: str,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    로컬 데이터베이스에서 특정 종목의 과거 주가 데이터를 조회합니다.

    Args:
        ticker: 종목 티커 (예: 005930.KS, 419120.KQ)
        start_date: 시작 날짜 (YYYY-MM-DD 형식, inclusive)
        end_date: 종료 날짜 (YYYY-MM-DD 형식, inclusive). 미지정시 start_date만 조회

    Returns:
        조회된 데이터 딕셔너리 또는 에러 메시지
        항상 일관된 구조로 반환: 시가, 고가, 저가, 종가, 거래량, 등락률, 거래대금, 날짜
    """
    db_client = SqliteDBClient()

    try:
        # 기본 쿼리 구성
        if end_date:
            # 날짜 범위 조회
            query = """
                SELECT date, open, high, low, close, volume, value, change_rate
                FROM ohlcv 
                WHERE ticker = ? AND date BETWEEN ? AND ?
                ORDER BY date
            """
            params = [ticker, start_date, end_date]
        else:
            # 단일 날짜 조회
            query = """
                SELECT date, open, high, low, close, volume, value, change_rate
                FROM ohlcv 
                WHERE ticker = ? AND date = ?
            """
            params = [ticker, start_date]

        results, columns = db_client.fetch_query(query, params)

        if not results:
            return {"error": f"No historical data found for {ticker} on {start_date}"}

        # 결과 처리
        if end_date and end_date != start_date:
            # 실제 날짜 범위 조회 - 여러 날짜 데이터 반환
            formatted_results = []
            for row in results:
                row_dict = dict(zip(columns, row))
                formatted_row = _format_row_data(row_dict)
                formatted_results.append(formatted_row)

            return {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "results": formatted_results,
                "count": len(formatted_results),
            }
        else:
            # 단일 날짜 조회 (end_date가 없거나 start_date와 동일한 경우)
            # 첫 번째 결과만 반환하되, 일관된 구조로 반환
            row_dict = dict(zip(columns, results[0]))
            formatted_result = _format_row_data(row_dict)

            return {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": start_date,  # 단일 날짜이므로 end_date도 동일
                "results": [
                    formatted_result
                ],  # 단일 결과를 배열로 감싸서 일관된 구조 유지
                "count": 1,
            }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db_client.close()


def _format_row_data(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    데이터베이스 결과를 일관된 형태로 포맷팅합니다.
    항상 모든 필드를 포함하여 반환합니다.
    """
    # 모든 데이터를 포함하여 일관된 구조로 반환
    formatted = {
        "시가": (
            float(row_dict.get("open", 0)) if row_dict.get("open") is not None else 0
        ),
        "고가": (
            float(row_dict.get("high", 0)) if row_dict.get("high") is not None else 0
        ),
        "저가": float(row_dict.get("low", 0)) if row_dict.get("low") is not None else 0,
        "종가": (
            float(row_dict.get("close", 0)) if row_dict.get("close") is not None else 0
        ),
        "거래량": (
            int(row_dict.get("volume", 0)) if row_dict.get("volume") is not None else 0
        ),
        "등락률": (
            round(float(row_dict.get("change_rate", 0)), 2)
            if row_dict.get("change_rate") is not None
            else 0
        ),
        "거래대금": (
            int(row_dict.get("value", 0)) if row_dict.get("value") is not None else 0
        ),
        "날짜": row_dict.get("date", ""),
    }

    return formatted


# 새로운 함수들 추가


class StockRankingInput(BaseModel):
    ticker: str = Field(..., description="종목 티커 (예: 005930.KS, 419120.KQ)")
    date: str = Field(..., description="조회 날짜 (YYYY-MM-DD 형식)")
    market: str = Field(default="ALL", description="시장 구분 (KOSPI, KOSDAQ, ALL)")
    rank_by: str = Field(
        default="volume",
        description="순위 기준 (volume: 거래량, close: 종가, change_rate: 등락률)",
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


@tool(args_schema=StockRankingInput)
def get_stock_ranking(
    ticker: str, date: str, market: str = "ALL", rank_by: str = "volume"
) -> Dict[str, Any]:
    """
    특정 종목의 시장 순위를 조회합니다.

    Args:
        ticker: 종목 티커
        date: 조회 날짜 (YYYY-MM-DD 형식)
        market: 시장 구분 (KOSPI, KOSDAQ, ALL)
        rank_by: 순위 기준 (volume, close, change_rate)

    Returns:
        종목의 순위 정보와 해당 지표값
    """
    db_client = SqliteDBClient()

    try:
        # 1. 해당 종목의 데이터 조회
        stock_query = """
            SELECT o.close, o.volume, o.change_rate, s.name
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.ticker = ? AND o.date = ?
        """
        stock_result, _ = db_client.fetch_query(stock_query, [ticker, date])

        if not stock_result:
            return {"error": f"No data found for {ticker} on {date}"}

        stock_data = stock_result[0]
        stock_name = stock_data[3]

        # 2. 시장 전체 데이터 조회하여 순위 계산
        market_condition = ""
        if market == "KOSPI":
            market_condition = "AND s.market = 'KOSPI'"
        elif market == "KOSDAQ":
            market_condition = "AND s.market = 'KOSDAQ'"

        rank_column_map = {
            "volume": "o.volume",
            "close": "o.close",
            "change_rate": "o.change_rate",
        }

        rank_column = rank_column_map.get(rank_by, "o.volume")

        ranking_query = f"""
            SELECT o.ticker, {rank_column}, s.name
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.date = ? {market_condition}
            AND o.volume > 0
            ORDER BY {rank_column} DESC
        """

        all_results, _ = db_client.fetch_query(ranking_query, [date])

        if not all_results:
            return {"error": f"No market data found for {date}"}

        # 3. 순위 계산
        target_value = (
            stock_data[0]
            if rank_by == "close"
            else stock_data[1] if rank_by == "volume" else stock_data[2]
        )
        rank = 1

        for row in all_results:
            if row[0] == ticker:
                break
            rank += 1

        total_stocks = len(all_results)

        return {
            "ticker": ticker,
            "stock_name": stock_name,
            "date": date,
            "market": market,
            "rank_by": rank_by,
            "rank": rank,
            "total_stocks": total_stocks,
            "value": target_value,
            "percentage": round((rank / total_stocks) * 100, 2),
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db_client.close()


class StockComparisonInput(BaseModel):
    tickers: List[str] = Field(
        ..., description="비교할 종목 티커 리스트 (예: ['005930.KS', '035420.KS'])"
    )
    date: str = Field(..., description="조회 날짜 (YYYY-MM-DD 형식)")
    compare_by: List[str] = Field(
        default=["close", "volume", "change_rate"],
        description="비교 기준 리스트 (close, volume, change_rate, value, market_cap)",
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


@tool(args_schema=StockComparisonInput)
def get_stock_comparison(
    tickers: List[str],
    date: str,
    compare_by: List[str] = ["close", "volume", "change_rate", "market_cap"],
) -> Dict[str, Any]:
    """
    여러 종목을 지정된 지표로 비교 분석합니다.

    Args:
        tickers: 비교할 종목 티커 리스트
        date: 조회 날짜 (YYYY-MM-DD 형식)
        compare_by: 비교 기준 리스트 (close, volume, change_rate, value, market_cap)

    Returns:
        종목별 비교 결과와 우위 분석
    """
    db_client = SqliteDBClient()

    try:
        # 시가총액 비교가 포함된 경우 yfinance로 시가총액 데이터 조회
        market_cap_data = {}
        if "market_cap" in compare_by:
            for ticker in tickers:
                try:
                    # yfinance로 해당 날짜의 시가총액 조회
                    stock = yf.Ticker(ticker)
                    # end_date는 exclusive이므로 다음날로 설정
                    end_date = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
                    end_date_str = end_date.strftime("%Y-%m-%d")

                    hist = stock.history(start=date, end=end_date_str)
                    if not hist.empty:
                        # 시가총액 = 주가 * 발행주식수
                        close_price = hist.iloc[-1]["Close"]
                        shares = stock.info.get("sharesOutstanding", 0)
                        market_cap = close_price * shares if shares > 0 else 0
                        market_cap_data[ticker] = market_cap
                    else:
                        market_cap_data[ticker] = 0
                except Exception as e:
                    print(f"Error fetching market cap for {ticker}: {e}")
                    market_cap_data[ticker] = 0

        # 1. 모든 종목의 데이터 조회 (시가총액 제외)
        placeholders = ",".join(["?" for _ in tickers])
        query = f"""
            SELECT o.ticker, o.close, o.volume, o.change_rate, o.value, s.name
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.ticker IN ({placeholders}) AND o.date = ?
        """

        results, _ = db_client.fetch_query(query, tickers + [date])

        if not results:
            return {"error": f"No data found for specified tickers on {date}"}

        # 2. 결과 정리
        stock_data = {}
        for row in results:
            ticker, close, volume, change_rate, value, name = row
            stock_data[ticker] = {
                "ticker": ticker,
                "name": name,
                "close": float(close) if close else 0,
                "volume": int(volume) if volume else 0,
                "change_rate": float(change_rate) if change_rate else 0,
                "value": int(value) if value else 0,
            }

            # 시가총액 데이터 추가
            if ticker in market_cap_data:
                stock_data[ticker]["market_cap"] = market_cap_data[ticker]

        # 3. 각 지표별 비교 분석 - 간단한 형태로 반환
        comparison_summary = {}

        for metric in compare_by:
            if metric not in ["close", "volume", "change_rate", "value", "market_cap"]:
                continue

            # 시가총액의 경우 yfinance 데이터만 사용
            if metric == "market_cap":
                available_stocks = {
                    k: v for k, v in stock_data.items() if "market_cap" in v
                }
                if not available_stocks:
                    continue
            else:
                available_stocks = stock_data

            # 해당 지표로 정렬
            sorted_stocks = sorted(
                available_stocks.items(), key=lambda x: x[1][metric], reverse=True
            )

            # 간단한 형태로 요약 정보 생성
            metric_summary = {
                "highest": {
                    "name": sorted_stocks[0][1]["name"],
                    "value": sorted_stocks[0][1][metric],
                    "ticker": sorted_stocks[0][0],
                },
                "lowest": {
                    "name": sorted_stocks[-1][1]["name"],
                    "value": sorted_stocks[-1][1][metric],
                    "ticker": sorted_stocks[-1][0],
                },
                "all_companies": [],
            }

            # 모든 회사 정보 추가
            for ticker, data in sorted_stocks:
                metric_summary["all_companies"].append(
                    {"name": data["name"], "value": data[metric], "ticker": ticker}
                )

            comparison_summary[metric] = metric_summary

        # 4. 간단한 형태로 반환
        return {
            "date": date,
            "comparison_summary": comparison_summary,
            "companies_count": len(stock_data),
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db_client.close()


class MarketAverageComparisonInput(BaseModel):
    ticker: str = Field(..., description="분석할 종목 티커")
    date: str = Field(..., description="조회 날짜 (YYYY-MM-DD 형식)")
    market: str = Field(default="ALL", description="시장 구분 (KOSPI, KOSDAQ, ALL)")
    compare_by: str = Field(
        default="change_rate", description="비교 기준 (change_rate, volume)"
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


@tool(args_schema=MarketAverageComparisonInput)
def get_market_average_comparison(
    ticker: str, date: str, market: str = "ALL", compare_by: str = "change_rate"
) -> Dict[str, Any]:
    """
    특정 종목의 지표를 시장 평균과 비교합니다.

    Args:
        ticker: 분석할 종목 티커
        date: 조회 날짜 (YYYY-MM-DD 형식)
        market: 시장 구분 (KOSPI, KOSDAQ, ALL)
        compare_by: 비교 기준 (change_rate, volume)

    Returns:
        종목 지표와 시장 평균 비교 결과
    """
    db_client = SqliteDBClient()

    try:
        # 1. 해당 종목의 데이터 조회
        stock_query = """
            SELECT o.close, o.volume, o.change_rate, s.name
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.ticker = ? AND o.date = ?
        """
        stock_result, _ = db_client.fetch_query(stock_query, [ticker, date])

        if not stock_result:
            return {"error": f"No data found for {ticker} on {date}"}

        stock_data = stock_result[0]
        stock_name = stock_data[3]
        stock_value = stock_data[2] if compare_by == "change_rate" else stock_data[1]

        # 2. 시장 평균 계산
        market_condition = ""
        if market == "KOSPI":
            market_condition = "AND s.market = 'KOSPI'"
        elif market == "KOSDAQ":
            market_condition = "AND s.market = 'KOSDAQ'"

        metric_column = "o.change_rate" if compare_by == "change_rate" else "o.volume"

        avg_query = f"""
            SELECT AVG({metric_column}) as avg_value, COUNT(*) as total_stocks
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.date = ? {market_condition}
            AND o.volume > 0
        """

        avg_result, _ = db_client.fetch_query(avg_query, [date])

        if not avg_result or avg_result[0][0] is None:
            return {"error": f"No market data found for {date}"}

        market_avg = float(avg_result[0][0])
        total_stocks = int(avg_result[0][1])

        # 3. 비교 분석
        difference = stock_value - market_avg
        percentage_diff = (difference / market_avg * 100) if market_avg != 0 else 0
        is_higher = stock_value > market_avg

        return {
            "ticker": ticker,
            "stock_name": stock_name,
            "date": date,
            "market": market,
            "compare_by": compare_by,
            "stock_value": stock_value,
            "market_average": round(market_avg, 2),
            "difference": round(difference, 2),
            "percentage_difference": round(percentage_diff, 2),
            "is_higher_than_average": is_higher,
            "total_stocks_in_market": total_stocks,
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db_client.close()


class MarketRatioInput(BaseModel):
    ticker: str = Field(..., description="분석할 종목 티커")
    date: str = Field(..., description="조회 날짜 (YYYY-MM-DD 형식)")
    market: str = Field(default="ALL", description="시장 구분 (KOSPI, KOSDAQ, ALL)")
    ratio_by: str = Field(
        default="volume", description="비율 계산 기준 (volume: 거래량, value: 거래대금)"
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


@tool(args_schema=MarketRatioInput)
def get_market_ratio(
    ticker: str, date: str, market: str = "ALL", ratio_by: str = "volume"
) -> Dict[str, Any]:
    """
    특정 종목의 지표가 전체 시장에서 차지하는 비율을 계산합니다.

    Args:
        ticker: 분석할 종목 티커
        date: 조회 날짜 (YYYY-MM-DD 형식)
        market: 시장 구분 (KOSPI, KOSDAQ, ALL)
        ratio_by: 비율 계산 기준 (volume, value)

    Returns:
        종목의 시장 비율 정보
    """
    db_client = SqliteDBClient()

    try:
        # 1. 해당 종목의 데이터 조회
        stock_query = """
            SELECT o.volume, o.value, s.name
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.ticker = ? AND o.date = ?
        """
        stock_result, _ = db_client.fetch_query(stock_query, [ticker, date])

        if not stock_result:
            return {"error": f"No data found for {ticker} on {date}"}

        stock_data = stock_result[0]
        stock_name = stock_data[2]
        stock_value = stock_data[0] if ratio_by == "volume" else stock_data[1]

        # 2. 시장 전체 합계 계산
        market_condition = ""
        if market == "KOSPI":
            market_condition = "AND s.market = 'KOSPI'"
        elif market == "KOSDAQ":
            market_condition = "AND s.market = 'KOSDAQ'"

        metric_column = "o.volume" if ratio_by == "volume" else "o.value"

        total_query = f"""
            SELECT SUM({metric_column}) as total_value, COUNT(*) as total_stocks
            FROM ohlcv o
            JOIN stocks s ON o.ticker = s.ticker
            WHERE o.date = ? {market_condition}
            AND o.volume > 0
        """

        total_result, _ = db_client.fetch_query(total_query, [date])

        if not total_result or total_result[0][0] is None:
            return {"error": f"No market data found for {date}"}

        market_total = float(total_result[0][0])
        total_stocks = int(total_result[0][1])

        # 3. 비율 계산
        ratio = (stock_value / market_total * 100) if market_total != 0 else 0

        return {
            "ticker": ticker,
            "stock_name": stock_name,
            "date": date,
            "market": market,
            "ratio_by": ratio_by,
            "stock_value": stock_value,
            "market_total": market_total,
            "ratio_percentage": round(ratio, 2),
            "total_stocks_in_market": total_stocks,
        }

    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        db_client.close()
