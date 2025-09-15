from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_naver import ChatClovaX
from pykrx import stock
from db.crud import get_ticker_by_name_exact
from rag.stock_agent.graph.state import StockAgentState
from utils.logger import get_logger
from rag.stock_agent.graph.clova_function_calling import process_function_calling
from rag.stock_agent.graph.prompts import PREPROCESS_TOOLS as TOOLS
import json
import datetime
import re
from typing import List

# LLM 인스턴스 생성
llm = ChatClovaX(model="HCX-005", temperature=0)

logger = get_logger(__name__)


@tool
def check_trading_date(date: str) -> dict:
    """
    주어진 날짜가 주식거래일인지 확인.
    date: YYYY-MM-DD 또는 YYYYMMDD 형식의 날짜
    """
    # 날짜 형식 변환 (YYYY-MM-DD -> YYYYMMDD)
    if "-" in date:
        # YYYY-MM-DD 형식을 YYYYMMDD로 변환
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
        date = date_obj.strftime("%Y%m%d")

    return {
        "query_date": date,
        "is_trading_date": stock.get_nearest_business_day_in_a_week(date) == date,
    }


@tool
def names_to_ticker(names: List[str]) -> dict:
    """
    주어진 주식명 리스트에 해당하는 Ticker들을 조회.
    KOSPI, KOSDAQ은 지수 종목이므로 티커가 없음.
    """
    results = []
    for name in names:
        ticker = get_ticker_by_name_exact(name)
        results.append(
            {
                "ticker": ticker,
                "name": name,
            }
        )

    return {"stock_list": results, "count": len(results)}


def extract_date_from_query(query: str) -> str:
    """쿼리에서 날짜를 추출합니다."""
    # YYYY-MM-DD 패턴
    date_pattern = r"\d{4}-\d{2}-\d{2}"
    match = re.search(date_pattern, query)
    if match:
        return match.group()

    # YYYYMMDD 패턴
    date_pattern = r"\d{8}"
    match = re.search(date_pattern, query)
    if match:
        date_str = match.group()
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    return None


def extract_stock_names_with_llm(query: str) -> List[str]:
    """LLM을 사용하여 쿼리에서 주식명들을 추출합니다."""
    from rag.stock_agent.graph.prompts import STOCK_NAMES_EXTRACTION_PROMPT

    prompt = ChatPromptTemplate.from_messages(STOCK_NAMES_EXTRACTION_PROMPT)

    try:
        response = llm.invoke(prompt.invoke({"query": query}))
        stock_names_text = response.content

        # "없음" 또는 빈 문자열 처리
        if stock_names_text in ["없음", "", "None", "null", "[]"]:
            return []

        # JSON 형식으로 파싱 시도
        try:
            stock_names = json.loads(stock_names_text)
            if isinstance(stock_names, list):
                return stock_names
        except json.JSONDecodeError:
            pass

        # 쉼표로 구분된 문자열로 파싱 시도
        if "," in stock_names_text:
            stock_names = [name.strip() for name in stock_names_text.split(",")]
            return stock_names

        # 단일 주식명인 경우
        return [stock_names_text.strip()]

    except Exception as e:
        logger.error(f"LLM 주식명 추출 실패: {e}")
        return []


def preprocess(state: StockAgentState) -> StockAgentState:
    """
    성능 최적화된 전처리 - Function Calling 우회
    """
    query = state["query"]
    api_key = state["api_key"]

    # 성능 최적화: Function Calling 우회하고 직접 도구 호출
    try:
        background_knowledge = {}

        # 날짜 추출 및 확인
        date = extract_date_from_query(query)
        if date:
            logger.info(f"--직접 도구 호출: check_trading_date with {date}--")
            date_result = check_trading_date.invoke({"date": date})
            background_knowledge["check_trading_date"] = date_result

        # 복수 종목명 추출 및 티커 변환 (LLM 기반으로 개선)
        stock_names = extract_stock_names_with_llm(query)
        if stock_names:
            logger.info(f"--LLM 기반 복수 주식명 추출: {stock_names}--")

            # 복수 주식명인 경우 새로운 방식 사용
            ticker_result = names_to_ticker.invoke({"names": stock_names})
            background_knowledge["names_to_tickers"] = ticker_result
            logger.info(f"--복수 주식명 처리: {ticker_result}--")

        logger.info(f"--최종 background_knowledge: {background_knowledge}--")
        state["context"] = background_knowledge
        return state

    except Exception as e:
        logger.error(f"직접 도구 호출 실패: {e}")
        # Fallback: 기존 Function Calling 방식 사용
        logger.info("--Fallback: Function Calling 방식 사용--")

        # 초기 메시지 설정
        from rag.stock_agent.graph.prompts import PREPROCESS_SYSTEM_MSG

        initial_messages = [
            {
                "role": "system",
                "content": PREPROCESS_SYSTEM_MSG,
            },
            {"role": "user", "content": query},
        ]

        # 도구 함수 매핑
        tool_functions = {
            "check_trading_date": check_trading_date,
            "names_to_ticker": names_to_ticker,
        }

        # Function calling 프로세스 실행
        result = process_function_calling(
            initial_messages=initial_messages,
            tools=TOOLS,
            tool_functions=tool_functions,
            feedback="",
            api_key=api_key,
        )

        if not result["success"]:
            logger.error(
                f"Function calling 실패: {result.get('error', 'Unknown error')}"
            )
            state["context"] = {}
            return state

        # 결과 정리
        background_knowledge = {}
        for tool_result in result["tool_results"]:
            function_name = tool_result["function_name"]
            background_knowledge[function_name] = tool_result["result"]

        logger.info(f"--최종 background_knowledge: {background_knowledge}--")
        state["context"] = background_knowledge
        # 민감정보 노출 방지: 전체 state는 출력하지 않습니다.
        logger.debug("== preprocess 종료 == state_keys=%s", list(state.keys()))
        return state
