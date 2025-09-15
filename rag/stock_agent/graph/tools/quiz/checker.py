import re
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
from langchain_naver import ChatClovaX
from rag.stock_agent.graph.prompts import (
    get_quiz_answer_check_prompt,
    DEFAULT_CONFIDENCE,
)
from utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class QuizAnswerChecker:
    """퀴즈 답변 검증 클래스"""

    def __init__(self):
        self.llm = ChatClovaX(model="HCX-005", temperature=0)

    def check_answer(
        self, quiz_data: Dict[str, Any], user_answer: str
    ) -> Dict[str, Any]:
        """
        사용자 답변을 검증합니다 (LLM 우선, 룰 기반 폴백).

        Args:
            quiz_data: 퀴즈 데이터
            user_answer: 사용자 답변

        Returns:
            검증 결과 딕셔너리
        """
        llm_result = self._check_with_llm(quiz_data, user_answer)
        return llm_result

    def _check_with_llm(
        self, quiz_data: Dict[str, Any], user_answer: str
    ) -> Dict[str, Any]:
        """LLM을 사용하여 사용자 답변이 정답인지 검증합니다."""
        try:
            # 퀴즈 정보 추출
            question = quiz_data.get("question", "")
            options = quiz_data.get("options", {})
            correct_answer = quiz_data.get("correct_answer", {})
            correct_number = correct_answer.get("number", "")
            correct_company = correct_answer.get("company", "")

            # 프롬프트 모듈에서 가져온 함수 사용
            check_prompt = get_quiz_answer_check_prompt(
                question, options, correct_number, correct_company, user_answer
            )

            response = self.llm.invoke(check_prompt)
            result_text = response.content.strip()

            # LLM 응답 파싱
            is_correct = "정답" in result_text and "정답여부: 정답" in result_text

            # 신뢰도 추출 (프롬프트 모듈의 상수 사용)
            confidence = DEFAULT_CONFIDENCE  # 기본값

            confidence_match = re.search(r"신뢰도:\s*(\d+)", result_text)
            if confidence_match:
                confidence = int(confidence_match.group(1))

            # 이유 추출
            reason_match = re.search(r"이유:\s*(.+)", result_text)
            explanation = reason_match.group(1) if reason_match else "LLM 판단 결과"

            return {
                "success": True,
                "is_correct": is_correct,
                "confidence": confidence,
                "explanation": explanation,
                "method": "llm",
                "raw_response": result_text,
            }

        except Exception as e:
            logger.error(f"LLM 답변 검증 중 오류: {e}")
            return {
                "success": False,
                "is_correct": False,
                "confidence": 0,
                "explanation": "답변 검증 중 오류가 발생했습니다.",
                "method": "error",
                "error": str(e),
            }

    def get_hint(self, quiz_data: Dict[str, Any]) -> str:
        """
        퀴즈 힌트를 생성합니다.

        Args:
            quiz_data: 퀴즈 데이터

        Returns:
            힌트 텍스트
        """
        try:
            background = quiz_data.get("background", "")

            if not background:
                return "힌트를 제공할 수 있는 정보가 없습니다."

            # 배경지식을 의미단위로 자르기
            hint_text = self._extract_meaningful_hint(background, quiz_data)

            logger.info(f"퀴즈 {quiz_data.get('id', 'Unknown')}번 힌트 생성")
            return f"💡 {hint_text}"

        except Exception as e:
            logger.error(f"힌트 생성 중 오류: {e}")
            return "힌트를 생성할 수 없습니다."

    def _extract_meaningful_hint(
        self, background: str, quiz_data: Dict[str, Any] = None
    ) -> str:
        """LLM을 사용해서 기업명을 노출하지 않는 키워드 힌트를 생성합니다."""
        try:
            # 정답 기업명 추출
            correct_company = ""
            if quiz_data:
                correct_answer = quiz_data.get("correct_answer", {})
                correct_company = correct_answer.get("company", "")

            # LLM에게 힌트 생성 요청
            hint_prompt = f"""
다음 배경지식을 바탕으로 키워드 형태의 힌트를 생성해주세요.

배경지식: {background}
정답 기업명: {correct_company}

요구사항:
1. 정답 기업명을 절대 포함하지 마세요
2. 기업명의 일부분도 포함하지 마세요  
3. 3-5개의 핵심 키워드만 추출해주세요
4. 년도, 금액, 숫자, 업종, 특징 등을 포함해주세요
5. "키워드: " 형태로 답변해주세요

예시: "키워드: 2022년, 상장, 첫날, 59만원, 시총2위"
"""

            response = self.llm.invoke(hint_prompt)
            hint_text = response.content.strip()

            # 혹시 기업명이 포함되었는지 최종 검증
            if correct_company and correct_company in hint_text:
                # 기업명이 포함된 경우 대체 힌트 제공
                return "키워드: 관련 정보, 배경지식, 참고자료"

            return hint_text

        except Exception as e:
            logger.error(f"LLM 힌트 생성 중 오류: {e}")
            return "키워드: 관련, 정보, 배경"
