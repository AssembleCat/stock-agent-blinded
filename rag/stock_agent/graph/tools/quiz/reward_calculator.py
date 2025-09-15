from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from db.sqlite_db import SqliteDBClient
from utils.logger import get_logger

logger = get_logger(__name__)


class QuizRewardCalculator:
    """퀴즈 보상 계산 클래스"""

    @staticmethod
    def get_ticker_from_company_name(company_name: str) -> Optional[str]:
        """
        기업명으로 ticker를 조회합니다.

        Args:
            company_name: 기업명

        Returns:
            ticker 또는 None
        """
        try:
            db = SqliteDBClient()

            # 정확한 이름 매칭
            query = "SELECT ticker FROM stocks WHERE name = ?"
            results, columns = db.fetch_query(query, [company_name])

            if results:
                ticker = results[0][0]
                logger.debug(f"기업명 '{company_name}' -> ticker '{ticker}'")
                db.close()
                return ticker

            # 부분 매칭 시도
            query = "SELECT ticker FROM stocks WHERE name LIKE ?"
            results, columns = db.fetch_query(query, [f"%{company_name}%"])

            if results:
                ticker = results[0][0]
                logger.debug(
                    f"기업명 '{company_name}' -> ticker '{ticker}' (부분 매칭)"
                )
                db.close()
                return ticker

            logger.warning(
                f"기업명 '{company_name}'에 해당하는 ticker를 찾을 수 없습니다."
            )
            db.close()
            return None

        except Exception as e:
            logger.error(f"Ticker 조회 중 오류: {e}")
            return None

    @staticmethod
    def get_previous_business_day(reference_date: datetime = None) -> str:
        """
        직전 영업일을 반환합니다.

        Args:
            reference_date: 기준 날짜 (기본값: 오늘)

        Returns:
            직전 영업일 (YYYY-MM-DD 형식)
        """
        try:
            if reference_date is None:
                reference_date = datetime.now()

            # 주말과 공휴일을 고려하여 최대 10일 전까지 확인
            for i in range(1, 11):
                candidate_date = reference_date - timedelta(days=i)

                # 주말 제외 (월요일=0, 일요일=6)
                if candidate_date.weekday() >= 5:  # 토요일(5), 일요일(6)
                    continue

                # DB에 해당 날짜의 거래 데이터가 있는지 확인
                date_str = candidate_date.strftime("%Y-%m-%d")
                if QuizRewardCalculator._has_trading_data(date_str):
                    logger.debug(f"직전 영업일: {date_str}")
                    return date_str

            # 최후의 수단: 7일 전 날짜 반환
            fallback_date = (reference_date - timedelta(days=7)).strftime("%Y-%m-%d")
            logger.warning(f"영업일을 찾을 수 없어 fallback 사용: {fallback_date}")
            return fallback_date

        except Exception as e:
            logger.error(f"직전 영업일 조회 중 오류: {e}")
            return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    @staticmethod
    def _has_trading_data(date_str: str) -> bool:
        """
        특정 날짜에 거래 데이터가 있는지 확인합니다.

        Args:
            date_str: 날짜 (YYYY-MM-DD 형식)

        Returns:
            거래 데이터 존재 여부
        """
        try:
            db = SqliteDBClient()

            query = "SELECT COUNT(*) FROM ohlcv WHERE date = ?"
            results, columns = db.fetch_query(query, [date_str])

            count = results[0][0] if results else 0
            db.close()

            return count > 0

        except Exception as e:
            logger.error(f"거래 데이터 확인 중 오류: {e}")
            return False

    @staticmethod
    def get_closing_price(ticker: str, date_str: str) -> Optional[float]:
        """
        특정 날짜의 종가를 조회합니다.

        Args:
            ticker: 종목 티커
            date_str: 날짜 (YYYY-MM-DD 형식)

        Returns:
            종가 또는 None
        """
        try:
            db = SqliteDBClient()

            query = "SELECT close FROM ohlcv WHERE ticker = ? AND date = ?"
            results, columns = db.fetch_query(query, [ticker, date_str])

            if results and results[0][0] is not None:
                closing_price = float(results[0][0])
                logger.debug(f"{ticker} {date_str} 종가: {closing_price:,}원")
                db.close()
                return closing_price

            logger.warning(f"{ticker} {date_str}의 종가 데이터를 찾을 수 없습니다.")
            db.close()
            return None

        except Exception as e:
            logger.error(f"종가 조회 중 오류: {e}")
            return None

    @staticmethod
    def calculate_reward_shares(
        company_name: str, target_value: float = 100.0
    ) -> Dict[str, Any]:
        """
        직전 영업일 종가 기준으로 목표 가치에 해당하는 주식 수량을 계산합니다.

        Args:
            company_name: 기업명
            target_value: 목표 가치 (기본값: 100원)

        Returns:
            보상 정보 딕셔너리
        """
        try:
            # 1. 기업명으로 ticker 조회
            ticker = QuizRewardCalculator.get_ticker_from_company_name(company_name)
            if not ticker:
                return {
                    "success": False,
                    "error": f"'{company_name}'에 해당하는 ticker를 찾을 수 없습니다.",
                    "company_name": company_name,
                    "shares": 0,
                    "total_value": 0,
                    "closing_price": 0,
                }

            # 2. 직전 영업일 조회
            previous_date = QuizRewardCalculator.get_previous_business_day()

            # 3. 종가 조회
            closing_price = QuizRewardCalculator.get_closing_price(
                ticker, previous_date
            )
            if not closing_price or closing_price <= 0:
                return {
                    "success": False,
                    "error": f"'{company_name}'({ticker})의 {previous_date} 종가를 조회할 수 없습니다.",
                    "company_name": company_name,
                    "ticker": ticker,
                    "date": previous_date,
                    "shares": 0,
                    "total_value": 0,
                    "closing_price": 0,
                }

            # 4. 목표 가치에 해당하는 주식 수량 계산 (소수점 3자리까지)
            shares = round(target_value / closing_price, 7)
            actual_value = shares * closing_price

            logger.info(
                f"보상 계산 완료: {company_name} {shares}주 (가치: {actual_value:,.0f}원)"
            )

            return {
                "success": True,
                "company_name": company_name,
                "ticker": ticker,
                "date": previous_date,
                "closing_price": closing_price,
                "shares": shares,
                "total_value": actual_value,
                "target_value": target_value,
            }

        except Exception as e:
            logger.error(f"보상 계산 중 오류: {e}")
            return {
                "success": False,
                "error": f"보상 계산 중 오류가 발생했습니다: {str(e)}",
                "company_name": company_name,
                "shares": 0,
                "total_value": 0,
                "closing_price": 0,
            }


# 전역 인스턴스
quiz_reward_calculator = QuizRewardCalculator()
