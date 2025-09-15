import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from rag.stock_agent.graph.tools.quiz.reward_calculator import quiz_reward_calculator
from rag.stock_agent.graph.tools.quiz.user_reward_manager import user_reward_manager
from rag.stock_agent.graph.tools.quiz.company_insight_generator import (
    company_insight_generator,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class QuizInfoProvider:
    """퀴즈 완료 후 종합 정보 제공 클래스"""

    def __init__(self):
        self.reward_calculator = quiz_reward_calculator
        self.user_manager = user_reward_manager
        self.insight_generator = company_insight_generator

    def generate_answer_package(
        self,
        quiz_data: Dict[str, Any],
        user_answer: str,
        is_correct: bool,
        answer_check_result: Dict[str, Any],
        request_id: str = "",
    ) -> Dict[str, Any]:
        """
        퀴즈 답변 후 종합 정보 패키지를 생성합니다.

        Args:
            quiz_data: 퀴즈 데이터
            user_answer: 사용자 답변
            is_correct: 정답 여부
            answer_check_result: 답변 검증 결과
            request_id: 사용자 요청 고유 ID

        Returns:
            종합 정보 패키지
        """
        try:
            correct_answer = quiz_data.get("correct_answer", {})
            correct_company = correct_answer.get("company", "")

            # 기본 정보 구성
            package = {
                "quiz_id": quiz_data.get("id", 0),
                "question": quiz_data.get("question", ""),
                "user_answer": user_answer,
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "explanation": self._generate_explanation(
                    quiz_data, user_answer, is_correct, answer_check_result
                ),
                "reward_info": self._generate_reward_info(
                    correct_company, is_correct, request_id
                ),
                "company_insight": (
                    self._generate_company_insight(quiz_data) if is_correct else ""
                ),
                "timestamp": datetime.now().isoformat(),
            }

            # 보상 정보를 생성한 후에 사용자 보상 현황 조회 (현재 보상 포함)
            package["user_rewards_info"] = self._get_user_rewards_info(
                request_id, package["reward_info"]
            )

            logger.debug(f"퀴즈 {quiz_data.get('id', 'Unknown')} 정보 패키지 생성")
            return package

        except Exception as e:
            logger.error(f"정보 패키지 생성 중 오류: {e}")
            return self._get_error_package(quiz_data, user_answer, str(e))

    def _generate_explanation(
        self,
        quiz_data: Dict[str, Any],
        user_answer: str,
        is_correct: bool,
        answer_check_result: Dict[str, Any],
    ) -> str:
        """정답/오답 설명을 생성합니다."""

        try:
            correct_answer = quiz_data.get("correct_answer", {})
            correct_number = correct_answer.get("number", "")
            correct_company = correct_answer.get("company", "")
            options = quiz_data.get("options", {})

            if is_correct:
                # 정답인 경우 - 간단한 축하 메시지만
                return "🎉 정답입니다!"
            else:
                # 오답인 경우
                explanation_parts = []
                explanation_parts.append("❌ 아쉽게도 틀렸습니다.")

                # 정답 정보 제공
                correct_option = options.get(correct_number, "")
                explanation_parts.append(
                    f"정답은 {correct_number}번 '{correct_company}'입니다."
                )

                if correct_option:
                    explanation_parts.append(f"정답 선택지: {correct_option}")

                # 사용자 답변 분석
                if user_answer:
                    explanation_parts.append(
                        f"입력하신 답변 '{user_answer}'는 다른 선택지에 해당합니다."
                    )

                return " ".join(explanation_parts)

        except Exception as e:
            logger.error(f"설명 생성 중 오류: {e}")
            return f"답변 설명을 생성하는 중 오류가 발생했습니다: {str(e)}"

    def _generate_reward_info(
        self, company_name: str, is_correct: bool, request_id: str = ""
    ) -> Dict[str, Any]:
        """보상 정보를 생성합니다."""

        try:
            if not is_correct:
                return {
                    "eligible": False,
                    "message": "정답이 아니어서 주식 선물을 받을 수 없습니다. 다음 기회에 도전해보세요!",
                    "stock_name": "",
                    "amount": 0,
                    "value_estimate": "",
                }

            # 1시간 제한 체크
            can_receive_reward, next_reward_time = (
                self.user_manager.check_reward_eligibility(request_id)
            )

            if not can_receive_reward:
                return {
                    "eligible": False,
                    "reward_limited": True,
                    "next_reward_time": next_reward_time,
                    "message": "🎉 정답입니다!",
                    "limitation_message": self.user_manager.format_reward_limit_message(
                        next_reward_time
                    ),
                    "stock_name": company_name,
                    "amount": 0,
                }

            # 실제 직전 영업일 종가 기준 100원 가치 보상 계산
            reward_result = self.reward_calculator.calculate_reward_shares(
                company_name=company_name, target_value=100.0
            )

            if not reward_result.get("success", False):
                # 계산 실패 시 기본 보상
                logger.warning(f"보상 계산 실패: {reward_result.get('error', '')}")
                return {
                    "eligible": True,
                    "message": f"🎁 축하합니다! {company_name} 주식을 선물로 드렸습니다!",
                    "stock_name": company_name,
                    "amount": 0.001,  # 기본값
                    "closing_price": "가격 조회 실패",
                    "total_value": "100원",
                    "calculation_error": reward_result.get("error", ""),
                }

            # 성공적으로 계산된 경우
            shares = reward_result.get("shares", 0)
            closing_price = reward_result.get("closing_price", 0)
            total_value = reward_result.get("total_value", 0)
            date = reward_result.get("date", "")

            return {
                "eligible": True,
                "message": f"🎁 축하합니다! {date} 종가 기준 {total_value:,.0f}원 가치의 {company_name} 주식 {shares}주를 선물로 드렸습니다!",
                "stock_name": company_name,
                "amount": shares,
                "closing_price": f"{closing_price:,.0f}원",
                "total_value": f"{total_value:,.0f}원",
                "reference_date": date,
                "calculation_details": f"({date} 종가 기준)",
            }

        except Exception as e:
            logger.error(f"보상 정보 생성 중 오류: {e}")
            return {
                "eligible": False,
                "message": "보상 정보를 생성하는 중 오류가 발생했습니다.",
                "stock_name": company_name,
                "amount": 0,
                "error": str(e),
            }

    def _generate_company_insight(self, quiz_data: Dict[str, Any]) -> str:
        """기업에 대한 투자자 관점의 통찰 스낵글을 생성합니다."""

        try:
            correct_company = quiz_data.get("correct_answer", {}).get("company", "")
            quiz_background = quiz_data.get("background", "")

            if not correct_company:
                return ""

            insight = self.insight_generator.generate_company_insight(
                company_name=correct_company, quiz_background=quiz_background
            )

            logger.debug(f"{correct_company} 기업 통찰 생성 완료")
            return insight

        except Exception as e:
            logger.error(f"기업 통찰 생성 중 오류: {e}")
            return ""

    def _get_user_rewards_info(
        self, request_id: str = "", current_reward: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """사용자 전체 보상 현황을 조회합니다. 현재 받은 보상도 포함합니다."""

        try:
            # 기존 보상 현황 조회
            base_rewards_info = self.user_manager.get_user_total_rewards(request_id)

            # 현재 받은 보상이 있고 지급 가능한 경우 포함
            if (
                current_reward
                and current_reward.get("eligible", False)
                and not current_reward.get("reward_limited", False)
            ):
                stock_name = current_reward.get("stock_name", "")
                amount = current_reward.get("amount", 0)

                if stock_name and amount > 0:
                    # 기존 보상에 현재 보상 추가
                    if base_rewards_info.get("success", False):
                        total_rewards = base_rewards_info.get(
                            "total_rewards", {}
                        ).copy()
                        total_count = base_rewards_info.get("total_count", 0)

                        # 현재 받은 주식을 기존 보상에 추가
                        if stock_name in total_rewards:
                            total_rewards[stock_name] += amount
                        else:
                            total_rewards[stock_name] = amount

                        # 소수점 정리
                        total_rewards[stock_name] = round(total_rewards[stock_name], 7)

                        return {
                            "success": True,
                            "message": f"총 {total_count + 1}회 퀴즈 정답으로 {len(total_rewards)}종목의 주식을 받았습니다.",
                            "total_rewards": total_rewards,
                            "total_count": total_count + 1,
                            "includes_current": True,
                        }
                    else:
                        # 기존 이력이 없는 경우 현재 보상만
                        return {
                            "success": True,
                            "message": "첫 번째 퀴즈 정답으로 1종목의 주식을 받았습니다.",
                            "total_rewards": {stock_name: round(amount, 7)},
                            "total_count": 1,
                            "includes_current": True,
                        }

            # 현재 보상이 없거나 지급되지 않는 경우 기존 정보만 반환
            return base_rewards_info

        except Exception as e:
            logger.error(f"사용자 보상 현황 조회 중 오류: {e}")
            return {
                "success": False,
                "message": "보상 현황을 조회할 수 없습니다.",
                "total_rewards": {},
                "total_count": 0,
            }

    def _get_error_package(
        self, quiz_data: Dict[str, Any], user_answer: str, error_message: str
    ) -> Dict[str, Any]:
        """오류 발생 시 기본 패키지를 반환합니다."""

        return {
            "quiz_id": quiz_data.get("id", 0),
            "question": quiz_data.get("question", ""),
            "user_answer": user_answer,
            "is_correct": False,
            "correct_answer": quiz_data.get("correct_answer", {}),
            "explanation": "답변 처리 중 오류가 발생했습니다.",
            "reward_info": {
                "eligible": False,
                "message": "오류로 인해 보상을 제공할 수 없습니다.",
                "stock_name": "",
                "amount": 0,
            },
            "user_rewards_info": {
                "success": False,
                "message": "보상 현황을 조회할 수 없습니다.",
                "total_rewards": {},
                "total_count": 0,
            },
            "timestamp": datetime.now().isoformat(),
            "error": error_message,
        }

    def generate_quiz_start_message(self, quiz_data: Dict[str, Any]) -> str:
        """퀴즈 시작 메시지를 생성합니다."""

        try:
            question = quiz_data.get("question", "")
            options = quiz_data.get("options", {})
            quiz_id = quiz_data.get("id", "Unknown")

            message_parts = []

            # 헤더
            message_parts.append("🎯 주식 퀴즈 도전!")
            message_parts.append(f"문제 #{quiz_id}")
            message_parts.append("")

            # 문제
            message_parts.append(f"Q. {question}")
            message_parts.append("")

            # 선택지
            for num in sorted(options.keys()):
                option_text = options[num]
                symbol = {"1": "①", "2": "②", "3": "③", "4": "④"}.get(num, f"{num}.")
                message_parts.append(f"{symbol} {option_text}")

            message_parts.append("")
            message_parts.append(
                "💡 번호(1,2,3,4), 기업명, 또는 '힌트'를 입력해주세요!"
            )

            return "\n".join(message_parts)

        except Exception as e:
            logger.error(f"퀴즈 시작 메시지 생성 중 오류: {e}")
            return "퀴즈를 시작하는 중 오류가 발생했습니다."


# 전역 인스턴스
quiz_info_provider = QuizInfoProvider()
