from rag.stock_agent.graph.state import StockAgentState
from rag.stock_agent.graph.clova_function_calling import process_function_calling
from rag.stock_agent.graph.tools.signal.signal_tools import (
    get_bollinger_touch_stocks,
    get_cross_signal_stocks,
    get_cross_signal_count_by_stock,
    get_volume_surge_stocks,
    get_rsi_stocks,
    get_ma_deviation_stocks,
    get_volume_deviation_stocks,
)
from rag.stock_agent.graph.prompts import SIGNAL_TOOLS as TOOLS, SIGNAL_SYSTEM_MSG as SYSTEM_MSG
from utils.logger import get_logger
import json

logger = get_logger(__name__)


def signal_stock_data(state: StockAgentState) -> StockAgentState:
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
        "get_bollinger_touch_stocks": get_bollinger_touch_stocks,
        "get_cross_signal_stocks": get_cross_signal_stocks,
        "get_cross_signal_count_by_stock": get_cross_signal_count_by_stock,
        "get_volume_surge_stocks": get_volume_surge_stocks,
        "get_rsi_stocks": get_rsi_stocks,
        "get_ma_deviation_stocks": get_ma_deviation_stocks,
        "get_volume_deviation_stocks": get_volume_deviation_stocks,
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
            "source": "signal",
            "sql": "",
            "query_type": "technical_analysis",
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

    # create_result_response 함수가 반환하는 구조 처리
    results = tool_result.get("results", [])
    total_count = tool_result.get("total_count", 0)
    returned_count = tool_result.get("returned_count", len(results))

    if total_count == 0:
        summary = f"조건 '{query}'에 해당하는 종목이 없습니다."
    else:
        summary = f"조건 '{query}'에 해당하는 종목 {total_count}개를 찾았습니다."
        if returned_count < total_count:
            summary += f" (상위 {returned_count}개 표시)"

    logger.info(f"--Signal search result: {total_count}개 종목 발견--")

    # state["data"]에 저장 (create_result_response 구조 반영)
    state["data"] = {
        "results": results,  # create_result_response에서 이미 제한된 결과
        "total_count": total_count,
        "summary": summary,
        "source": "signal",
        "sql": "",
        "query_type": "technical_analysis",
        "parameters": {"query": query, "context": context},
    }

    return state