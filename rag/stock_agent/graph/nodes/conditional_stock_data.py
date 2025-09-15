from rag.stock_agent.graph.state import StockAgentState
from rag.stock_agent.graph.clova_function_calling import process_function_calling
from rag.stock_agent.graph.tools.conditional.conditional_search import (
    get_stocks_by_price_range,
    get_stocks_by_volume,
    get_stocks_by_change_rate,
    get_stocks_by_volume_change,
    get_stocks_by_combined_conditions,
    get_top_stocks_by_price,
)
from rag.stock_agent.graph.prompts import (
    CONDITIONAL_TOOLS as TOOLS,
    CONDITIONAL_SYSTEM_MSG as SYSTEM_MSG,
)
from utils.logger import get_logger
import json

logger = get_logger(__name__)


def conditional_stock_data(state: StockAgentState) -> StockAgentState:
    query = state["query"]
    context = state["context"]
    api_key = state["api_key"]

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
            """,
        },
    ]

    # 도구 함수 매핑
    tool_functions = {
        "get_stocks_by_price_range": get_stocks_by_price_range,
        "get_stocks_by_volume": get_stocks_by_volume,
        "get_stocks_by_change_rate": get_stocks_by_change_rate,
        "get_stocks_by_volume_change": get_stocks_by_volume_change,
        "get_stocks_by_combined_conditions": get_stocks_by_combined_conditions,
        "get_top_stocks_by_price": get_top_stocks_by_price,
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
            "source": "conditional",
            "sql": "",
            "query_type": "conditional_search",
            "parameters": {"query": query, "context": context},
        }
        return state

    # 결과 정리
    tool_result = {"results": [], "total_count": 0}
    if result["tool_results"]:
        last_tool_result = result["tool_results"][-1]["result"]
        if isinstance(last_tool_result, dict):
            tool_result = last_tool_result
        else:
            try:
                if (
                    isinstance(last_tool_result, str)
                    and "{" in last_tool_result
                    and "}" in last_tool_result
                ):
                    start_idx = last_tool_result.find("{")
                    end_idx = last_tool_result.rfind("}") + 1
                    json_str = last_tool_result[start_idx:end_idx]
                    tool_result = json.loads(json_str)
            except:
                tool_result = {"results": [], "total_count": 0}

    # 결과 포맷팅
    results = tool_result.get("results", [])
    total_count = tool_result.get("total_count", 0)

    if total_count == 0:
        summary = f"조건 '{query}'에 해당하는 종목이 없습니다."
    else:
        summary = f"조건 '{query}'에 해당하는 종목 {total_count}개를 찾았습니다."
        if total_count > 10:
            summary += f" (상위 10개 표시)"

    logger.info(f"--Conditional search result: {total_count}개 종목 발견--")

    # state["data"]에 저장 (올바른 방식)
    state["data"] = {
        "results": results[:10],  # 최대 10개
        "total_count": total_count,
        "summary": summary,
        "source": "conditional",
        "sql": "",
        "query_type": "conditional_search",
        "parameters": {"query": query, "context": context},
    }

    return state
