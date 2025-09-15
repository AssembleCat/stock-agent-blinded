from pydantic import Field
from typing import TypedDict, Dict, Any, List


class StockAgentState(TypedDict):
    """
    data: 모든 데이터 조회 결과를 통합 저장
        - results: 실제 데이터 (최대 10개)
        - total_count: 전체 개수
        - summary: 요약 정보
        - source: 데이터 소스 (conditional, signal, sql, fetch)
        - sql: 생성된 SQL (SQL 관련인 경우)
        - query_type: 쿼리 타입
        - parameters: 사용된 파라미터
    context: 질문에 대한 배경지식
    response: 최종응답
    query: 사용자 질문
    query_category: 질문타입
    clarification_info: ambiguous_query에서 생성된 구체화 정보
    request_id: 사용자 요청 고유 ID

    # 퀴즈 세션 관리 필드들
    quiz_session_active: bool - 퀴즈 세션 활성 여부 (기본: False)
    quiz_current_question: Dict[str, Any] - 현재 퀴즈 문제 정보
    quiz_session_start_time: str - 퀴즈 세션 시작 시간 (ISO format)
    quiz_hint_used: bool - 힌트 사용 여부 (기본: False)
    quiz_session_phase: str - 퀴즈 세션 단계 ("inactive", "asking", "processing", "completed")
    quiz_session_id: str - 세션 고유 ID
    """

    api_key: str
    data: Dict[str, Any]
    context: dict
    query: str
    response: str
    query_category: str
    clarification_info: Dict[str, Any]
    request_id: str

    # 퀴즈 세션 관리 필드들
    quiz_session_active: bool
    quiz_current_question: Dict[str, Any]
    quiz_session_start_time: str
    quiz_hint_used: bool
    quiz_session_phase: str
    quiz_session_id: str


def default_stock_agent_state() -> StockAgentState:
    """기본 StockAgentState 생성"""
    return StockAgentState(
        api_key="",
        data={},
        context={},
        query="",
        response="",
        query_category="",
        clarification_info={},
        request_id="",
        # 퀴즈 세션 기본값
        quiz_session_active=False,
        quiz_current_question={},
        quiz_session_start_time="",
        quiz_hint_used=False,
        quiz_session_phase="inactive",
        quiz_session_id="",
    )
