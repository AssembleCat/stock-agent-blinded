from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from rag.stock_agent.graph.state import StockAgentState
from rag.stock_agent.graph.tools.quiz.database import QuizDatabase
from utils.logger import get_logger

logger = get_logger(__name__)


class QuizSessionPhase(Enum):
    """퀴즈 세션 단계"""

    INACTIVE = "inactive"  # 비활성 상태
    ASKING = "asking"  # 문제 제시 중
    PROCESSING = "processing"  # 답변 처리 중
    COMPLETED = "completed"  # 완료됨


class QuizSessionManager:
    """퀴즈 세션 관리 클래스"""

    # 세션 타임아웃 (분)
    SESSION_TIMEOUT_MINUTES = 10

    @classmethod
    def start_new_session(
        cls, state: StockAgentState, quiz_data: Dict[str, Any]
    ) -> StockAgentState:
        """
        새로운 퀴즈 세션을 시작합니다.

        Args:
            state: 현재 StockAgentState
            quiz_data: 선택된 퀴즈 데이터

        Returns:
            업데이트된 StockAgentState
        """
        try:
            # 기존 세션이 있다면 종료
            if state.get("quiz_session_active", False):
                logger.warning("기존 활성 세션이 있어 강제 종료합니다.")
                state = cls.end_session(state)

            # 세션 ID 생성
            session_id = QuizDatabase.generate_session_id()
            current_time = datetime.now().isoformat()

            # 새 세션 정보 설정
            state["quiz_session_active"] = True
            state["quiz_session_id"] = session_id
            state["quiz_session_start_time"] = current_time
            state["quiz_current_question"] = quiz_data
            state["quiz_hint_used"] = False
            state["quiz_session_phase"] = QuizSessionPhase.ASKING.value

            logger.info(
                f"새 퀴즈 세션 시작 - ID: {session_id}, 퀴즈: {quiz_data.get('id', 'Unknown')}"
            )
            return state

        except Exception as e:
            logger.error(f"퀴즈 세션 시작 중 오류: {e}")
            return state

    @classmethod
    def update_session_phase(
        cls, state: StockAgentState, new_phase: QuizSessionPhase
    ) -> StockAgentState:
        """
        세션 단계를 업데이트합니다.

        Args:
            state: 현재 StockAgentState
            new_phase: 새로운 단계

        Returns:
            업데이트된 StockAgentState
        """
        try:
            if not cls.is_session_active(state):
                logger.warning("활성 세션이 없어 단계 업데이트를 건너뜁니다.")
                return state

            old_phase = state.get("quiz_session_phase", "unknown")
            state["quiz_session_phase"] = new_phase.value

            logger.info(f"세션 단계 변경: {old_phase} -> {new_phase.value}")
            return state

        except Exception as e:
            logger.error(f"세션 단계 업데이트 중 오류: {e}")
            return state

    @classmethod
    def end_session(
        cls,
        state: StockAgentState,
        save_to_db: bool = False,
        user_answer: str = "",
        is_correct: bool = False,
        request_id: str = "",
        reward_info: Dict[str, Any] = None,
    ) -> StockAgentState:
        """
        퀴즈 세션을 종료합니다.

        Args:
            state: 현재 StockAgentState
            save_to_db: 데이터베이스 저장 여부
            user_answer: 사용자 답변 (DB 저장용)
            is_correct: 정답 여부 (DB 저장용)
            request_id: 사용자 요청 고유 ID (DB 저장용)
            reward_info: 보상 정보 (DB 저장용)

        Returns:
            업데이트된 StockAgentState
        """
        try:
            session_id = state.get("quiz_session_id", "")
            current_quiz = state.get("quiz_current_question", {})

            # 데이터베이스 저장
            if save_to_db and current_quiz:
                try:
                    if reward_info is None:
                        reward_info = {"stock": "", "amount": 0}

                    success = QuizDatabase.save_quiz_result(
                        request_id=request_id,
                        quiz_id=current_quiz.get("id", 0),
                        quiz_question=current_quiz.get("question", ""),
                        correct_answer=current_quiz.get("correct_answer", {}).get(
                            "company", ""
                        ),
                        user_answer=user_answer,
                        is_correct=is_correct,
                        hint_used=state.get("quiz_hint_used", False),
                        reward_stock=reward_info.get("stock", ""),
                        reward_amount=reward_info.get("amount", 0),
                    )

                    if success:
                        logger.info(f"퀴즈 결과 DB 저장 완료 - 사용자: {request_id}")
                    else:
                        logger.error(f"퀴즈 결과 DB 저장 실패 - 사용자: {request_id}")

                except Exception as e:
                    logger.error(f"퀴즈 결과 DB 저장 중 오류: {e}")

            # 세션 상태 초기화
            state["quiz_session_active"] = False
            state["quiz_session_id"] = ""
            state["quiz_session_start_time"] = ""
            state["quiz_current_question"] = {}
            state["quiz_hint_used"] = False
            state["quiz_session_phase"] = QuizSessionPhase.INACTIVE.value

            logger.info(f"퀴즈 세션 종료 - ID: {session_id}")
            return state

        except Exception as e:
            logger.error(f"퀴즈 세션 종료 중 오류: {e}")
            return state

    @classmethod
    def is_session_active(cls, state: StockAgentState) -> bool:
        """
        현재 활성 퀴즈 세션이 있는지 확인합니다.

        Args:
            state: 현재 StockAgentState

        Returns:
            활성 세션 여부
        """
        return state.get("quiz_session_active", False)

    @classmethod
    def is_session_expired(cls, state: StockAgentState) -> bool:
        """
        현재 세션이 만료되었는지 확인합니다.

        Args:
            state: 현재 StockAgentState

        Returns:
            세션 만료 여부
        """
        try:
            if not cls.is_session_active(state):
                return False

            start_time_str = state.get("quiz_session_start_time", "")
            if not start_time_str:
                return True

            start_time = datetime.fromisoformat(start_time_str)
            current_time = datetime.now()
            elapsed_time = current_time - start_time

            is_expired = elapsed_time > timedelta(minutes=cls.SESSION_TIMEOUT_MINUTES)

            if is_expired:
                logger.warning(f"퀴즈 세션 만료 감지 - 경과시간: {elapsed_time}")

            return is_expired

        except Exception as e:
            logger.error(f"세션 만료 확인 중 오류: {e}")
            return True  # 오류 시 만료로 간주

    @classmethod
    def cleanup_expired_session(cls, state: StockAgentState) -> StockAgentState:
        """
        만료된 세션을 정리합니다.

        Args:
            state: 현재 StockAgentState

        Returns:
            업데이트된 StockAgentState
        """
        try:
            if cls.is_session_expired(state):
                logger.info("만료된 세션을 정리합니다.")
                state = cls.end_session(state)

            return state

        except Exception as e:
            logger.error(f"만료된 세션 정리 중 오류: {e}")
            return state

    @classmethod
    def get_session_info(cls, state: StockAgentState) -> Dict[str, Any]:
        """
        현재 세션 정보를 반환합니다.

        Args:
            state: 현재 StockAgentState

        Returns:
            세션 정보 딕셔너리
        """
        try:
            if not cls.is_session_active(state):
                return {
                    "active": False,
                    "phase": "inactive",
                    "session_id": "",
                    "start_time": "",
                    "elapsed_minutes": 0,
                    "remaining_minutes": cls.SESSION_TIMEOUT_MINUTES,
                    "current_quiz": {},
                }

            start_time_str = state.get("quiz_session_start_time", "")
            elapsed_minutes = 0
            remaining_minutes = cls.SESSION_TIMEOUT_MINUTES

            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                elapsed_time = datetime.now() - start_time
                elapsed_minutes = round(elapsed_time.total_seconds() / 60, 1)
                remaining_minutes = max(
                    0, cls.SESSION_TIMEOUT_MINUTES - elapsed_minutes
                )

            return {
                "active": True,
                "phase": state.get("quiz_session_phase", "unknown"),
                "session_id": state.get("quiz_session_id", ""),
                "start_time": start_time_str,
                "elapsed_minutes": elapsed_minutes,
                "remaining_minutes": remaining_minutes,
                "current_quiz": state.get("quiz_current_question", {}),
                "hint_used": state.get("quiz_hint_used", False),
            }

        except Exception as e:
            logger.error(f"세션 정보 조회 중 오류: {e}")
            return {"active": False, "error": str(e)}

    @classmethod
    def validate_session_transition(
        cls, state: StockAgentState, target_phase: QuizSessionPhase
    ) -> bool:
        """
        세션 단계 전환이 유효한지 확인합니다.

        Args:
            state: 현재 StockAgentState
            target_phase: 목표 단계

        Returns:
            전환 유효성
        """
        try:
            current_phase = state.get("quiz_session_phase", "inactive")

            # 유효한 전환 규칙 정의
            valid_transitions = {
                QuizSessionPhase.INACTIVE.value: [QuizSessionPhase.ASKING.value],
                QuizSessionPhase.ASKING.value: [
                    QuizSessionPhase.PROCESSING.value,
                    QuizSessionPhase.COMPLETED.value,
                ],
                QuizSessionPhase.PROCESSING.value: [QuizSessionPhase.COMPLETED.value],
                QuizSessionPhase.COMPLETED.value: [QuizSessionPhase.INACTIVE.value],
            }

            allowed_targets = valid_transitions.get(current_phase, [])
            is_valid = target_phase.value in allowed_targets

            if not is_valid:
                logger.warning(
                    f"잘못된 세션 단계 전환: {current_phase} -> {target_phase.value}"
                )

            return is_valid

        except Exception as e:
            logger.error(f"세션 전환 유효성 확인 중 오류: {e}")
            return False
