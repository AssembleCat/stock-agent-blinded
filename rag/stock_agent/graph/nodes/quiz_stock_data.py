from typing import Dict, Any
from rag.stock_agent.graph.state import StockAgentState
from rag.stock_agent.graph.tools.quiz.parser import (
    parse_quiz_file,
    get_random_quiz,
    get_unplayed_quiz,
)
from rag.stock_agent.graph.tools.quiz.checker import QuizAnswerChecker
from rag.stock_agent.graph.tools.quiz.info_provider import quiz_info_provider
from rag.stock_agent.graph.tools.quiz.session_manager import (
    QuizSessionManager,
    QuizSessionPhase,
)
from rag.stock_agent.graph.tools.quiz.database import QuizDatabase
from rag.stock_agent.graph.tools.news.naver_news_search import naver_news_search_tool
from utils.logger import get_logger
import os

logger = get_logger(__name__)


def quiz_stock_data(state: StockAgentState) -> StockAgentState:
    """
    퀴즈 관련 모든 로직을 처리하는 메인 노드
    - 새로운 퀴즈 시작
    - 사용자 답변 처리 (정답/오답/힌트)
    - 세션 관리
    """

    try:
        query = state.get("query", "").strip()

        # 만료된 세션 정리
        state = QuizSessionManager.cleanup_expired_session(state)

        # 현재 세션 상태 확인
        current_phase = state.get("quiz_session_phase", QuizSessionPhase.INACTIVE.value)
        is_session_active = QuizSessionManager.is_session_active(state)

        # 상태에 따른 처리 분기
        if current_phase == QuizSessionPhase.INACTIVE.value:
            # 새로운 퀴즈 시작
            return _handle_quiz_start(state, query)

        elif current_phase == QuizSessionPhase.ASKING.value:
            # 사용자 답변 처리
            return _handle_user_answer(state, query)

        elif current_phase == QuizSessionPhase.PROCESSING.value:
            # 처리 중 상태 (일반적으로 이 단계는 빠르게 지나감)
            logger.debug("처리 중 단계에서 다시 호출됨 - completed로 전환")
            state = QuizSessionManager.update_session_phase(
                state, QuizSessionPhase.COMPLETED
            )
            return _handle_session_completion(state)

        elif current_phase == QuizSessionPhase.COMPLETED.value:
            # 완료 상태 - 세션 종료
            return _handle_session_completion(state)

        else:
            # 알 수 없는 상태
            logger.error(f"알 수 없는 퀴즈 세션 단계: {current_phase}")
            state = QuizSessionManager.end_session(state)
            return _generate_error_response(
                state, "퀴즈 세션 상태 오류가 발생했습니다."
            )

    except Exception as e:
        logger.error(f"퀴즈 노드 처리 중 오류: {e}")
        state = QuizSessionManager.end_session(state)
        return _generate_error_response(
            state, f"퀴즈 처리 중 오류가 발생했습니다: {str(e)}"
        )


def _handle_quiz_start(state: StockAgentState, query: str) -> StockAgentState:
    """새로운 퀴즈 시작을 처리합니다."""

    try:
        logger.info("새로운 퀴즈 세션 시작 처리")

        # Quiz.txt 파일 로드
        quiz_file_path = "quiz_data/Quiz.txt"
        if not os.path.exists(quiz_file_path):
            logger.error(f"퀴즈 파일을 찾을 수 없습니다: {quiz_file_path}")
            return _generate_error_response(state, "퀴즈 파일을 찾을 수 없습니다.")

        # 퀴즈 파싱
        quizzes = parse_quiz_file(quiz_file_path)
        if not quizzes:
            logger.error("유효한 퀴즈를 로드할 수 없습니다.")
            return _generate_error_response(state, "유효한 퀴즈를 로드할 수 없습니다.")

        # 사용자별 미완료 퀴즈 선택
        request_id = state.get("request_id", "")
        selected_quiz = get_unplayed_quiz(quizzes, request_id)
        if not selected_quiz:
            logger.error("퀴즈 선택에 실패했습니다.")
            return _generate_error_response(state, "퀴즈 선택에 실패했습니다.")

        # 세션 시작
        state = QuizSessionManager.start_new_session(state, selected_quiz)

        # 퀴즈 시작 메시지 생성
        quiz_message = quiz_info_provider.generate_quiz_start_message(selected_quiz)

        # 응답 데이터 구성
        state["data"] = {
            "source": "quiz",
            "results": [
                {
                    "type": "quiz_generation",
                    "quiz_text": quiz_message,
                    "quiz_data": selected_quiz,
                    "session_info": QuizSessionManager.get_session_info(state),
                }
            ],
            "total_count": 1,
            "summary": f"퀴즈 #{selected_quiz.get('id', 'Unknown')} 시작",
            "query_type": "quiz_start",
        }

        logger.info(
            f"새 퀴즈 세션 시작 - ID: {state.get('quiz_session_id')}, 퀴즈: {selected_quiz['id']}"
        )
        logger.debug(f"퀴즈 {selected_quiz.get('id', 'Unknown')}번 시작")

        return state

    except Exception as e:
        logger.error(f"퀴즈 시작 처리 중 오류: {e}")
        return _generate_error_response(
            state, f"퀴즈 시작 중 오류가 발생했습니다: {str(e)}"
        )


def _handle_user_answer(state: StockAgentState, user_answer: str) -> StockAgentState:
    """사용자 답변을 처리합니다."""

    try:
        # 현재 퀴즈 정보 조회
        current_quiz = state.get("quiz_current_question", {})
        if not current_quiz:
            logger.error("현재 활성 퀴즈가 없습니다.")
            state = QuizSessionManager.end_session(state)
            return _generate_error_response(state, "활성화된 퀴즈가 없습니다.")

        # 힌트 요청 처리
        if user_answer.lower() in [
            "힌트",
            "hint",
            "도움",
            "help",
            "힌트 주세요",
            "힌트주세요",
            "힌트 좀",
            "힌트좀",
            "도움 주세요",
            "도움주세요",
            "도와주세요",
            "도와줘",
            "모르겠어",
            "모르겠어요",
            "모르겠다",
            "몰라",
            "몰라요",
            "어려워",
            "어려워요",
            "어렵다",
            "어려운데",
            "잘 모르겠어",
            "잘 모르겠어요",
            "잘 모르겠네",
            "헷갈려",
            "헷갈려요",
            "헷갈린다",
            "애매해",
            "애매해요",
            "뭐지",
            "뭐야",
            "뭔지",
            "뭔가요",
        ]:
            logger.info("힌트 요청")
            return _handle_hint_request(state, current_quiz)

        # 처리 중 단계로 전환
        state = QuizSessionManager.update_session_phase(
            state, QuizSessionPhase.PROCESSING
        )

        # 답변 검증
        checker = QuizAnswerChecker()
        answer_result = checker.check_answer(current_quiz, user_answer)

        if not answer_result.get("success", False):
            logger.error(f"답변 검증 실패: {answer_result}")
            return _generate_error_response(state, "답변 검증 중 오류가 발생했습니다.")

        is_correct = answer_result.get("is_correct", False)

        # 정답 처리
        if is_correct:
            logger.info("✅ 정답!")
            return _handle_correct_answer(
                state, current_quiz, user_answer, answer_result
            )

        # 오답 처리 - 힌트 제공하고 퀴즈 계속
        else:
            logger.info("❌ 오답 - 힌트 제공")
            return _handle_wrong_answer(state, current_quiz, user_answer, answer_result)

    except Exception as e:
        logger.error(f"답변 처리 중 오류: {e}")
        state = QuizSessionManager.end_session(state)
        return _generate_error_response(
            state, f"답변 처리 중 오류가 발생했습니다: {str(e)}"
        )


def _handle_correct_answer(
    state: StockAgentState,
    quiz_data: Dict[str, Any],
    user_answer: str,
    answer_result: Dict[str, Any],
) -> StockAgentState:
    """정답 처리 - 정보 패키지 제공하고 세션 종료"""

    try:
        request_id = state.get("request_id", "")

        # 정보 패키지 생성
        info_package = quiz_info_provider.generate_answer_package(
            quiz_data=quiz_data,
            user_answer=user_answer,
            is_correct=True,
            answer_check_result=answer_result,
            request_id=request_id,
        )

        # 세션 완료로 전환
        state = QuizSessionManager.update_session_phase(
            state, QuizSessionPhase.COMPLETED
        )

        # 데이터베이스 저장용 보상 정보 추출
        reward_info = info_package.get("reward_info", {})
        stock_name = reward_info.get(
            "stock_name", quiz_data.get("correct_answer", {}).get("company", "")
        )
        reward_amount = reward_info.get("amount", 0)

        # 세션 종료 및 DB 저장
        state = QuizSessionManager.end_session(
            state=state,
            save_to_db=True,
            user_answer=user_answer,
            is_correct=True,
            request_id=request_id,
            reward_info={
                "stock": stock_name,
                "amount": reward_amount,
            },
        )

        # 결과 메시지 생성
        result_message = _format_answer_result(info_package)

        # 응답 데이터 구성
        state["data"] = {
            "source": "quiz",
            "results": [
                {
                    "type": "answer_checking",
                    "result_text": result_message,
                    "info_package": info_package,
                    "is_correct": True,
                    "session_completed": True,
                }
            ],
            "total_count": 1,
            "summary": f"퀴즈 정답: {user_answer}",
            "query_type": "quiz_answer",
        }

        logger.debug("정보 패키지 제공")
        return state

    except Exception as e:
        logger.error(f"정답 처리 중 오류: {e}")
        state = QuizSessionManager.end_session(state)
        return _generate_error_response(
            state, f"정답 처리 중 오류가 발생했습니다: {str(e)}"
        )


def _handle_wrong_answer(
    state: StockAgentState,
    quiz_data: Dict[str, Any],
    user_answer: str,
    answer_result: Dict[str, Any],
) -> StockAgentState:
    """오답 처리 - 오답 알림 + 힌트 제공하고 퀴즈 계속"""

    try:
        # asking 상태로 되돌리기 (퀴즈 계속)
        state = QuizSessionManager.update_session_phase(state, QuizSessionPhase.ASKING)

        # 힌트 생성
        checker = QuizAnswerChecker()
        hint_text = checker.get_hint(quiz_data)

        # 정답 정보 추출
        correct_answer = quiz_data.get("correct_answer", {})
        correct_option = correct_answer.get("option", "")
        correct_company = correct_answer.get("company", "")

        # 오답 + 힌트 메시지 구성
        wrong_answer_message = f"""**오답입니다!**

입력하신 답변: {user_answer}
정답은 다른 선택지입니다.

💡 **힌트**: {hint_text}

다시 답변해보세요!"""

        # 응답 데이터 구성 (세션은 asking 상태 유지)
        state["data"] = {
            "source": "quiz",
            "results": [
                {
                    "type": "wrong_answer_with_hint",
                    "wrong_answer_message": wrong_answer_message,
                    "user_answer": user_answer,
                    "hint_text": hint_text,
                    "quiz_continues": True,
                    "session_info": QuizSessionManager.get_session_info(state),
                }
            ],
            "total_count": 1,
            "summary": f"퀴즈 #{quiz_data.get('id', 'Unknown')} 오답 + 힌트 제공",
            "query_type": "quiz_wrong_answer",
        }

        logger.info("오답 처리 완료 - 퀴즈 계속")
        return state

    except Exception as e:
        logger.error(f"오답 처리 중 오류: {e}")
        return _generate_error_response(
            state, f"오답 처리 중 오류가 발생했습니다: {str(e)}"
        )


def _handle_hint_request(
    state: StockAgentState, quiz_data: Dict[str, Any]
) -> StockAgentState:
    """힌트 요청을 처리합니다."""

    try:
        # 힌트 사용 표시
        state["quiz_hint_used"] = True

        # 1. 기존 힌트 생성
        checker = QuizAnswerChecker()
        traditional_hint = checker.get_hint(quiz_data)

        # 2. 네이버 뉴스 기반 힌트 생성
        news_hint_result = naver_news_search_tool.generate_news_based_hint(quiz_data)

        # 3. 힌트 메시지 통합 구성
        hint_message = _combine_hints(traditional_hint, news_hint_result)

        # 응답 데이터 구성 (세션은 asking 상태 유지)
        state["data"] = {
            "source": "quiz",
            "results": [
                {
                    "type": "hint_provided",
                    "hint_text": hint_message,
                    "quiz_continues": True,
                    "session_info": QuizSessionManager.get_session_info(state),
                    "hint_details": {
                        "traditional_hint": traditional_hint,
                        "news_hint": news_hint_result,
                    },
                }
            ],
            "total_count": 1,
            "summary": f"퀴즈 #{quiz_data.get('id', 'Unknown')} 힌트 제공 (기존 + 뉴스)",
            "query_type": "quiz_hint",
        }

        logger.info("힌트 제공 완료 (기존 + 뉴스 기반)")
        return state

    except Exception as e:
        logger.error(f"힌트 처리 중 오류: {e}")
        return _generate_error_response(
            state, f"힌트 제공 중 오류가 발생했습니다: {str(e)}"
        )


def _handle_session_completion(state: StockAgentState) -> StockAgentState:
    """완료된 세션을 정리합니다."""

    try:
        logger.debug("세션 완료 처리")

        # 세션 종료
        state = QuizSessionManager.end_session(state)

        # 완료 메시지 생성
        completion_message = "퀴즈가 완료되었습니다. '주식퀴즈도전'으로 새로운 퀴즈를 시작할 수 있습니다!"

        # 응답 데이터 구성
        state["data"] = {
            "source": "quiz",
            "results": [
                {
                    "type": "session_completed",
                    "completion_text": completion_message,
                    "new_quiz_available": True,
                }
            ],
            "total_count": 1,
            "summary": "퀴즈 세션 완료",
            "query_type": "quiz_completion",
        }

        return state

    except Exception as e:
        logger.error(f"세션 완료 처리 중 오류: {e}")
        return _generate_error_response(
            state, f"세션 완료 처리 중 오류가 발생했습니다: {str(e)}"
        )


def _combine_hints(traditional_hint: str, news_hint_result: Dict[str, Any]) -> str:
    """뉴스 기반 힌트만 표시합니다."""

    try:
        message_parts = []

        # 뉴스 기반 힌트만 추가
        if news_hint_result.get("success", False):
            news_hint_message = news_hint_result.get("hint_message", "")
            if news_hint_message:
                message_parts.append(news_hint_message)
                message_parts.append("")
        else:
            # 뉴스 힌트 실패 시 폴백 메시지
            fallback_message = news_hint_result.get("hint_message", "")
            if fallback_message:
                message_parts.append(f"📰 {fallback_message}")
                message_parts.append("")

        # 마무리 메시지
        message_parts.append("---")
        message_parts.append("퀴즈는 계속 진행 중입니다. 답변을 입력해주세요!")

        return "\n".join(message_parts)

    except Exception as e:
        logger.error(f"힌트 통합 중 오류: {e}")
        # 오류 시 간단한 메시지 반환
        return "힌트를 제공할 수 없습니다.\n\n퀴즈는 계속 진행 중입니다. 답변을 입력해주세요!"


def _format_answer_result(info_package: Dict[str, Any]) -> str:
    """답변 결과를 사용자 친화적인 메시지로 포맷합니다."""

    try:
        from rag.stock_agent.graph.tools.quiz.user_reward_manager import (
            user_reward_manager,
        )

        message_parts = []

        # 1. 정답/오답 설명
        explanation = info_package.get("explanation", "")
        if explanation:
            message_parts.append(explanation)
            message_parts.append("")

        # 2. 기업 통찰 스낵글 (정답인 경우에만)
        company_insight = info_package.get("company_insight", "")
        if company_insight:
            message_parts.append("📚 **기업 정보**")
            message_parts.append(company_insight)
            message_parts.append("")

        # 3. 보상 정보
        reward_info = info_package.get("reward_info", {})

        # 보상 제한인 경우
        if reward_info.get("reward_limited", False):
            limitation_message = reward_info.get("limitation_message", "")
            if limitation_message:
                message_parts.append(limitation_message)
                message_parts.append("")

        # 정상 보상인 경우
        elif reward_info.get("eligible", False):
            message_parts.append("🎁 **보상**")
            message_parts.append(reward_info.get("message", ""))
            closing_price = reward_info.get("closing_price", "")
            if closing_price:
                message_parts.append(f"종가: {closing_price}")
            message_parts.append("")

        # 4. 사용자 전체 보상 현황
        user_rewards_info = info_package.get("user_rewards_info", {})
        if user_rewards_info.get("success", False):
            rewards_display = user_reward_manager.format_user_rewards_display(
                user_rewards_info
            )
            message_parts.append(rewards_display)
            message_parts.append("")

        # 5. 마무리 메시지
        message_parts.append("---")
        message_parts.append("🎯 새로운 퀴즈를 원하시면 '주식퀴즈도전'을 입력해주세요!")

        return "\n".join(message_parts)

    except Exception as e:
        logger.error(f"결과 메시지 포맷 중 오류: {e}")
        return "답변 결과를 표시하는 중 오류가 발생했습니다."


def _generate_error_response(
    state: StockAgentState, error_message: str
) -> StockAgentState:
    """오류 응답을 생성합니다."""

    try:
        logger.error(f"퀴즈 오류 응답 생성: {error_message}")

        state["data"] = {
            "source": "quiz",
            "results": [
                {
                    "type": "error",
                    "error_text": error_message,
                    "suggestion": "다시 '주식퀴즈도전'으로 시도해보세요.",
                }
            ],
            "total_count": 1,
            "summary": "퀴즈 오류 발생",
            "query_type": "quiz_error",
        }

        return state

    except Exception as e:
        logger.error(f"오류 응답 생성 중 추가 오류: {e}")

        # 최후의 수단 - 최소한의 오류 응답
        state["data"] = {
            "source": "quiz",
            "results": [
                {"type": "error", "error_text": "치명적인 오류가 발생했습니다."}
            ],
            "total_count": 1,
            "summary": "치명적 오류",
            "query_type": "quiz_fatal_error",
        }

        return state
