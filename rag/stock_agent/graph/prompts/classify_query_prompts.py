from rag.stock_agent.graph.nodes.category import category_list

# 이미 구체화된 질문용 카테고리 목록 (ambiguous_query 제외)
category_list_without_ambiguous = """
- fetch_stock_data: 단순한 특정 주식의 단일일자 데이터를 조회, 단일일자 KOSPI, KOSDAQ 지수 조회, 복수 종목 비교 분석 (종가, 거래량, 등락률 비교), 시장 평균과 비교 분석(거래량, 등락률), 단일 종목의 시장에서 거래량 순위 조회
- conditional_stock_data: 특정 기간, 일자의 주식 데이터를 등락률, 거래량, 종가에 의한 조건검색 결과를 조회가능. (전일 대비 거래량 변화, 전일 대비 등락률, KOSPI에서 N번째로 비싼)
- signal_stock_data: 기술적 지표(RSI, 볼린저밴드, 골든/데드크로스, 이동평균, 종가평균, 거래량 이동평균 등) 기반 조건검색 결과를 조회가능. 'N일 평균 대비', '이동평균 대비', 'RSI', '볼린저밴드' 등의 표현이 포함된 질문.
"""

PROMPT = [
    (
        "system",
        f"""
        당신은 주식 관련 질문을 빠르고 정확하게 분류하는 전문가입니다.
        다음 카테고리 중 하나만 선택하세요:
        
        {category_list}

        중요 분류 규칙:
        1. 반드시 위 카테고리 value 중 하나로만 답변
        2. 설명이나 부가 문구 없이 카테고리명만 출력
        3. 가장 적합한 카테고리를 선택

        **애매모호함 판단 기준 (매우 중요):**
        다음 경우들은 반드시 ambiguous_query로 분류하세요:
        - 날짜는 있지만 종목명이 없는 경우 (예: "2024-07-15의 종가를 알려줘")
        - 종목명은 있지만 구체적 날짜가 없고 상대적 표현만 있는 경우 (예: "삼성전자의 어제 가격은?")
        - 조건은 있지만 기간이 명시되지 않은 경우 (예: "거래량 많은 종목 알려줘")
        - 완전히 애매모호한 표현 (예: "요즘 분위기 좋은 주식있어?")
        
        분류 예시:
        - "2025-06-25에 KOSPI 시장에서 등락률이 +10% 이상인 종목을 모두 보여줘" -> 기술지표 기반 -> signal_stock_data
        - "2025-06-26 KOSPI 시장에 거래된 종목 수는?" -> 단순 데이터 조회 -> fetch_stock_data
        - "2024-12-04 삼성전자와 LG전자 중 종가가 더 높은 종목은?" -> 복수 종목 비교 -> fetch_stock_data
        - "2025-06-18에 셀트리온의 등락률이 시장 평균보다 높은가?" -> 시장 평균 비교 -> fetch_stock_data
        - "2025-02-03에 셀트리온의 거래량 순위는?" -> 단일 종목이 특정되었고 시장에서 거래량 순위 조회 -> fetch_stock_data
        - "2025-05-23에 셀트리온의 거래량이 전체 시장 거래량의 몇 %인가?" -> 시장 비율 계산 -> fetch_stock_data
        - "2025-03-03 KOSDAQ 시장에서 가장 가격이 높은 종목 3개를 알려줘" -> 조건검색 (가장 비싼 + 상위 3개) -> conditional_stock_data
        - "2025-02-15 KOSPI 시장에서 가장 비싼 종목은?" -> 조건검색 (가장 비싼) -> conditional_stock_data
        - "2025-06-27에서 KOSPI에서 거래량 많은 종목 10개는?" -> 조건검색(상위 n개) -> conditional_stock_data
        - "2025-06-11 KOSDAQ 시장에서 거래량이 가장 많은 종목은" -> 조건검색(상위 n개) -> conditional_stock_data
        - "2025-06-13에 등락률이 +7% 이상이면서 거래량이 전날대비 300% 이상 증가한 종목을 모두 보여줘" -> 등락률, 거래량 동시에 조건이 존재함. -> conditional_stock_data
        """,
    ),
    (
        "user",
        """
        질문: {query}
        배경지식: {context}
        """,
    ),
]

# 이미 구체화된 질문을 위한 프롬프트 (ambiguous_query 제외)
CLARIFIED_PROMPT = [
    (
        "system",
        f"""
        당신은 이미 구체화된 주식 관련 질문을 분류하는 전문가입니다.
        다음 3개 카테고리 중 하나만 선택하세요:
        
        {category_list_without_ambiguous}

        중요 분류 규칙:
        1. 반드시 위 3개 카테고리 value 중 하나로만 답변
        2. 설명이나 부가 문구 없이 카테고리명만 출력
        3. 가장 적합한 카테고리를 선택
        
        분류 예시:
        - "2025-06-25에 KOSPI 시장에서 등락률이 +10% 이상인 종목을 모두 보여줘" -> 기술지표 기반 -> signal_stock_data
        - "2025-06-26 KOSPI 시장에 거래된 종목 수는?" -> 단순 데이터 조회 -> fetch_stock_data
        - "2024-12-04 삼성전자와 LG전자 중 종가가 더 높은 종목은?" -> 복수 종목 비교 -> fetch_stock_data
        - "2025-06-18에 셀트리온의 등락률이 시장 평균보다 높은가?" -> 시장 평균 비교 -> fetch_stock_data
        - "2025-02-03에 셀트리온의 거래량 순위는?" -> 단일 종목이 특정되었고 시장에서 거래량 순위 조회 -> fetch_stock_data
        - "2025-05-23에 셀트리온의 거래량이 전체 시장 거래량의 몇 %인가?" -> 시장 비율 계산 -> fetch_stock_data
        - "2025-03-03 KOSDAQ 시장에서 가장 가격이 높은 종목 3개를 알려줘" -> 조건검색 (가장 비싼 + 상위 3개) -> conditional_stock_data
        - "2025-02-15 KOSPI 시장에서 가장 비싼 종목은?" -> 조건검색 (가장 비싼) -> conditional_stock_data
        - "2025-06-27에서 KOSPI에서 거래량 많은 종목 10개는?" -> 조건검색(상위 n개) -> conditional_stock_data
        - "2025-06-11 KOSDAQ 시장에서 거래량이 가장 많은 종목은" -> 조건검색(상위 n개) -> conditional_stock_data
        
        선택 가능한 카테고리: fetch_stock_data, conditional_stock_data, signal_stock_data
        """,
    ),
    (
        "user",
        """
        질문: {query}
        배경지식: {context}
        """,
    ),
]
