import sqlite3
import os
import sys

# 상위 디렉토리 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.logger import get_logger

logger = get_logger(__name__)


def create_performance_indexes():
    """
    모든 테이블에 성능 최적화를 위한 인덱스를 생성합니다.
    """
    db_path = "market.db"

    if not os.path.exists(db_path):
        logger.error(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 기존 인덱스 확인
        cursor.execute("PRAGMA index_list(technical_signals)")
        existing_tech_indexes = [row[1] for row in cursor.fetchall()]
        logger.info(f"technical_signals 기존 인덱스: {existing_tech_indexes}")

        cursor.execute("PRAGMA index_list(ohlcv)")
        existing_ohlcv_indexes = [row[1] for row in cursor.fetchall()]
        logger.info(f"ohlcv 기존 인덱스: {existing_ohlcv_indexes}")

        cursor.execute("PRAGMA index_list(stocks)")
        existing_stocks_indexes = [row[1] for row in cursor.fetchall()]
        logger.info(f"stocks 기존 인덱스: {existing_stocks_indexes}")

        cursor.execute("PRAGMA index_list(market_index_ohlcv)")
        existing_market_indexes = [row[1] for row in cursor.fetchall()]
        logger.info(f"market_index_ohlcv 기존 인덱스: {existing_market_indexes}")

        # 성능 최적화를 위한 복합 인덱스들
        indexes_to_create = [
            # technical_signals 테이블 인덱스
            (
                "ix_technical_signals_date_indicator",
                "CREATE INDEX ix_technical_signals_date_indicator ON technical_signals(date, indicator)",
            ),
            (
                "ix_technical_signals_ticker_date",
                "CREATE INDEX ix_technical_signals_ticker_date ON technical_signals(ticker, date)",
            ),
            (
                "ix_technical_signals_indicator_date",
                "CREATE INDEX ix_technical_signals_indicator_date ON technical_signals(indicator, date)",
            ),
            # ohlcv 테이블 인덱스
            (
                "ix_ohlcv_date_ticker",
                "CREATE INDEX ix_ohlcv_date_ticker ON ohlcv(date, ticker)",
            ),
            (
                "ix_ohlcv_ticker_date",
                "CREATE INDEX ix_ohlcv_ticker_date ON ohlcv(ticker, date)",
            ),
            (
                "ix_ohlcv_date_volume",
                "CREATE INDEX ix_ohlcv_date_volume ON ohlcv(date, volume)",
            ),
            (
                "ix_ohlcv_date_change_rate",
                "CREATE INDEX ix_ohlcv_date_change_rate ON ohlcv(date, change_rate)",
            ),
            (
                "ix_ohlcv_date_close",
                "CREATE INDEX ix_ohlcv_date_close ON ohlcv(date, close)",
            ),
            # stocks 테이블 인덱스
            ("ix_stocks_market", "CREATE INDEX ix_stocks_market ON stocks(market)"),
            ("ix_stocks_name", "CREATE INDEX ix_stocks_name ON stocks(name)"),
            # market_index_ohlcv 테이블 인덱스
            (
                "ix_market_index_ohlcv_market_date",
                "CREATE INDEX ix_market_index_ohlcv_market_date ON market_index_ohlcv(market, date)",
            ),
            (
                "ix_market_index_ohlcv_date_market",
                "CREATE INDEX ix_market_index_ohlcv_date_market ON market_index_ohlcv(date, market)",
            ),
        ]

        created_count = 0
        for index_name, create_sql in indexes_to_create:
            if (
                index_name not in existing_tech_indexes
                and index_name not in existing_ohlcv_indexes
                and index_name not in existing_stocks_indexes
                and index_name not in existing_market_indexes
            ):
                logger.info(f"인덱스 생성 중: {index_name}")
                cursor.execute(create_sql)
                created_count += 1
            else:
                logger.info(f"인덱스가 이미 존재합니다: {index_name}")

        conn.commit()
        logger.info(f"총 {created_count}개의 인덱스가 생성되었습니다.")

        # 최종 인덱스 목록 확인
        logger.info("=== 최종 인덱스 목록 ===")
        for table in ["technical_signals", "ohlcv", "stocks", "market_index_ohlcv"]:
            cursor.execute(f"PRAGMA index_list({table})")
            final_indexes = [row[1] for row in cursor.fetchall()]
            logger.info(f"{table}: {final_indexes}")

    except Exception as e:
        logger.error(f"인덱스 생성 중 오류 발생: {str(e)}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    create_performance_indexes()
