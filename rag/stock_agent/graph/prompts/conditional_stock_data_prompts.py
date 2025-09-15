# conditional_stock_data.py에서 사용되는 프롬프트와 도구 정의

# 도구 정의 (클로바 v3 Function Calling 형식)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stocks_by_price_range",
            "description": "가격을 기준으로 종목을 검색합니다. 가장비싼, Top N개의 종목, 특정 가격구간의 종목을 조회할 수 있습니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분, 질문에 KOSPI, KOSDAQ 시장구분이 없으면 ALL로 설정",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜 (기간 조회 시 사용)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜 (기간 조회 시 사용)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 날짜 (단일 날짜 조회 시 사용)",
                    },
                    "min_price": {"type": "number", "description": "최소 주가 (원)"},
                    "max_price": {"type": "number", "description": "최대 주가 (원)"},
                    "order_by": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "정렬 방향 (ASC: 오름차순, DESC: 내림차순)",
                    },
                },
                "required": ["market"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stocks_by_volume",
            "description": "특정 거래량 이상의 종목을 검색합니다. '거래량 상위', '거래량이 많은 종목', '거래량 기준 상위', '거래량 하위' 등의 질문에 사용됩니다. '거래량 상위' 요청 시 min_volume을 0으로 설정하여 모든 종목을 조회한 후 정렬하세요. ",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분, 질문에 KOSPI, KOSDAQ 시장구분이 없으면 ALL로 설정",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜 (기간 조회 시 사용)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜 (기간 조회 시 사용)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 날짜 (단일 날짜 조회 시 사용)",
                    },
                    "min_volume": {
                        "type": "integer",
                        "description": "최소 거래량 (주), 0으로 설정하면 모든 종목 조회",
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "정렬 방향 (ASC: 오름차순, DESC: 내림차순)",
                    },
                },
                "required": ["market"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stocks_by_change_rate",
            "description": "특정 등락률 범위의 종목을 검색합니다. '상승한 종목', '상승률 높은', '하락률 높은', '상승률 상위', '하락률 상위' 등의 질문에 사용됩니다. 기본적으로 등락률이 높은 순서(내림차순)로 정렬됩니다. '상승한 종목' 요청 시 min_change_rate를 0.01 이상으로 설정하여 0% 변화(변화 없음)를 제외하세요. '하락한 종목' 요청 시 max_change_rate를 -0.01 이하로 설정하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분, 질문에 KOSPI, KOSDAQ 시장구분이 없으면 ALL로 설정",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜 (기간 조회 시 사용)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜 (기간 조회 시 사용)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 날짜 (단일 날짜 조회 시 사용)",
                    },
                    "min_change_rate": {
                        "type": "number",
                        "description": "최소 등락률 (퍼센트 단위로 입력: 3% = 3.0, 상승 종목 조회 시 0.01 이상 설정)",
                    },
                    "max_change_rate": {
                        "type": "number",
                        "description": "최대 등락률 (퍼센트 단위로 입력: -2% = -2.0, 하락 종목 조회 시 -0.01 이하 설정)",
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "정렬 방향 (ASC: 오름차순, DESC: 내림차순)",
                    },
                },
                "required": ["market"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stocks_by_volume_change",
            "description": "전일 대비 거래량 증가 종목 검색. 검색 기준이 거래량 뿐일때 사용하세요. 기본적으로 거래량 증가율이 높은 순서(내림차순)로 정렬됩니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분, 질문에 KOSPI, KOSDAQ 시장구분이 없으면 ALL로 설정",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜 (기간 조회 시 사용)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜 (기간 조회 시 사용)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 날짜 (단일 날짜 조회 시 사용)",
                    },
                    "min_volume_ratio": {
                        "type": "number",
                        "description": "전일 대비 최소 거래량 비율 (배수로 입력: 1.3 = 30% 증가, 2.0 = 100% 증가, 3.0 = 200% 증가)",
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "정렬 방향 (ASC: 오름차순, DESC: 내림차순)",
                    },
                },
                "required": ["market", "min_volume_ratio"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stocks_by_combined_conditions",
            "description": "질문이 복합 조건(종가, 등락율, 거래량 등)을 조합한 종목 검색. 등락률 조건이 있으면 등락률 기준, 거래량 조건이 있으면 거래량 기준, 아니면 가격 기준으로 내림차순 정렬됩니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분, 질문에 KOSPI, KOSDAQ 시장구분이 없으면 ALL로 설정",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜 (기간 조회 시 사용)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜 (기간 조회 시 사용)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 날짜 (단일 날짜 조회 시 사용)",
                    },
                    "min_price": {"type": "number", "description": "최소 주가 (원)"},
                    "max_price": {"type": "number", "description": "최대 주가 (원)"},
                    "min_volume": {
                        "type": "integer",
                        "description": "최소 거래량 (주)",
                    },
                    "max_volume": {
                        "type": "integer",
                        "description": "최대 거래량 (주)",
                    },
                    "min_change_rate": {
                        "type": "number",
                        "description": "최소 등락률 (퍼센트 단위로 입력: 3% = 3.0)",
                    },
                    "max_change_rate": {
                        "type": "number",
                        "description": "최대 등락률 (퍼센트 단위로 입력: -2% = -2.0)",
                    },
                    "min_volume_ratio": {
                        "type": "number",
                        "description": "전일 대비 최소 거래량 비율 (배수로 입력: 1.3 = 30% 증가)",
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "정렬 방향 (ASC: 오름차순, DESC: 내림차순)",
                    },
                },
                "required": ["market"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_stocks_by_price",
            "description": "특정 시장에서 종가/거래량/등락률 기준 상위 N개 종목을 조회합니다. '가장 비싼 종목', '상위 N개 종목', '가장 거래량 많은 종목' 등의 질문에 사용됩니다. '하락률 높은 종목' 요청 시 order_by='change_rate', order_direction='ASC'로 설정하여 등락률이 낮은 순서로 정렬하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분 (KOSPI, KOSDAQ, ALL)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 조회 날짜",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "상위 몇 개 종목 (기본값: 1)",
                    },
                    "order_by": {
                        "type": "string",
                        "enum": ["close", "volume", "change_rate"],
                        "description": "정렬 기준 (close: 종가, volume: 거래량, change_rate: 등락률)",
                    },
                    "order_direction": {
                        "type": "string",
                        "enum": ["ASC", "DESC"],
                        "description": "정렬 방향 (ASC: 오름차순, DESC: 내림차순)",
                    },
                },
                "required": ["market", "date"],
            },
        },
    },
]

SYSTEM_MSG = """
    당신은 주식 데이터를 조회하는 도구를 사용해야 합니다. 사용자의 질문에 따라 적절한 도구를 호출하세요.
    
    **중요**: 반드시 제공된 도구 중 하나를 사용하여 응답해야 합니다. 텍스트로만 설명하지 마세요.
    
    [도구 선택 규칙]
    - '상승한 종목' 요청 시: min_change_rate를 0.01 이상으로 설정 (0% 변화 제외)
    - '하락한 종목' 요청 시: max_change_rate를 -0.01 이하로 설정 (0% 변화 제외)
    - '가장 비싼 종목' 요청 시: get_top_stocks_by_price 사용 (order_by="close", order_direction="DESC")
    - '가장 싼 종목' 요청 시: get_top_stocks_by_price 사용 (order_by="close", order_direction="ASC")
    - '거래량 상위' 요청 시: get_top_stocks_by_price 사용 (order_by="volume", order_direction="DESC")
    - '등락률 상위' 요청 시: get_top_stocks_by_price 사용 (order_by="change_rate", order_direction="DESC")
    - '하락률 높은 종목' 요청 시: get_top_stocks_by_price 사용 (order_by="change_rate", order_direction="ASC")
    
    [도구 선택 예시]
    - "YYYY-MM-DD에 KOSDAQ 시장에서 가장 비싼 종목은?" 같은 질문은  → get_top_stocks_by_price 사용
    - "YYYY-MM-DD에 KOSPI 시장에서 상위 3개 종목은?" 같은 질문은  → get_top_stocks_by_price 사용
    - "YYYY-MM-DD에 KOSDAQ 시장에서 가장 싼 종목은?" 같은 질문은  → get_top_stocks_by_price 사용 (order_direction="ASC")
    - "YYYY-MM-DD에 KOSPI 시장에서 가장 거래량이 많은 종목은?" 같은 질문은  → get_top_stocks_by_price 사용 (order_by="volume")
    - "YYYY-MM-DD에 KOSPI 시장에서 거래량 상위 5개 종목은?" 같은 질문은  → get_top_stocks_by_price 사용 (order_by="volume")
    - "YYYY-MM-DD에 KOSDAQ에서 하락률 높은 종목 5개는?" 같은 질문은  → get_top_stocks_by_price 사용 (order_by="change_rate", order_direction="ASC")
    - "YYYY-MM-DD에 등락률이 +5% 이상이면서 거래량이 전날대비 300% 이상 증가한 종목" → get_stocks_by_combined_conditions 사용
    
    [날짜 설정]
    - 단일 날짜 조회 시: 반드시 date 파라미터만 사용
    - 기간 조회 시: start_date와 end_date 사용
    - 예시: "2025-01-16에" → date="2025-01-16" 사용
    - 예시: "2025-01-16부터 2025-01-20까지" → start_date="2025-01-16", end_date="2025-01-20" 사용
    
    [시장 구분]
    - 질문에 "KOSPI", "코스피" 언급 시: market="KOSPI"
    - 질문에 "KOSDAQ", "코스닥" 언급 시: market="KOSDAQ"
    - 시장 구분이 명시되지 않은 경우: 반드시 market="ALL" 설정
    
    [입력 형식]
    - 2000만주 이상 일때는 20000000으로 실제 수치로 변환하여 입력
    - 등락률: 퍼센트 단위로 입력 (3% = 3.0, 5.5% = 5.5, -2% = -2.0)
    - 거래량 비율: 배수로 입력 (30% 증가 = 1.3, 100% 증가 = 2.0, 200% 증가 = 3.0)
    
    [정렬 방향]
    - '가장 싼', '가격 낮은', '거래량 적은', '하락률 높은' 등 명시적으로 낮은 값 요청 시에만 ASC 설정
    - '하락률 높은' = 등락률이 낮은 순서 = ASC (음수 등락률이 상위에 오도록)
"""
