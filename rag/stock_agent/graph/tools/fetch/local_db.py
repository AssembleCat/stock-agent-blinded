from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from db.sqlite_db import SqliteDBClient


class Market(str, Enum):
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"
    ALL = "ALL"


class MarketOhlcvInput(BaseModel):
    market: Market = Field(..., description="The market to fetch OHLCV data for")
    date: str = Field(
        ...,
        description="It must be 'YYYY-MM-DD' format, The date to fetch OHLCV data for",
    )


@tool(args_schema=MarketOhlcvInput)
def get_market_ohlcv(market: Market, date: str):
    """
    특정일자의 KOSPI, KOSDAQ, 모든 시장의 OHLCV 데이터와 거래대금 데이터를 조회합니다.
    질문에 따라 필요한 정보만 반환합니다.
    """

    db_client = SqliteDBClient()

    if market == Market.KOSPI:
        results, columes = db_client.fetch_query(
            "SELECT * FROM market_index_ohlcv WHERE market = ? AND date = ?",
            params=["KOSPI", date],
        )
    elif market == Market.KOSDAQ:
        results, columes = db_client.fetch_query(
            "SELECT * FROM market_index_ohlcv WHERE market = ? AND date = ?",
            params=["KOSDAQ", date],
        )
    elif market == Market.ALL:
        results, columes = db_client.fetch_query(
            "SELECT * FROM market_index_ohlcv WHERE date = ?", params=[date]
        )

    if results and columes:
        dict_results = []
        for row in results:
            row_dict = dict(zip(columes, row))
            # 데이터 타입 변환하여 일관성 확보
            for key, value in row_dict.items():
                if key in ["open", "high", "low", "close", "volume", "value"]:
                    if value is not None:
                        try:
                            if key == "volume":
                                row_dict[key] = int(value)
                            else:
                                row_dict[key] = float(value)
                        except (ValueError, TypeError):
                            row_dict[key] = 0 if key == "volume" else 0.0
                    else:
                        row_dict[key] = 0 if key == "volume" else 0.0
            dict_results.append(row_dict)
        return dict_results
    else:
        return []


if __name__ == "__main__":
    print(get_market_ohlcv.invoke({"market": "KOSPI", "date": "20241121"}))
