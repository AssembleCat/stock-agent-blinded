from typing import Dict, Any
from rag.stock_agent.graph.state import StockAgentState
from utils.logger import get_logger

logger = get_logger(__name__)


def quiz_generate_response(state: StockAgentState) -> StockAgentState:
    """
    퀴즈 전용 응답 생성 노드입니다.
    quiz_stock_data에서 처리된 결과를 최종 사용자 응답으로 변환합니다.
    """
    try:
        data = state.get("data", {})

        # 퀴즈 데이터 처리
        response_text = format_quiz_response(data)

        state["response"] = response_text
        logger.debug("퀴즈 응답 완료")

        return state

    except Exception as e:
        logger.error(f"퀴즈 응답 생성 중 오류: {e}")
        error_response = (
            "퀴즈 응답을 생성하는 중 오류가 발생했습니다. 다시 시도해주세요."
        )
        state["response"] = error_response
        return state


def format_quiz_response(data: Dict[str, Any]) -> str:
    """
    퀴즈 데이터를 사용자에게 보여질 응답 형식으로 변환합니다.

    Args:
        data: quiz_stock_data에서 생성된 데이터

    Returns:
        formatted response text
    """
    try:
        source = data.get("source", "")

        if source != "quiz":
            return "퀴즈 데이터 형식이 올바르지 않습니다."

        results = data.get("results", [])
        if not results:
            return "퀴즈 데이터가 없습니다."

        quiz_result = results[0]  # 퀴즈는 단일 결과

        # 퀴즈 생성인 경우
        if quiz_result.get("type") == "quiz_generation":
            quiz_text = quiz_result.get("quiz_text", "")
            return quiz_text

        # 답변 확인인 경우 (정답)
        elif quiz_result.get("type") == "answer_checking":
            result_text = quiz_result.get("result_text", "")
            return result_text

        # 오답 + 힌트 제공인 경우
        elif quiz_result.get("type") == "wrong_answer_with_hint":
            wrong_answer_message = quiz_result.get("wrong_answer_message", "")
            return wrong_answer_message

        # 힌트 제공인 경우
        elif quiz_result.get("type") == "hint_provided":
            hint_text = quiz_result.get("hint_text", "")
            return hint_text

        # 세션 완료인 경우
        elif quiz_result.get("type") == "session_completed":
            completion_text = quiz_result.get("completion_text", "")
            return completion_text

        # 오류인 경우
        elif quiz_result.get("type") == "error":
            error_text = quiz_result.get("error_text", "")
            suggestion = quiz_result.get("suggestion", "")
            return f"{error_text}\n\n{suggestion}" if suggestion else error_text

        # 기타 경우
        return "퀴즈 처리가 완료되었습니다."

    except Exception as e:
        logger.error(f"퀴즈 응답 포맷팅 중 오류: {e}")
        return "퀴즈 응답을 생성하는 중 오류가 발생했습니다."
