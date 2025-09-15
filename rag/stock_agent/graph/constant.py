# Stock Agent 노드 상수
PREPROCESS = "preprocess"
CLASSIFY_QUERY = "classify_query"
AMBIGUOUS_QUERY = "ambiguous_query"
ASK_CLARIFICATION = "ask_clarification"
FETCH_STOCK_DATA = "fetch_stock_data"
CONDITIONAL_STOCK_DATA = "conditional_stock_data"
SIGNAL_STOCK_DATA = "signal_stock_data"
QUIZ_STOCK_DATA = "quiz_stock_data"
QUIZ_GENERATE_RESPONSE = "quiz_generate_response"
GENERATE_RESPONSE = "generate_response"
SQL_GENERATION = "sql_generation"

# 기본 결과 개수 설정
DEFAULT_RESULT_COUNT = 10  # 기본적으로 상위 10개 반환
MAX_RESULT_COUNT = 20  # 최대 반환 가능한 개수

# 시장별 설정
MARKET_SETTINGS = {
    "KOSPI": {"default_count": 10, "max_count": 20},
    "KOSDAQ": {"default_count": 10, "max_count": 20},
}

# 기술적 지표별 설정
TECHNICAL_INDICATOR_SETTINGS = {
    "RSI": {"default_count": 10, "max_count": 20},
    "BOLLINGER_BANDS": {"default_count": 10, "max_count": 20},
    "VOLUME_SURGE": {"default_count": 10, "max_count": 20},
    "MA_DEVIATION": {"default_count": 10, "max_count": 20},
    "CROSS_SIGNAL": {"default_count": 10, "max_count": 20},
}

# 데이터 포맷팅 설정
FORMATTING_SETTINGS = {
    "decimal_places": 2,  # 소수점 자릿수
    "use_thousand_separator": True,  # 천 단위 구분자 사용
    "currency_symbol": "원",  # 통화 기호
    "percentage_symbol": "%",  # 퍼센트 기호
}
