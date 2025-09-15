import os
from langchain_naver import ChatClovaX
from typing import Dict, Any
from utils.logger import get_logger
import datetime
import re
from rag.stock_agent.graph.state import StockAgentState
from rag.stock_agent.graph.prompts import (
    get_clarification_prompt,
    output_parser,
    get_information_analysis_prompt,
    information_parser,
    STOCK_NAME_EXTRACTION_PROMPT,
    get_clarification_generation_prompt,
    clarification_parser,
)
from langchain_core.prompts import ChatPromptTemplate

logger = get_logger(__name__)

llm = ChatClovaX(model="HCX-005", temperature=0)


def get_today_date() -> str:
    """오늘 날짜를 YYYY-MM-DD 형식으로 반환"""
    return datetime.datetime.now().strftime("%Y-%m-%d")


def extract_date_from_query(query: str) -> str:
    """쿼리에서 날짜를 추출합니다."""
    # YYYY-MM-DD 패턴
    date_pattern = r"\d{4}-\d{2}-\d{2}"
    match = re.search(date_pattern, query)
    if match:
        return match.group()

    # YYYYMMDD 패턴
    date_pattern = r"\d{8}"
    match = re.search(date_pattern, query)
    if match:
        date_str = match.group()
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    return None


def extract_stock_name_with_llm(query: str) -> str:
    """LLM을 사용하여 쿼리에서 주식명을 추출합니다."""
    prompt = ChatPromptTemplate.from_messages(STOCK_NAME_EXTRACTION_PROMPT)

    try:
        response = llm.invoke(prompt.invoke({"query": query}))
        stock_name = response.content.strip()

        # "없음" 또는 빈 문자열 처리
        if stock_name in ["없음", "", "None", "null"]:
            return None

        return stock_name
    except Exception as e:
        logger.error(f"LLM 주식명 추출 실패: {e}")
        return None


def analyze_information_with_llm(query: str, context: dict) -> Dict[str, Any]:
    """LLM을 사용하여 질문의 정보 완성도를 분석합니다."""
    prompt = get_information_analysis_prompt()

    try:
        response = llm.invoke(
            prompt.format(
                query=query,
                context=str(context),
                format_instructions=information_parser.get_format_instructions(),
            )
        )

        # 구조화된 출력 파싱
        parsed_result = information_parser.parse(response.content)

        logger.info(f"--LLM 정보 분석 결과: {parsed_result}--")

        return parsed_result

    except Exception as e:
        logger.error(f"LLM 정보 분석 실패: {e}")
        # 폴백: 기본 분석
        return {
            "has_stock_name": bool(extract_stock_name_with_llm(query)),
            "has_specific_date": bool(extract_date_from_query(query)),
            "has_relative_time": False,
            "has_metrics": False,
            "has_conditions": False,
            "missing_information_type": "NONE",
            "information_completeness": "AMBIGUOUS",
        }


def analyze_ambiguity_type(query: str, context: dict) -> str:
    """
    LLM 기반으로 애매모호함 유형을 분석
    Returns: "SELF_CLARIFY" | "ASK_USER"
    """
    # LLM 기반 정보 분석
    analysis = analyze_information_with_llm(query, context)

    completeness = analysis.get("information_completeness", "AMBIGUOUS")
    missing_type = analysis.get("missing_information_type", "NONE")

    logger.info(f"--정보 완성도: {completeness}, 부족한 정보: {missing_type}--")

    # 1. 완전한 정보가 있는 경우는 애매모호함 처리 대상이 아님 (에러 케이스)
    if completeness == "COMPLETE":
        logger.warning("--완전한 질문이 애매모호함 분석에 도달함--")
        return "SELF_CLARIFY"

    # 2. 부분적 정보 부족 → 재질의 vs 자체 구체화 판단
    elif completeness == "PARTIAL":
        # 상대적 날짜가 있으면 구체화 가능 → 자체 구체화
        has_relative_time = analysis.get("has_relative_time", False)

        if missing_type == "SPECIFIC_DATE" and has_relative_time:
            logger.info(f"--상대적 날짜({has_relative_time}) 있음 -> 자체 구체화--")
            return "SELF_CLARIFY"
        elif missing_type in ["STOCK_NAME", "SPECIFIC_DATE", "TIME_PERIOD"]:
            logger.info(f"--부분 정보 부족 ({missing_type}) -> 재질의--")
            return "ASK_USER"
        else:
            logger.info("--부분 정보 부족이지만 재질의 불가 -> 자체 구체화--")
            return "SELF_CLARIFY"

    # 3. 완전 애매모호 → 자체 구체화
    else:  # AMBIGUOUS
        logger.info("--완전 애매모호 -> 자체 구체화--")
        return "SELF_CLARIFY"


def generate_clarification_question(query: str, context: dict) -> str:
    """LLM 기반으로 구조화된 재질의 생성 (하드코딩 제거)"""
    analysis = analyze_information_with_llm(query, context)
    missing_type = analysis.get("missing_information_type", "NONE")

    logger.info(f"--LLM 기반 재질의 생성 시작: missing_type={missing_type}--")

    # 오늘 날짜 정보
    today_date = get_today_date()

    # LLM 기반 재질의 생성 프롬프트
    prompt = get_clarification_generation_prompt()

    try:
        # 구조화된 LLM 호출
        response = llm.invoke(
            prompt.format(
                original_query=query,
                missing_type=missing_type,
                extracted_info=str(analysis),
                today_date=today_date,
                format_instructions=clarification_parser.get_format_instructions(),
            )
        )

        # 구조화된 출력 파싱
        parsed_result = clarification_parser.parse(response.content)
        clarification_message = parsed_result.get("clarification_message", "")

        logger.info(f"--LLM 생성 재질의: {clarification_message}--")

        return clarification_message

    except Exception as e:
        logger.error(f"LLM 기반 재질의 생성 실패: {e}")
        # 폴백: 간단한 기본 메시지
        return f"질문을 처리하기 위해 추가 정보가 필요합니다. {missing_type} 정보를 제공해주시겠어요?"


def clarify_vague_question(query: str) -> Dict[str, Any]:
    """
    애매모호한 질문을 구체적인 질문으로 변환 (기존 로직)
    """
    prompt = get_clarification_prompt()
    today_date = get_today_date()

    # LLM 호출
    response = llm.invoke(
        prompt.format(
            query=query,
            today_date=today_date,
            format_instructions=output_parser.get_format_instructions(),
        )
    )

    # 구조화된 출력 파싱
    parsed_result = output_parser.parse(response.content)

    logger.info(f"질문 명확화 결과: {parsed_result}")

    return parsed_result


def clarify_question_node(state: StockAgentState) -> StockAgentState:
    """
    질문 명확화 노드 - LLM 기반 개선된 버전
    """
    query = state.get("query", "")
    context = state.get("context", {})

    if not query:
        logger.error("질문이 없습니다.")
        return state

    # LLM 기반 애매모호함 유형 분석
    ambiguity_type = analyze_ambiguity_type(query, context)

    if ambiguity_type == "ASK_USER":
        # 재질의 응답 생성
        clarification_question = generate_clarification_question(query, context)
        state["response"] = clarification_question
        state["query_category"] = "ask_clarification"
        logger.info(f"--재질의 응답 생성: {clarification_question}--")
        return state

    else:  # SELF_CLARIFY
        # 기존 로직: 자체 구체화
        logger.info("--자체 구체화 로직 실행--")
        clarified = clarify_vague_question(query)

        # 원본 질문과 구체화 정보를 state에 저장
        original_query = query
        specific_question = clarified.get("specific_question", query)

        # 구체화 정보를 state에 저장
        state["clarification_info"] = {
            "original_query": original_query,
            "clarified_query": specific_question,
            "start_date": clarified.get("start_date", ""),
            "end_date": clarified.get("end_date", ""),
            "market_scope": clarified.get("market_scope", ""),
            "primary_criteria": clarified.get("primary_criteria", ""),
            "secondary_criteria": clarified.get("secondary_criteria", ""),
        }

        # 변환된 질문을 state의 query에 저장
        state["query"] = specific_question

        logger.info(f"원본 질문: {original_query}")
        logger.info(f"구체화된 질문: {specific_question}")
        logger.info(f"구체화 정보: {state['clarification_info']}")

        return state


def ambiguous_query_with_path(state: StockAgentState) -> str:
    """
    AMBIGUOUS_QUERY 노드에서 다음 경로를 결정
    """
    from rag.stock_agent.graph.constant import ASK_CLARIFICATION, CLASSIFY_QUERY

    query_category = state.get("query_category", "")
    if query_category == "ask_clarification":
        return ASK_CLARIFICATION
    else:
        return CLASSIFY_QUERY
