from dotenv import load_dotenv
from langchain_naver import ChatClovaX
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.stock_agent.graph.state import StockAgentState
from utils.logger import get_logger
from rag.stock_agent.graph.nodes.category import QueryCategory
from rag.stock_agent.graph.prompts import PROMPT, CLARIFIED_PROMPT
import re

load_dotenv()

logger = get_logger(__name__)

llm = ChatClovaX(model="HCX-005", temperature=0)

prompt = ChatPromptTemplate.from_messages(PROMPT)
clarified_prompt = ChatPromptTemplate.from_messages(CLARIFIED_PROMPT)

classify_query_chain = prompt | llm | StrOutputParser()
clarified_classify_query_chain = clarified_prompt | llm | StrOutputParser()


def extract_category_from_response(response: str) -> str:
    """
    클로바 스튜디오의 응답에서 카테고리를 추출합니다.
    응답에 설명이 포함되어 있을 경우 카테고리만 정확히 추출합니다.
    """
    if not response:
        return ""

    # 응답을 정리 (앞뒤 공백 제거)
    response = response.strip()

    # 카테고리 목록을 정규식 패턴으로 생성
    category_pattern = "|".join(
        [re.escape(cat) for cat in QueryCategory._value2member_map_.keys()]
    )

    # 정확한 카테고리 매칭
    match = re.search(rf"\b({category_pattern})\b", response, re.IGNORECASE)
    if match:
        return match.group(1)

    # 카테고리가 포함된 줄 찾기
    lines = response.split("\n")
    for line in lines:
        line = line.strip()
        if any(
            cat.lower() in line.lower()
            for cat in QueryCategory._value2member_map_.keys()
        ):
            # 해당 줄에서 카테고리 추출
            match = re.search(rf"\b({category_pattern})\b", line, re.IGNORECASE)
            if match:
                return match.group(1)

    # 마지막 시도: 전체 응답에서 카테고리 찾기
    for category in QueryCategory._value2member_map_.keys():
        if category.lower() in response.lower():
            return category

    return ""


def classify_query(state: StockAgentState) -> StockAgentState:
    query = state["query"]

    # 활성 퀴즈 세션 보호 - 최우선 처리
    if state.get("quiz_session_active", False):
        logger.debug("활성 퀴즈 세션 - 퀴즈 노드로 라우팅")
        state["query_category"] = "quiz_stock_data"
        return state

    # 새로운 퀴즈 시작 감지
    if "퀴즈도전" in query:
        logger.info("퀴즈 시작 키워드 감지")
        state["query_category"] = "quiz_stock_data"
        return state

    # 이미 구체화된 질문인지 확인
    if state.get("clarification_info"):
        logger.info("--이미 구체화된 질문이므로 ambiguous_query 제외 프롬프트 사용--")
        # 이미 구체화된 질문은 ambiguous_query 제외 프롬프트 사용
        category = clarified_classify_query_chain.invoke(
            {
                "query": query,
                "context": state["context"],
            }
        )

        # LLM이 반환한 카테고리에서 실제 카테고리 추출
        category_name = extract_category_from_response(category)

        logger.info(f"--Query Category (extracted): {category_name}--")

        # 카테고리 유효성 검사 및 기본값 설정 (ambiguous_query 제외)
        valid_categories = {
            QueryCategory.FETCH_STOCK_DATA.value,
            QueryCategory.CONDITIONAL_STOCK_DATA.value,
            QueryCategory.SIGNAL_STOCK_DATA.value,
        }

        if category_name not in valid_categories:
            logger.warning(
                f"Unknown category: {category_name}, falling back to fetch_stock_data"
            )
            category_name = QueryCategory.FETCH_STOCK_DATA.value

        state["query_category"] = category_name
        return state

    # 기존 LLM 분류 로직 (퀴즈 비활성 상태에서만)
    category = classify_query_chain.invoke(
        {
            "query": query,
            "context": state["context"],
        }
    )

    # LLM이 반환한 카테고리에서 실제 카테고리 추출
    category_name = extract_category_from_response(category)

    logger.info(f"--Query Category (extracted): {category_name}--")

    # 카테고리 유효성 검사 및 기본값 설정
    valid_categories = {
        QueryCategory.FETCH_STOCK_DATA.value,
        QueryCategory.CONDITIONAL_STOCK_DATA.value,
        QueryCategory.SIGNAL_STOCK_DATA.value,
        QueryCategory.AMBIGUOUS_QUERY.value,
    }

    if category_name not in valid_categories:
        logger.warning(
            f"Unknown category: {category_name}, falling back to ambiguous_query"
        )
        category_name = QueryCategory.AMBIGUOUS_QUERY.value

    state["query_category"] = category_name
    return state


def classify_query_with_path(state: StockAgentState) -> str:
    return state["query_category"]
