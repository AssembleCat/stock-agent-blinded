from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_core.prompts import ChatPromptTemplate

response_schemas = [
    ResponseSchema(
        name="start_date",
        description="질문에서 요구하는 시작 날짜를 YYYY-MM-DD 형식으로 정확히 명시 (예: '2024-01-01')",
        type="string",
    ),
    ResponseSchema(
        name="end_date",
        description="질문에서 요구하는 종료 날짜를 YYYY-MM-DD 형식으로 정확히 명시 (예: '2024-12-31'). 단일 날짜 조회인 경우 start_date와 동일하게 설정",
        type="string",
    ),
    ResponseSchema(
        name="market_scope",
        description="검색할 시장 범위 (예: 'KOSPI', 'KOSDAQ', 'ALL')",
        type="string",
    ),
    ResponseSchema(
        name="primary_criteria",
        description="가장 중요한 검색 기준을 구체적으로 명시 (예: '거래량 급증', '고점 대비 하락', '상승률')",
        type="string",
    ),
    ResponseSchema(
        name="secondary_criteria",
        description="보조 검색 기준들 (예: '최소 거래량 100만주', '시가총액 1000억 이상')",
        type="string",
    ),
    ResponseSchema(
        name="specific_question",
        description="원본 애매모호한 질문을 stock_agent가 처리할 수 있는 구체적이고 명확한 질문으로 변환",
        type="string",
    ),
]

output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

information_analysis_schemas = [
    ResponseSchema(
        name="has_stock_name",
        description="질문에 구체적인 종목명이 포함되어 있는지 여부 (true/false)",
        type="boolean",
    ),
    ResponseSchema(
        name="extracted_stock_name",
        description="질문에서 추출된 종목명 (없으면 null)",
        type="string",
    ),
    ResponseSchema(
        name="has_specific_date",
        description="질문에 구체적인 날짜(YYYY-MM-DD 형식)가 포함되어 있는지 여부 (true/false)",
        type="boolean",
    ),
    ResponseSchema(
        name="extracted_date",
        description="질문에서 추출된 구체적 날짜 (없으면 null)",
        type="string",
    ),
    ResponseSchema(
        name="has_relative_time",
        description="질문에 상대적 시간 표현(어제, 최근, 요즘 등)이 포함되어 있는지 여부 (true/false)",
        type="boolean",
    ),
    ResponseSchema(
        name="has_metrics",
        description="질문에 주식 지표(종가, 시가, 고가, 저가, 거래량, 등락률 등)가 포함되어 있는지 여부 (true/false)",
        type="boolean",
    ),
    ResponseSchema(
        name="has_conditions",
        description="질문에 조건이나 기준(상승, 하락, 많은, 적은, 이상, 이하 등)이 포함되어 있는지 여부 (true/false)",
        type="boolean",
    ),
    ResponseSchema(
        name="missing_information_type",
        description="답변을 위해 부족한 핵심 정보 유형 ('STOCK_NAME', 'SPECIFIC_DATE', 'TIME_PERIOD', 'NONE')",
        type="string",
    ),
    ResponseSchema(
        name="information_completeness",
        description="질문의 완성도 ('COMPLETE': 답변 가능, 'PARTIAL': 부분 정보 부족, 'AMBIGUOUS': 완전 애매모호)",
        type="string",
    ),
]

information_parser = StructuredOutputParser.from_response_schemas(
    information_analysis_schemas
)

# === 주식명 추출용 프롬프트 ===
STOCK_NAME_EXTRACTION_PROMPT = [
    (
        "system",
        """
        당신은 텍스트에서 한국 주식 종목명을 정확히 추출하는 전문가입니다.
        
        규칙:
        1. 한국 주식 시장의 정식 종목명만 추출 (삼성전자, LG화학, SK하이닉스 등)
        2. 종목명이 명확하지 않거나 없으면 "없음"으로 응답
        3. 회사명의 약어나 별명도 인식 (삼성 → 삼성전자)
        4. 우선주 표기도 포함 (삼성전자우)
        5. 설명 없이 종목명만 출력
        
        예시:
        - "삼성전자의 어제 주가는?" → "삼성전자"
        - "LG 주식 정보" → "LG전자"  
        - "요즘 분위기 좋은 주식" → "없음"
        """,
    ),
    (
        "user",
        "질문: {query}\n\n",
    ),
]


def get_clarification_prompt() -> ChatPromptTemplate:
    """질문 명확화를 위한 프롬프트 템플릿"""

    format_instructions = output_parser.get_format_instructions()

    prompt_template = """
    당신은 애매모호한 주식 관련 질문을 구체적이고 명확한 질문으로 변환하는 전문가입니다.
    
    **중요한 규칙:**
    1. 모든 날짜는 반드시 YYYY-MM-DD 형식으로 정확히 표현해야 합니다.
    2. 오늘 날짜는 {today_date}입니다.
    3. 상대적 기간 표현을 정확한 날짜 범위로 변환해야 합니다:
       - "최근 1주일" → {today_date}부터 7일 전까지
       - "최근 6개월" → {today_date}부터 6개월 전까지  
       - "이번 주" → 이번 주 월요일부터 {today_date}까지
       - "이번 달" → 이번 달 1일부터 {today_date}까지
       - "52주" → {today_date}부터 52주 전까지
    4. 단일 날짜 조회인 경우 start_date와 end_date를 동일하게 설정하세요.
    
    **수치 정확성 규칙 (매우 중요):**
    질문의 강도와 맥락에 따라 적절한 수치를 선택하세요:
    
    **상승률 관련:**
    - "상승률이 높은", "잘 나가는", "분위기 좋은" → 3~8% 범위에서 선택 (3%, 5%, 7% 등)
    - "상승률이 매우 높은", "급등한", "폭등한" → 10~30% 범위에서 선택 (10%, 15%, 20% 등)
    - "상승률 상위" → "상위 5개" 또는 "상위 10개"
    
    **하락률 관련:**
    - "하락률이 높은", "떨어진", "부진한" → -5~-15% 범위에서 선택 (-5%, -10%, -15% 등)
    - "하락률이 매우 높은", "폭락한", "급락한" → -20~-30% 범위에서 선택 (-20%, -25%, -30% 등)
    - "하락률 하위" → "하위 5개" 또는 "하위 10개"
    
    **거래량 관련:**
    - "거래량이 증가한", "거래량이 많은" → 30~80% 범위에서 선택 (30%, 50%, 70% 등)
    - "거래량이 급증한", "거래량이 폭발한" → 100~300% 범위에서 선택 (100%, 200%, 300% 등)
    - "거래량 상위" → "상위 5개" 또는 "상위 10개"
    
    **복합 조건 (분위기 좋은 등):**
    - "분위기 좋은", "투자하기 좋은" → "상승률 3~7% 이상, 거래량 전일 대비 30~70% 이상 증가"
    - "핫한", "인기 있는" → "상승률 5~10% 이상, 거래량 전일 대비 50~100% 이상 증가"
    
    **수치 선택 가이드라인:**
    - 질문의 강도가 약하면 낮은 수치 선택 (3%, 30% 등)
    - 질문의 강도가 강하면 높은 수치 선택 (10%, 200% 등)
    - "매우", "폭발적", "급등" 등의 표현이 있으면 높은 수치 선택
    - "조금", "약간", "살짝" 등의 표현이 있으면 낮은 수치 선택
    
    **다양성 유지 원칙:**
    - 같은 질문이라도 다양한 수치를 사용하여 자연스럽게 변환
    - 3%, 5%, 7% 등 다양한 상승률 수치 활용
    - 30%, 50%, 70% 등 다양한 거래량 증가율 활용
    - 질문의 맥락과 강도에 맞는 적절한 수치 선택
    
    주어진 질문을 분석하여 다음 정보를 추출해주세요:
    - 시작 날짜: YYYY-MM-DD 형식의 정확한 시작 날짜
    - 종료 날짜: YYYY-MM-DD 형식의 정확한 종료 날짜  
    - 시장 범위: 검색할 시장 (KOSPI, KOSDAQ, ALL)
    - 주요 기준: 가장 중요한 검색 조건 (구체적 수치 포함)
    - 구체적 질문: stock_agent가 처리할 수 있는 명확한 질문 형태 (구체적 수치 포함)
    
    현재 질문: {query}
    
    {format_instructions}
    """

    return ChatPromptTemplate.from_template(prompt_template)


def get_information_analysis_prompt() -> ChatPromptTemplate:
    """질문의 정보 완성도를 분석하는 프롬프트 템플릿"""

    format_instructions = information_parser.get_format_instructions()

    prompt_template = """
    당신은 주식 관련 질문을 분석하여 정보의 완성도와 부족한 요소를 파악하는 전문가입니다.
    
    **분석 기준:**
    1. **종목명 분석**: 구체적인 한국 주식 종목명이 명시되어 있는가?
    2. **날짜 분석**: 구체적인 날짜(YYYY-MM-DD)가 명시되어 있는가?
    3. **시간 표현**: 상대적 시간 표현(어제, 최근, 요즘 등)이 있는가?
    4. **지표 분석**: 주식 관련 지표(종가, 시가, 거래량, 등락률 등)가 언급되는가?
    5. **조건 분석**: 조건이나 기준(상승, 하락, 많은, 적은 등)이 포함되어 있는가?
    
    **정보 완성도 판단:**
    - **COMPLETE**: 모든 필요 정보가 있어 바로 답변 가능
    - **PARTIAL**: 일부 정보는 있으나 핵심 정보가 부족하여 재질의 필요
    - **AMBIGUOUS**: 대부분의 정보가 애매모호하여 자체 구체화 필요
    
    **부족한 정보 유형:**
    - **STOCK_NAME**: 종목명이 부족함
    - **SPECIFIC_DATE**: 구체적 날짜가 부족함  
    - **TIME_PERIOD**: 조건 검색을 위한 기간이 부족함
    - **NONE**: 부족한 정보 없음
    
    **판단 예시:**
    - "삼성전자의 2024-07-15 종가는?" → COMPLETE, NONE
    - "어제의 종가를 알려줘" → PARTIAL, STOCK_NAME
    - "삼성전자의 어제 가격은?" → PARTIAL, SPECIFIC_DATE
    - "거래량 많은 종목 알려줘" → PARTIAL, TIME_PERIOD
    - "요즘 분위기 좋은 주식있어?" → AMBIGUOUS, NONE
    
    현재 질문: {query}
    배경지식: {context}
    
    위 질문을 분석해주세요:
    
    {format_instructions}
    """
    return ChatPromptTemplate.from_template(prompt_template)


# === 재질의 생성을 위한 스키마와 프롬프트 ===

clarification_generation_schemas = [
    ResponseSchema(
        name="clarification_message",
        description="사용자에게 제공할 재질의 메시지 (원래 질문 맥락 + 부족한 정보 요청)",
        type="string",
    ),
    ResponseSchema(
        name="missing_info_description",
        description="부족한 정보에 대한 구체적 설명",
        type="string",
    ),
    ResponseSchema(
        name="contextual_examples",
        description="사용자 질문 맥락에 맞는 구체적 예시 (동적 생성)",
        type="string",
    ),
]

clarification_parser = StructuredOutputParser.from_response_schemas(
    clarification_generation_schemas
)


def get_clarification_generation_prompt() -> ChatPromptTemplate:
    """구조화된 재질의 생성을 위한 프롬프트 템플릿"""

    prompt_template = """
    당신은 사용자의 주식 관련 질문에서 부족한 정보를 정확히 파악하여 
    도움이 되는 재질의를 생성하는 전문가입니다.

    **재질의 생성 원칙 (필수 준수):**
    1. 사용자의 원래 질문 의도를 정확히 파악하고 유지
    2. 부족한 정보만 구체적으로 요청 (과도한 요구 금지)
    3. 친근하고 도움이 되는 톤으로 작성 
    4. 사용자가 쉽게 답할 수 있는 형태로 구성
    5. 2-3문장으로 간결하게 작성

    **재질의 구조 (반드시 준수):**
    - **1문장**: 원래 질문 맥락 인정 + 부족한 정보 설명
    - **2문장**: 구체적으로 필요한 정보 요청  
    - **3문장**: 맥락에 맞는 구체적 예시 제공

    **부족한 정보별 재질의 가이드:**
    
    **STOCK_NAME (종목명 부족):**
    - 사용자가 언급한 다른 정보(날짜, 지표 등)는 그대로 유지
    - "어떤 종목의 [언급된 정보]를 조회해드릴까요?" 형태
    - 대표적인 종목명들을 예시로 제공
    
    **SPECIFIC_DATE (구체적 날짜 부족):**
    - 사용자가 언급한 종목명은 그대로 유지
    - 상대적 날짜("어제", "오늘" 등)가 있으면 구체적 날짜로 변환하여 제시
    - "삼성전자의 2025-07-23(어제) 가격을 조회해드릴까요?" 형태로 확인
    - 상대적 표현이 없으면 YYYY-MM-DD 형식 예시와 최근 날짜들 제공
    
    **TIME_PERIOD (기간 부족):**
    - 사용자가 언급한 조건들은 그대로 유지
    - "어떤 기간으로 조회해드릴까요?" 형태
    - 기간 형식 예시와 일반적인 기간들 제공

    **금지 사항:**
    - 템플릿화된 딱딱한 표현 금지
    - 사용자 질문 맥락과 무관한 일반적 예시 금지
    - 과도하게 긴 설명이나 부가 정보 금지
    - "요청하신", "말씀하신" 등의 과도한 존댓말 금지

    **상대적 날짜 변환 규칙 (필수 적용):**
    - 오늘 날짜: {today_date}
    - 어제 날짜: 오늘 날짜에서 1일을 뺀 날짜로 계산
    - "어제" 표현이 있으면 → 어제 날짜(YYYY-MM-DD)를 계산하여 변환
    - "오늘" 표현이 있으면 → {today_date}(오늘)로 변환
    
    **변환 예시 (정확히 이 형태로):**
    
    질문에 "어제"가 있고 종목명이 있는 경우:
    - 재질의: "[종목명]의 [어제날짜](어제) [지표]를 조회해드릴까요?"
    
    질문에 "어제"가 있고 종목명이 없는 경우:
    - 재질의: "[어제날짜](어제)의 어떤 종목 [지표]를 알려드릴까요?"
    
    질문에 "오늘"이 있는 경우:
    - 재질의: "[종목명]의 {today_date}(오늘) [지표]를 확인해드릴까요?"

    **분석할 정보:**
    - 원래 질문: {original_query}
    - 부족한 정보 유형: {missing_type}
    - 추출된 정보: {extracted_info}
    - 오늘 날짜: {today_date}
    
    위 정보를 바탕으로 사용자에게 도움이 되는 재질의를 생성해주세요:
    
    {format_instructions}
    """

    return ChatPromptTemplate.from_template(prompt_template)
