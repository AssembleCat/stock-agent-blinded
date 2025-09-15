import os
from typing import Dict, Any, List
from dotenv import load_dotenv
import requests
from langchain_naver import ChatClovaX
from utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class NaverSearchAPIWrapper:
    """네이버 검색 API 래퍼 (LangChain 스타일)"""

    def __init__(self, naver_client_id: str, naver_client_secret: str):
        self.client_id = naver_client_id
        self.client_secret = naver_client_secret
        self.base_url = "https://openapi.naver.com/v1/search"

    def run(self, query: str, search_type: str = "news", max_results: int = 5) -> str:
        """검색을 실행하고 결과를 문자열로 반환합니다."""
        try:
            url = f"{self.base_url}/{search_type}.json"
            headers = {
                "X-Naver-Client-Id": self.client_id,
                "X-Naver-Client-Secret": self.client_secret,
            }
            params = {
                "query": query,
                "display": max_results,
                "start": 1,
                "sort": "date" if search_type == "news" else "sim",
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            results = []

            if "items" in data:
                for item in data["items"]:
                    title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    description = (
                        item.get("description", "")
                        .replace("<b>", "")
                        .replace("</b>", "")
                    )
                    link = item.get("link", "")

                    results.append(f"{title} - {description} {link}")

            return "\n".join(results)

        except Exception as e:
            logger.error(f"네이버 검색 중 오류: {e}")
            return ""


class NaverNewsSearchTool:
    """네이버 뉴스 검색을 통한 최근 뉴스 기반 힌트 생성 도구"""

    def __init__(self):
        """네이버 뉴스 검색 도구 초기화"""
        try:
            # 네이버 검색 API 설정 확인
            self.client_id = os.getenv("NAVER_CLIENT_ID")
            self.client_secret = os.getenv("NAVER_CLIENT_SECRET")

            if not self.client_id or not self.client_secret:
                logger.warning(
                    "네이버 검색 API 키가 설정되지 않았습니다. 뉴스 검색 기능이 제한됩니다."
                )
                self.search_available = False
            else:
                self.search_available = True
                # LangChain 스타일의 NaverSearchAPIWrapper 초기화
                self.search_wrapper = NaverSearchAPIWrapper(
                    naver_client_id=self.client_id,
                    naver_client_secret=self.client_secret,
                )
                logger.info("네이버 뉴스 검색 도구 초기화 완료 (LangChain 스타일)")

            # LLM 초기화 (키워드 추출용)
            self.llm = ChatClovaX(model="HCX-005", temperature=0)

        except Exception as e:
            logger.error(f"네이버 뉴스 검색 도구 초기화 중 오류: {e}")
            self.search_available = False

    def generate_news_based_hint(
        self, quiz_data: Dict[str, Any], max_news_count: int = 5
    ) -> Dict[str, Any]:
        """
        퀴즈 데이터를 기반으로 최근 뉴스를 검색하여 힌트를 생성합니다.

        Args:
            quiz_data: 퀴즈 데이터 (배경지식, 정답 기업명 등 포함)
            max_news_count: 검색할 최대 뉴스 개수

        Returns:
            뉴스 기반 힌트 정보 딕셔너리
        """
        try:
            if not self.search_available:
                return self._get_fallback_hint("네이버 검색 API가 설정되지 않았습니다.")

            # 1. 검색 키워드 생성
            search_keywords = self._generate_search_keywords(quiz_data)
            if not search_keywords:
                return self._get_fallback_hint("검색 키워드를 생성할 수 없습니다.")

            # 2. 뉴스 검색 실행 (LangChain 스타일 사용)
            news_results = self._search_recent_news(search_keywords, max_news_count)
            if not news_results:
                return self._get_fallback_hint("관련 뉴스를 찾을 수 없습니다.")

            # 3. 뉴스 내용 분석 및 키워드 추출
            news_keywords = self._extract_news_keywords(news_results, quiz_data)

            # 4. 힌트 메시지 생성
            hint_message = self._create_hint_message(news_keywords, quiz_data)

            return {
                "success": True,
                "hint_type": "news_based",
                "hint_message": hint_message,
                "search_keywords": search_keywords,
                "news_count": len(news_results),
                "extracted_keywords": news_keywords,
                "raw_news": news_results[:3],  # 디버깅용 (최대 3개)
            }

        except Exception as e:
            logger.error(f"뉴스 기반 힌트 생성 중 오류: {e}")
            return self._get_fallback_hint(
                f"뉴스 검색 중 오류가 발생했습니다: {str(e)}"
            )

    def _generate_search_keywords(self, quiz_data: Dict[str, Any]) -> List[str]:
        """퀴즈 데이터를 기반으로 검색 키워드를 생성합니다."""
        try:
            correct_answer = quiz_data.get("correct_answer", {})
            correct_company = correct_answer.get("company", "")

            # 정답 기업명을 기반으로 키워드 추출
            keywords = []

            # 1. 정답 기업명에서 핵심 키워드 추출
            if correct_company:
                company_keywords = self._extract_keywords_from_company(correct_company)
                keywords.extend(company_keywords)

            # 2. 업종, 특징 등 추가 키워드
            additional_keywords = self._get_additional_keywords(quiz_data)
            keywords.extend(additional_keywords)

            # 3. 중복 제거
            unique_keywords = list(set(keywords))

            # 4. 검색 가능한 키워드만 필터링 (2글자 이상)
            searchable_keywords = [kw for kw in unique_keywords if len(kw) >= 2]

            logger.debug(f"생성된 검색 키워드: {searchable_keywords}")
            return searchable_keywords[:5]  # 최대 5개 키워드

        except Exception as e:
            logger.error(f"검색 키워드 생성 중 오류: {e}")
            return []

    def _extract_keywords_from_company(self, company_name: str) -> List[str]:
        """정답 기업명에서 검색 키워드를 추출합니다."""
        try:
            # LLM을 사용하여 기업명에서 키워드 추출
            prompt = f"""
다음 기업명에서 검색에 유용한 핵심 키워드 3-5개를 추출해주세요.

기업명: {company_name}

요구사항:
1. 기업명 자체는 제외하고 추출
2. 업종, 주요 사업, 특징, 기술 등을 포함
3. 검색 가능한 형태로 추출
4. 쉼표로만 구분하여 답변 (다른 설명 없이)

예시: "삼성전자" → "반도체, 메모리, 스마트폰, 가전"
예시: "현대자동차" → "자동차, 전기차, 수출, 국내최대"

답변 형식: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5
"""

            response = self.llm.invoke(prompt)
            result = response.content.strip()

            # 쉼표로 분리하여 키워드 리스트 생성
            keywords = []
            for kw in result.split(","):
                kw = kw.strip()
                # 설명이나 추가 텍스트 제거
                if (
                    kw
                    and len(kw) <= 20
                    and not kw.startswith("예시")
                    and not kw.startswith("답변")
                ):
                    # "키워드:" 접두사 제거
                    if kw.startswith("키워드:"):
                        kw = kw[4:].strip()
                    keywords.append(kw)

            return keywords[:5]  # 최대 5개

        except Exception as e:
            logger.error(f"기업명 키워드 추출 중 오류: {e}")
            return []

    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """텍스트에서 핵심 키워드를 추출합니다."""
        try:
            # LLM을 사용하여 키워드 추출
            prompt = f"""
다음 텍스트에서 검색에 유용한 핵심 키워드 3-5개를 추출해주세요.

텍스트: {text}

요구사항:
1. 기업명은 제외하고 추출
2. 업종, 특징, 연도, 금액, 기술명 등을 포함
3. 검색 가능한 형태로 추출
4. 쉼표로 구분하여 답변

예시: "반도체, 메모리, 2023년, AI, 자동차"
"""

            response = self.llm.invoke(prompt)
            result = response.content.strip()

            # 쉼표로 분리하여 키워드 리스트 생성
            keywords = []
            for kw in result.split(","):
                kw = kw.strip()
                # 설명이나 추가 텍스트 제거
                if (
                    kw
                    and len(kw) <= 20
                    and not kw.startswith("예시")
                    and not kw.startswith("답변")
                ):
                    # "키워드:" 접두사 제거
                    if kw.startswith("키워드:"):
                        kw = kw[4:].strip()
                    keywords.append(kw)

            return keywords[:5]  # 최대 5개

        except Exception as e:
            logger.error(f"텍스트 키워드 추출 중 오류: {e}")
            return []

    def _get_additional_keywords(self, quiz_data: Dict[str, Any]) -> List[str]:
        """퀴즈 데이터에서 추가 키워드를 추출합니다."""
        keywords = []

        try:
            # 선택지에서 키워드 추출
            options = quiz_data.get("options", [])
            for option in options:
                if isinstance(option, dict):
                    company = option.get("company", "")
                    if company:
                        # 기업명에서 업종 관련 키워드 추출
                        sector_keywords = self._extract_sector_keywords(company)
                        keywords.extend(sector_keywords)

            # 배경지식에서 추가 키워드
            background = quiz_data.get("background", "")
            if "상장" in background:
                keywords.append("상장")
            if "IPO" in background or "공모" in background:
                keywords.append("IPO")
            if "시총" in background or "시가총액" in background:
                keywords.append("시가총액")

        except Exception as e:
            logger.error(f"추가 키워드 추출 중 오류: {e}")

        return keywords

    def _extract_sector_keywords(self, company_name: str) -> List[str]:
        """기업명에서 업종 관련 키워드를 추출합니다."""
        sector_keywords = []

        # 업종별 키워드 매핑
        sector_mapping = {
            "전자": ["전자", "IT", "기술"],
            "반도체": ["반도체", "메모리", "칩"],
            "자동차": ["자동차", "차량", "모빌리티"],
            "바이오": ["바이오", "제약", "의료"],
            "금융": ["금융", "은행", "보험"],
            "건설": ["건설", "부동산"],
            "화학": ["화학", "석유"],
            "통신": ["통신", "네트워크"],
            "유통": ["유통", "소매", "마트"],
        }

        for sector, keywords in sector_mapping.items():
            if sector in company_name:
                sector_keywords.extend(keywords)
                break

        return sector_keywords

    def _search_recent_news(
        self, keywords: List[str], max_count: int
    ) -> List[Dict[str, Any]]:
        """키워드를 사용하여 최근 뉴스를 검색합니다. (LangChain 스타일 사용)"""
        try:
            if not keywords:
                return []

            # 가장 관련성 높은 키워드로 검색
            primary_keyword = keywords[0]

            # 최근 1주일 내 뉴스 검색
            search_query = f"{primary_keyword} 뉴스"

            logger.info(f"뉴스 검색 실행 (LangChain 스타일): {search_query}")

            # LangChain 스타일의 NaverSearchAPIWrapper 사용
            search_results = self.search_wrapper.run(
                search_query, search_type="news", max_results=max_count
            )

            # 검색 결과 파싱
            news_items = self._parse_search_results(search_results, max_count)

            return news_items

        except Exception as e:
            logger.error(f"뉴스 검색 중 오류: {e}")
            return []

    def _parse_search_results(
        self, search_results: str, max_count: int
    ) -> List[Dict[str, Any]]:
        """LangChain 스타일 검색 결과를 파싱하여 뉴스 아이템 리스트로 변환합니다."""
        try:
            news_items = []

            # 검색 결과를 줄 단위로 분리
            lines = search_results.strip().split("\n")

            for line in lines:
                if len(news_items) >= max_count:
                    break

                line = line.strip()
                if not line:
                    continue

                # 제목과 링크 추출 (간단한 파싱)
                if " - " in line and "http" in line:
                    # 제목 - 설명 링크 형식
                    parts = line.split(" - ")
                    title = parts[0].strip()

                    # 설명과 링크 분리
                    remaining = " - ".join(parts[1:])
                    if "http" in remaining:
                        desc_link_parts = remaining.split("http")
                        description = desc_link_parts[0].strip()
                        link = "http" + desc_link_parts[1].strip()
                    else:
                        description = remaining
                        link = ""

                    news_items.append(
                        {
                            "title": title,
                            "content": description,
                            "date": "",  # 날짜 정보는 별도로 추출 필요
                            "link": link,
                        }
                    )
                else:
                    # 단순한 형식
                    news_items.append(
                        {"title": line, "content": line, "date": "", "link": ""}
                    )

            return news_items

        except Exception as e:
            logger.error(f"검색 결과 파싱 중 오류: {e}")
            return []

    def _extract_news_keywords(
        self, news_results: List[Dict[str, Any]], quiz_data: Dict[str, Any]
    ) -> List[str]:
        """뉴스 내용에서 퀴즈와 관련된 키워드를 추출합니다."""
        try:
            if not news_results:
                return []

            # 뉴스 내용 통합
            combined_content = " ".join(
                [
                    item.get("title", "") + " " + item.get("content", "")
                    for item in news_results
                ]
            )

            # 정답 기업명 제외
            correct_answer = quiz_data.get("correct_answer", {})
            correct_company = correct_answer.get("company", "")

            # LLM을 사용하여 관련 키워드 추출
            prompt = f"""
다음 뉴스 내용에서 퀴즈와 관련된 핵심 키워드 3-5개를 추출해주세요.

뉴스 내용: {combined_content[:1000]}  # 길이 제한

요구사항:
1. 정답 기업명 "{correct_company}"은 절대 포함하지 마세요
2. 기업명의 일부분도 포함하지 마세요
3. 업종, 기술, 트렌드, 특징 등을 포함해주세요
4. 쉼표로만 구분하여 답변해주세요 (다른 설명 없이)

답변 형식: 키워드1, 키워드2, 키워드3, 키워드4, 키워드5

예시: "AI, 반도체, 메모리, 자율주행, 전기차"
"""

            response = self.llm.invoke(prompt)
            result = response.content.strip()

            # 쉼표로 분리하여 키워드 리스트 생성
            keywords = []
            for kw in result.split(","):
                kw = kw.strip()
                # 설명이나 추가 텍스트 제거
                if (
                    kw
                    and len(kw) <= 20
                    and not kw.startswith("예시")
                    and not kw.startswith("답변")
                ):
                    # "키워드:" 접두사 제거
                    if kw.startswith("키워드:"):
                        kw = kw[4:].strip()
                    keywords.append(kw)

            # 정답 기업명이 포함된 경우 제거
            if correct_company:
                keywords = [kw for kw in keywords if correct_company not in kw]

            return keywords[:5]  # 최대 5개

        except Exception as e:
            logger.error(f"뉴스 키워드 추출 중 오류: {e}")
            return []

    def _create_hint_message(
        self, keywords: List[str], quiz_data: Dict[str, Any]
    ) -> str:
        """추출된 키워드로 힌트 메시지를 생성합니다."""
        try:
            if not keywords:
                return "최근 뉴스에서 관련 키워드를 찾을 수 없습니다."

            # 키워드를 자연스러운 문장으로 구성
            keyword_text = ", ".join(keywords)

            hint_message = f"""📰 **최근 뉴스 기반 힌트**

최근 뉴스에서 발견된 관련 키워드:
💡 {keyword_text}

이 키워드들과 관련된 기업을 생각해보세요!"""

            return hint_message

        except Exception as e:
            logger.error(f"힌트 메시지 생성 중 오류: {e}")
            return "뉴스 기반 힌트를 생성할 수 없습니다."

    def _get_fallback_hint(self, reason: str) -> Dict[str, Any]:
        """뉴스 검색이 실패했을 때의 폴백 힌트를 반환합니다."""
        logger.warning(f"뉴스 기반 힌트 생성 실패: {reason}")

        return {
            "success": False,
            "hint_type": "fallback",
            "hint_message": "최근 뉴스 검색이 불가능합니다. 기존 힌트를 참고해주세요.",
            "reason": reason,
            "search_keywords": [],
            "news_count": 0,
            "extracted_keywords": [],
            "raw_news": [],
        }


# 싱글톤 인스턴스
naver_news_search_tool = NaverNewsSearchTool()
