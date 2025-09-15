# quiz_prompts.py - 퀴즈 관련 프롬프트 정의

from typing import Dict, Any


def get_company_insight_prompt(
    company_name: str, combined_data: Dict[str, Any], quiz_background: str = ""
) -> str:
    """
    기업 통찰 스낵글 생성을 위한 구조화된 프롬프트

    Args:
        company_name: 기업명
        combined_data: 정적 + 동적 데이터 결합
        quiz_background: 퀴즈 배경지식

    Returns:
        LLM에게 전달할 프롬프트 문자열
    """

    prompt = f"""
당신은 투자 전문 분석가입니다. 주어진 실제 데이터를 바탕으로 정확히 다음 템플릿 구조를 지켜서 투자자 관점의 기업 스낵글을 작성해주세요.

**템플릿 구조:**
[회사명]는 [업종] 분야의 [시장포지션]으로, [사업모델]을 통해 수익을 창출합니다. 최근 [분석기간]일간 [주가변동]하며 [현재상황] 상황입니다.

**제공된 실제 데이터:**
- 회사명: {company_name}
- 업종: {combined_data.get('sector', '정보없음')}
- 시가총액 순위: {combined_data.get('market_cap_rank', '정보없음')}위
- 시장 포지션: {combined_data.get('market_position', '정보없음')}
- 사업 모델: {combined_data.get('business_model', '정보없음')}
- 주가 분석 기간: {combined_data.get('actual_days', 30)}일 (영업일 기준 약 30거래일)
- 해당 기간 주가 변동: {combined_data.get('price_trend', 0):.1f}%
- 현재 상황: {combined_data.get('current_status', '정보없음')}

**작성 규칙:**
1. 반드시 위 템플릿 구조를 따라 작성하세요
2. 제공된 실제 데이터만을 사용하세요
3. 주가 분석 기간은 영업일 기준이므로 실제 달력상 기간임을 고려하세요
4. 주가 변동률과 업종 특성을 고려하여 자연스럽게 최근 상황을 설명하세요
5. 정중한 존댓말로 작성하세요  
6. 1문단 4-6문장으로 제한하세요
7. 투자자가 알아두면 좋은 핵심 정보를 포함하세요

퀴즈 배경지식 참고: {quiz_background if quiz_background else "없음"}

스낵글:
"""
    return prompt.strip()


def get_quiz_answer_check_prompt(
    question: str,
    options: Dict[str, str],
    correct_number: str,
    correct_company: str,
    user_answer: str,
) -> str:
    """
    퀴즈 답변 검증을 위한 프롬프트

    Args:
        question: 퀴즈 질문
        options: 선택지 딕셔너리
        correct_number: 정답 번호
        correct_company: 정답 기업명
        user_answer: 사용자 답변

    Returns:
        LLM에게 전달할 프롬프트 문자열
    """

    # 선택지 포맷팅
    formatted_options = _format_quiz_options(options)

    prompt = f"""
다음 주식 퀴즈의 사용자 답변이 정답인지 판단해주세요.

질문: {question}

선택지:
{formatted_options}

정답: {correct_number}번 - {correct_company}

사용자 답변: "{user_answer}"

판단 기준:
1. 정답 번호 ({correct_number}번)를 포함하면 정답
2. 정답 기업명 ({correct_company})을 포함하면 정답  
3. 기업명의 일부분이라도 포함하면 정답
4. 선택지 내용과 유사하면 정답
5. 숫자나 특수문자만 있어도 번호로 인식

다음 형식으로만 답변하세요:
정답여부: [정답/오답]
신뢰도: [0-100 숫자]
이유: [간단한 설명]

예시: 
정답여부: 정답
신뢰도: 95
이유: 사용자가 2번을 선택했고 정답이 2번입니다.
"""
    return prompt.strip()


def _format_quiz_options(options: Dict[str, str]) -> str:
    """선택지를 포맷팅합니다."""

    if not options:
        return "선택지 없음"

    formatted = []
    for key, value in options.items():
        if key.isdigit():
            formatted.append(f"{key}번: {value}")
        else:
            formatted.append(f"{key}: {value}")

    return "\n".join(formatted)


# 프롬프트 관련 상수
COMPANY_INSIGHT_TEMPLATE_FIELDS = [
    "회사명",
    "업종",
    "시장포지션",
    "사업모델",
    "분석기간",
    "주가변동",
    "현재상황",
]

QUIZ_CHECK_RESPONSE_FORMAT = {
    "정답여부": ["정답", "오답"],
    "신뢰도": "0-100 숫자",
    "이유": "간단한 설명",
}

# 프롬프트 검증 관련 상수
MIN_INSIGHT_LENGTH = 50  # 최소 스낵글 길이
MAX_INSIGHT_SENTENCES = 6  # 최대 문장 수
DEFAULT_CONFIDENCE = 50  # 기본 신뢰도
