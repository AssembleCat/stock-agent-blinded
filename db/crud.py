import sqlite3

DB_PATH = "market.db"


def get_ticker_by_name_exact(name: str) -> str:
    """
    주식 이름으로 정확히 일치하는 ticker를 조회합니다.

    Args:
        name: 주식 이름 (정확히 일치해야 함)

    Returns:
        ticker 코드 (market에 따라 .KS 또는 .KQ 추가), 없으면 None
    """

    if name in ["KOSPI", "KOSDAQ"]:
        return f"{name} is a Market Index"

    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute(
            "SELECT ticker FROM stocks WHERE REPLACE(name, ' ', '') = ?", (name,)
        )
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            return "Not found"


def get_stock_name(ticker: str) -> str:
    """
    ticker 코드로 주식 이름을 조회합니다.

    Args:
        ticker: ticker 코드 (예: 005930.KS)

    Returns:
        주식 이름, 없으면 ticker 그대로 반환
    """
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.execute("SELECT name FROM stocks WHERE ticker = ?", (ticker,))
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            return ticker
