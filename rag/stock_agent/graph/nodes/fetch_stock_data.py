from rag.stock_agent.graph.state import StockAgentState
from rag.stock_agent.graph.clova_function_calling import process_function_calling
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from rag.stock_agent.graph.tools.fetch.get_historical_data import (
    get_historical_data,
    get_stock_ranking,
    get_stock_comparison,
    get_market_average_comparison,
    get_market_ratio,
)
from rag.stock_agent.graph.tools.fetch.local_db import get_market_ohlcv
from rag.stock_agent.graph.prompts import (
    FETCH_TOOLS as TOOLS,
    FETCH_SYSTEM_MSG as SYSTEM_MSG,
)
from utils.logger import get_logger

logger = get_logger(__name__)


RESPONSE_SCHEMAS = [
    ResponseSchema(
        name="search_results",
        description="질문에 대한 주식데이터 조회 결과. 반드시 search_results라는 key로 반환해야 함.",
        type="Dict",
    )
]
PARSER = StructuredOutputParser.from_response_schemas(RESPONSE_SCHEMAS)


def fetch_stock_data(state: StockAgentState) -> StockAgentState:
    query = state["query"]
    context = state["context"]
    api_key = state["api_key"]

    # context에서 주식명 정보 추출하여 도구 선택 힌트 제공
    stock_info_hint = ""
    if context:
        if "names_to_tickers" in context:
            stock_list = context["names_to_tickers"].get("stock_list", [])
            if len(stock_list) > 1:
                # 유효한 티커가 있는 주식들만 필터링
                valid_stocks = [item for item in stock_list if item.get("ticker")]
                if valid_stocks:
                    stock_names = [item["name"] for item in valid_stocks]
                    stock_tickers = [item["ticker"] for item in valid_stocks]
                    stock_info_hint = f"""
                    [주식명 정보 - 복수 종목]
                    - 추출된 주식명: {stock_names}
                    - 해당 티커: {stock_tickers}
                    - 복수 주식명이 감지되었으므로 get_stock_comparison 도구 사용을 강력히 권장합니다.
                    - 질문이 비교 분석을 요구하는 경우 반드시 get_stock_comparison을 사용하세요.
                    """
                else:
                    stock_info_hint = """
                    [주의사항]
                    - 복수 주식명이 감지되었지만 유효한 티커를 찾을 수 없습니다.
                    - 다른 적절한 도구를 선택하거나 단일 종목 분석을 고려하세요.
                    """

    # 초기 메시지 설정
    initial_messages = [
        {
            "role": "system",
            "content": SYSTEM_MSG,
        },
        {
            "role": "user",
            "content": f"""
            question: {query}
            background_knowledge: {context}
            {stock_info_hint}
            """,
        },
    ]

    # 도구 함수 매핑
    tool_functions = {
        "get_historical_data": get_historical_data,
        "get_market_ohlcv": get_market_ohlcv,
        "get_stock_ranking": get_stock_ranking,
        "get_stock_comparison": get_stock_comparison,
        "get_market_average_comparison": get_market_average_comparison,
        "get_market_ratio": get_market_ratio,
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
        logger.error(f"Function calling 실패: {result.get('error', 'Unknown error')}")
        state["data"] = {
            "results": [],
            "total_count": 0,
            "summary": "요청 실패",
            "source": "fetch",
            "sql": "",
            "query_type": "stock_data_fetch",
            "parameters": {"query": query, "context": context},
        }
        return state

    # 새로운 응답 구조에 맞게 결과 처리
    tool_results = result.get("tool_results", [])
    fetch_result = {}

    # 도구 실행 결과를 처리
    for tool_result in tool_results:
        if tool_result.get("success", False):
            function_name = tool_result["function_name"]
            tool_data = tool_result["result"]
            fetch_result[function_name] = tool_data

    logger.info(f"--Fetch result: {fetch_result}--")

    # state["data"]에 저장
    state["data"] = {
        "results": [fetch_result] if fetch_result else [],
        "total_count": len(fetch_result) if fetch_result else 0,
        "summary": f"주식 데이터 조회 완료: {query}",
        "source": "fetch",
        "sql": "",
        "query_type": "stock_data_fetch",
        "parameters": {"query": query, "context": context},
    }
    return state
