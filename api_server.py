from fastapi import FastAPI, HTTPException, Request
from typing import Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils.logger import get_logger
from rag.stock_agent.graph.graph import app as agent
from rag.stock_agent.graph.state import default_stock_agent_state, StockAgentState
from rag.stock_agent.graph.tools.quiz.session_manager import QuizSessionManager

load_dotenv()
logger = get_logger(__name__)

app = FastAPI(title="Miraeasset Stock Agent API")

# 세션 저장소
session_store: Dict[str, StockAgentState] = {}
session_timestamps: Dict[str, datetime] = {}

# 세션 설정
SESSION_TIMEOUT_MINUTES = 10  # 퀴즈 세션 10분 만료
MAX_SESSIONS = 5  # 최대 세션은 5개!


def get_session_state(request_id: str) -> StockAgentState:
    """request_id로 세션 상태 조회 또는 새로 생성"""

    # 만료된 세션들 정리
    cleanup_expired_sessions()

    # 기존 세션 복원
    if request_id and request_id in session_store:
        # 활동 시간 업데이트
        session_timestamps[request_id] = datetime.now()
        logger.info(f"기존 세션 복원 - request_id: {request_id}")
        return session_store[request_id]

    # 새 세션 생성
    state = default_stock_agent_state()
    if request_id:
        session_store[request_id] = state
        session_timestamps[request_id] = datetime.now()
        logger.info(f"새 세션 생성 - request_id: {request_id}")

    return state


def save_session_state(request_id: str, state: StockAgentState):
    """세션 상태 저장"""
    if request_id:
        session_store[request_id] = state
        session_timestamps[request_id] = datetime.now()

        # 퀴즈 세션 상태 로깅
        if state.get("quiz_session_active"):
            logger.info(
                f"퀴즈 세션 저장 - request_id: {request_id}, 단계: {state.get('quiz_session_phase')}"
            )


def cleanup_expired_sessions():
    """만료된 세션들 정리"""
    current_time = datetime.now()
    expired_sessions = []

    for session_id, timestamp in list(session_timestamps.items()):
        # 10분 비활성 시 만료
        if current_time - timestamp > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            expired_sessions.append(session_id)
        # 퀴즈 세션의 경우 QuizSessionManager로도 체크
        elif session_id in session_store:
            state = session_store[session_id]
            if state.get("quiz_session_active"):
                if QuizSessionManager.is_session_expired(state):
                    expired_sessions.append(session_id)

    # 만료된 세션들 삭제
    for session_id in expired_sessions:
        session_store.pop(session_id, None)
        session_timestamps.pop(session_id, None)
        logger.info(f"만료된 세션 정리 - session_id: {session_id}")

    # 최대 세션 수 초과 시 오래된 세션부터 삭제제
    if len(session_store) > MAX_SESSIONS:
        sorted_sessions = sorted(session_timestamps.items(), key=lambda x: x[1])
        sessions_to_remove = sorted_sessions[: len(session_store) - MAX_SESSIONS]

        for session_id, _ in sessions_to_remove:
            session_store.pop(session_id, None)
            session_timestamps.pop(session_id, None)
            logger.warning(f"메모리 보호를 위한 세션 삭제 - session_id: {session_id}")


@app.get("/agent")
async def chat_with_agent(request: Request):
    """
    주식 에이전트와 대화하는 API 엔드포인트 (세션 관리 지원)

    Args:
        question: 사용자 질문
        api_key: Authorization 헤더에서 추출된 API 키
        request_id: X-NCP-CLOVASTUDIO-REQUEST-ID 헤더에서 추출된 request_id
    """
    try:
        request_id = request.headers.get("X-NCP-CLOVASTUDIO-REQUEST-ID")
        api_key = request.headers.get("Authorization")
        question = request.query_params.get("question")

        # 민감정보 노출 방지: API 키 원문은 로그하지 않음
        logger.info(
            f"API 요청 받음 - api_key_provided: {bool(api_key)}, request_id: {request_id}, question: {question}"
        )

        if not question:
            raise HTTPException(
                status_code=400, detail="question(질문) 요청이 비었습니다."
            )
        if not request_id:
            raise HTTPException(status_code=400, detail="request_id 요청이 비었습니다.")

        # 세션 기반 상태 관리
        state = get_session_state(request_id)
        state["query"] = question
        state["api_key"] = api_key
        state["request_id"] = request_id

        logger.info("--그래프 실행 시작--")
        result = agent.invoke(state)

        # 세션 상태 저장
        save_session_state(request_id, result)

        return {"answer": result.get("response", "응답을 생성할 수 없습니다.")}

    except Exception as e:
        logger.error(f"API 요청 처리 중 오류 발생: {e.with_traceback()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/sessions")
async def get_sessions_info():
    """현재 활성 세션 정보 조회 (디버깅용)"""
    sessions_info = []
    current_time = datetime.now()

    for session_id, state in session_store.items():
        timestamp = session_timestamps.get(session_id)
        elapsed = (current_time - timestamp).total_seconds() / 60 if timestamp else 0

        sessions_info.append(
            {
                "session_id": session_id,
                "quiz_active": state.get("quiz_session_active", False),
                "quiz_phase": state.get("quiz_session_phase", ""),
                "elapsed_minutes": round(elapsed, 1),
                "last_activity": timestamp.isoformat() if timestamp else None,
            }
        )

    return {"total_sessions": len(session_store), "sessions": sessions_info}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
