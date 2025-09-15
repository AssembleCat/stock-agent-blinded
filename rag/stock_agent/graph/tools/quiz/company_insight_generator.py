from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from langchain_naver import ChatClovaX
from datetime import datetime, timedelta
import json
from db.sqlite_db import SqliteDBClient
from rag.stock_agent.graph.prompts import get_company_insight_prompt, MIN_INSIGHT_LENGTH
from utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class CompanyInsightGenerator:
    """구조화된 프롬프트 기반 기업 통찰 스낵글 생성 클래스"""

    def __init__(self):
        self.llm = ChatClovaX(model="HCX-003", temperature=0.7)

        # 15개 퀴즈 종목 정적 데이터
        self.static_company_data = {
            "삼성전자": {
                "sector": "반도체",
                "business_model": "메모리 반도체, 스마트폰, 가전제품 제조",
                "ticker": "005930.KS",
                "group_affiliation": "삼성그룹",
            },
            "삼성전자우": {
                "sector": "반도체",
                "business_model": "메모리 반도체, 스마트폰, 가전제품 제조 (우선주)",
                "ticker": "005935.KS",
                "group_affiliation": "삼성그룹",
            },
            "SK하이닉스": {
                "sector": "반도체",
                "business_model": "DRAM, NAND 플래시 메모리 제조",
                "ticker": "000660.KS",
                "group_affiliation": "SK그룹",
            },
            "현대차": {
                "sector": "자동차",
                "business_model": "완성차 제조 및 판매",
                "ticker": "005380.KS",
                "group_affiliation": "현대차그룹",
            },
            "기아": {
                "sector": "자동차",
                "business_model": "완성차 제조 및 판매",
                "ticker": "000270.KS",
                "group_affiliation": "현대차그룹",
            },
            "삼성바이오로직스": {
                "sector": "바이오",
                "business_model": "바이오의약품 위탁생산(CMO)",
                "ticker": "207940.KS",
                "group_affiliation": "삼성그룹",
            },
            "셀트리온": {
                "sector": "바이오",
                "business_model": "바이오의약품 개발 및 제조",
                "ticker": "068270.KS",
                "group_affiliation": "독립기업",
            },
            "LG에너지솔루션": {
                "sector": "배터리",
                "business_model": "전기차 배터리 제조",
                "ticker": "373220.KS",
                "group_affiliation": "LG그룹",
            },
            "두산에너빌리티": {
                "sector": "에너지",
                "business_model": "원자력, 가스터빈 등 에너지 설비 제조",
                "ticker": "034020.KS",
                "group_affiliation": "두산그룹",
            },
            "KB금융": {
                "sector": "금융",
                "business_model": "은행, 보험, 증권 등 종합금융서비스",
                "ticker": "105560.KS",
                "group_affiliation": "KB금융그룹",
            },
            "신한지주": {
                "sector": "금융",
                "business_model": "은행, 보험, 증권 등 종합금융서비스",
                "ticker": "055550.KS",
                "group_affiliation": "신한금융그룹",
            },
            "NAVER": {
                "sector": "IT",
                "business_model": "검색 포털, 클라우드, 콘텐츠 플랫폼 서비스",
                "ticker": "035420.KS",
                "group_affiliation": "네이버",
            },
            "삼성물산": {
                "sector": "종합상사",
                "business_model": "건설, 상사, 패션 등 종합사업",
                "ticker": "028260.KS",
                "group_affiliation": "삼성그룹",
            },
            "한화에어로스페이스": {
                "sector": "항공우주",
                "business_model": "항공우주 및 방위산업 장비 제조",
                "ticker": "012450.KS",
                "group_affiliation": "한화그룹",
            },
            "HD현대중공업": {
                "sector": "조선",
                "business_model": "선박 건조 및 해양플랜트 제조",
                "ticker": "329180.KS",
                "group_affiliation": "현대중공업그룹",
            },
        }

    def generate_company_insight(
        self, company_name: str, quiz_background: str = ""
    ) -> str:
        """
        구조화된 프롬프트와 실시간 데이터를 활용하여 기업 통찰 스낵글을 생성합니다.

        Args:
            company_name: 기업명
            quiz_background: 퀴즈 배경지식 (참고용)

        Returns:
            투자자 관점의 스낵글
        """
        try:
            # 1. 정적 데이터 확인
            static_data = self.static_company_data.get(company_name)
            if not static_data:
                logger.warning(f"정적 데이터가 없는 기업: {company_name}")
                return self._get_fallback_insight(company_name)

            # 2. 실시간 데이터 수집
            dynamic_data = self._collect_dynamic_data(
                company_name, static_data["ticker"], static_data["sector"]
            )

            # 3. 데이터 통합
            combined_data = {**static_data, **dynamic_data}

            # 4. 구조화된 프롬프트로 스낵글 생성
            insight_text = self._generate_structured_insight(
                company_name, combined_data, quiz_background
            )

            logger.info(
                f"{company_name} 구조화된 스낵글 생성 완료 ({len(insight_text)}자)"
            )
            return insight_text

        except Exception as e:
            logger.error(f"{company_name} 스낵글 생성 중 오류: {e}")
            return self._get_fallback_insight(company_name)

    def _collect_dynamic_data(
        self, company_name: str, ticker: str, sector: str
    ) -> Dict[str, Any]:
        """실시간 동적 데이터를 수집합니다."""

        dynamic_data = {}

        try:
            # 시가총액 순위 조회
            market_cap_rank = self._get_market_cap_rank(ticker)
            dynamic_data["market_cap_rank"] = market_cap_rank
            dynamic_data["market_position"] = self._convert_rank_to_position(
                market_cap_rank
            )

            # 최근 주가 트렌드 분석 (실제 기간 포함)
            price_trend, actual_days = self._analyze_price_trend(ticker)
            dynamic_data["price_trend"] = price_trend
            dynamic_data["actual_days"] = actual_days
            dynamic_data["current_status"] = self._convert_trend_to_status(price_trend)

            # 최근 이슈는 LLM이 주가 트렌드와 업종을 고려하여 자연스럽게 추론하도록 함
            dynamic_data["recent_keywords"] = []
            dynamic_data["recent_issue"] = ""  # LLM이 동적으로 판단

            logger.debug(f"{company_name} 동적 데이터 수집 완료")

        except Exception as e:
            logger.warning(f"{company_name} 동적 데이터 수집 중 오류: {e}")
            # 기본값 설정
            dynamic_data.update(
                {
                    "market_cap_rank": 0,
                    "market_position": "주요 기업",
                    "price_trend": 0.0,
                    "actual_days": 30,  # 기본값
                    "current_status": "안정적인 흐름을 보이고 있는",
                    "recent_keywords": [],
                    "recent_issue": "",
                }
            )

        return dynamic_data

    def _get_market_cap_rank(self, ticker: str) -> int:
        """DB에서 시가총액 순위를 조회합니다."""

        try:
            db = SqliteDBClient()
            # 최근 데이터로 시총 계산 및 순위 조회
            query = """
                SELECT ticker, close, volume, 
                       RANK() OVER (ORDER BY close * volume DESC) as market_rank
                FROM ohlcv 
                WHERE date = (SELECT MAX(date) FROM ohlcv)
                AND ticker = ?
            """
            results, _ = db.fetch_query(query, [ticker])
            db.close()

            if results:
                return results[0][3]  # market_rank
            else:
                return 50  # 기본값

        except Exception as e:
            logger.warning(f"시총 순위 조회 오류: {e}")
            return 50

    def _convert_rank_to_position(self, rank: int) -> str:
        """순위를 시장 포지션 설명으로 변환합니다."""

        if rank == 1:
            return "코스피 최대 시가총액 기업"
        elif rank <= 3:
            return "코스피 대형주"
        elif rank <= 10:
            return "코스피 주요 기업"
        elif rank <= 30:
            return "중견 상장기업"
        else:
            return "코스피 상장기업"

    def _analyze_price_trend(self, ticker: str) -> tuple[float, int]:
        """최근 영업일 기준 주가 트렌드를 분석합니다."""

        try:
            db = SqliteDBClient()
            query = """
                SELECT close, date
                FROM ohlcv
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 30
            """
            results, _ = db.fetch_query(query, [ticker])
            db.close()

            if len(results) >= 2:
                recent_price = results[0][0]
                past_price = results[-1][0]

                # 실제 기간 계산 (첫 날짜와 마지막 날짜의 차이)
                recent_date = results[0][1]  # 최신 날짜
                past_date = results[-1][1]  # 과거 날짜

                # 날짜 문자열을 datetime으로 변환해서 실제 일수 계산
                from datetime import datetime

                recent_dt = datetime.strptime(recent_date, "%Y-%m-%d")
                past_dt = datetime.strptime(past_date, "%Y-%m-%d")
                actual_days = (recent_dt - past_dt).days

                trend_percent = (recent_price - past_price) / past_price * 100
                return trend_percent, actual_days
            else:
                return 0.0, 0

        except Exception as e:
            logger.warning(f"주가 트렌드 분석 오류: {e}")
            return 0.0, 0

    def _convert_trend_to_status(self, trend: float) -> str:
        """주가 트렌드를 현재 상황 설명으로 변환합니다."""

        if trend > 10:
            return "강한 상승세를 보이고 있는"
        elif trend > 5:
            return "상승 흐름을 이어가고 있는"
        elif trend > -5:
            return "안정적인 흐름을 보이고 있는"
        elif trend > -10:
            return "조정을 받고 있는"
        else:
            return "큰 조정을 겪고 있는"

    def _generate_structured_insight(
        self, company_name: str, combined_data: Dict[str, Any], quiz_background: str
    ) -> str:
        """구조화된 프롬프트로 스낵글을 생성합니다."""

        # 프롬프트 모듈에서 가져온 함수 사용
        structured_prompt = get_company_insight_prompt(
            company_name, combined_data, quiz_background
        )

        try:
            response = self.llm.invoke(structured_prompt)
            insight_text = response.content.strip()

            # 기본 품질 검증 (프롬프트 모듈의 상수 사용)
            if len(insight_text) < MIN_INSIGHT_LENGTH:
                logger.warning(f"{company_name} LLM 스낵글이 너무 짧음")
                return self._get_fallback_insight(company_name)

            return insight_text

        except Exception as e:
            logger.error(f"{company_name} 구조화된 스낵글 생성 오류: {e}")
            return self._get_fallback_insight(company_name)

    def _get_fallback_insight(self, company_name: str) -> str:
        """LLM 생성 실패 시 폴백 스낵글을 반환합니다."""

        static_data = self.static_company_data.get(company_name, {})
        sector = static_data.get("sector", "해당 업종")
        business_model = static_data.get("business_model", "주요 사업")

        return f"{company_name}는 {sector} 분야의 주요 기업으로, {business_model}을 통해 수익을 창출하고 있습니다. 투자 전에는 기업의 재무상태와 시장 전망을 종합적으로 검토해보시기 바랍니다."


# 전역 인스턴스
company_insight_generator = CompanyInsightGenerator()
