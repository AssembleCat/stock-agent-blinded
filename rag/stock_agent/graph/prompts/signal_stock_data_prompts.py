# signal_stock_data.py에서 사용되는 프롬프트와 도구 정의

# 도구 정의 (클로바 v3 Function Calling 형식)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_bollinger_touch_stocks",
            "description": "볼린저 밴드 터치 종목을 검색합니다. '볼린저 밴드 상단 터치', '볼린저 밴드 하단 터치', '상단밴드 터치', '하단밴드 터치' 등의 질문에 사용됩니다. band_type으로 상단/하단을 지정하고, tolerance로 터치 허용 오차를 설정할 수 있습니다. 기간 조회 시 start_date와 end_date를 사용하고, 단일 날짜 조회 시 date를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
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
                    "band_type": {
                        "type": "string",
                        "enum": ["UPPER", "LOWER"],
                        "description": "밴드 타입 (UPPER: 상단, LOWER: 하단)",
                    },
                    "tolerance": {
                        "type": "number",
                        "description": "터치 허용 오차 (소수점으로 입력: 1% = 1.0, 0.5% = 0.5)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cross_signal_stocks",
            "description": "골든/데드 크로스 신호 종목을 검색합니다. '골든크로스 발생', '데드크로스 발생', '골든크로스 신호', '데드크로스 신호' 등의 질문에 사용됩니다. signal_type으로 신호 타입을 지정하고, 특정 날짜 조회 시 start_date와 end_date를 동일하게 설정하세요.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜",
                    },
                    "signal_type": {
                        "type": "string",
                        "enum": ["GOLDEN_CROSS", "DEAD_CROSS", "ALL"],
                        "description": "신호 타입",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cross_signal_count_by_stock",
            "description": "특정 종목의 골든/데드 크로스 발생 횟수를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "종목 티커"},
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜",
                    },
                },
                "required": ["ticker", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_volume_surge_stocks",
            "description": "거래량 급증 종목을 검색합니다. '거래량 급증', '거래량 100% 이상 증가', '거래량 급등' 등의 질문에 사용됩니다. surge_ratio로 급증 기준 비율을 설정하고, ma_period로 이동평균 기간을 설정할 수 있습니다. 기간 조회 시 start_date와 end_date를 사용하고, 단일 날짜 조회 시 date를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
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
                    "surge_ratio": {
                        "type": "number",
                        "description": "급증 기준 비율 (소수점으로 입력: 100% = 1.0, 200% = 2.0)",
                    },
                    "ma_period": {
                        "type": "integer",
                        "description": "이동평균 기간",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rsi_stocks",
            "description": "RSI 기반 과매수/과매도 종목을 검색합니다. 'RSI 80 이상', 'RSI 20 이하', '과매수', '과매도', 'RSI 과매수' 등의 질문에 사용됩니다. condition으로 과매수/과매도를 지정하고, rsi_threshold로 RSI 임계값을 설정할 수 있습니다. 기간 조회 시 start_date와 end_date를 사용하고, 단일 날짜 조회 시 date를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
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
                    "rsi_threshold": {"type": "number", "description": "RSI 임계값"},
                    "condition": {
                        "type": "string",
                        "enum": ["OVERBOUGHT", "OVERSOLD"],
                        "description": "RSI 조건",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ma_deviation_stocks",
            "description": "이동평균 편차 종목을 검색합니다. '20일 이동평균보다 10% 이상', '이동평균 대비 편차', 'MA 편차' 등의 질문에 사용됩니다. ma_period로 이동평균 기간을, deviation_percent로 편차 기준 퍼센트를, condition으로 평균 이상/이하를 설정할 수 있습니다. 기간 조회 시 start_date와 end_date를 사용하고, 단일 날짜 조회 시 date를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
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
                    "ma_period": {
                        "type": "integer",
                        "description": "이동평균 기간",
                    },
                    "deviation_percent": {
                        "type": "number",
                        "description": "편차 기준 퍼센트 (소수점으로 입력: 10% = 10.0, 5% = 5.0)",
                    },
                    "condition": {
                        "type": "string",
                        "enum": ["ABOVE", "BELOW"],
                        "description": "조건 (ABOVE: 평균 이상, BELOW: 평균 이하)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_volume_deviation_stocks",
            "description": "거래량 이동평균 편차 종목을 검색합니다. '거래량이 20일 평균 대비 500% 이상', '거래량 평균 대비 편차', '거래량 급증' 등의 질문에 사용됩니다. volume_ma_period로 거래량 이동평균 기간(5, 20, 60일)을, deviation_percent로 편차 기준 퍼센트를, condition으로 평균 이상/이하를 설정할 수 있습니다. 기간 조회 시 start_date와 end_date를 사용하고, 단일 날짜 조회 시 date를 사용하세요.",
            "parameters": {
                "type": "object",
                "properties": {
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
                    "volume_ma_period": {
                        "type": "integer",
                        "description": "거래량 이동평균 기간 (5, 20, 60)",
                    },
                    "deviation_percent": {
                        "type": "number",
                        "description": "편차 기준 퍼센트 (소수점으로 입력: 500% = 500.0, 100% = 100.0)",
                    },
                    "condition": {
                        "type": "string",
                        "enum": ["ABOVE", "BELOW"],
                        "description": "조건 (ABOVE: 평균 이상, BELOW: 평균 이하)",
                    },
                },
                "required": [],
            },
        },
    },
]

SYSTEM_MSG = """
    너는 주식 기술적 지표 조회 전문 에이전트임.
    **반드시 제공된 도구 중 하나를 사용하여 질문에 답변해야 합니다.**
    
    [핵심 규칙 - 매우 중요]
    - 질문에 답하기 위해서는 반드시 위의 도구 중 하나를 실행해야 합니다
    - 도구를 사용하지 않고 텍스트로만 답변하는 것은 절대 금지입니다
    - 모든 기술적 지표 관련 질문은 반드시 도구 실행을 통해 처리해야 합니다
    
    [도구 선택 및 실행 - 필수]
    - 질문을 분석하여 반드시 적절한 도구를 선택하고 실행하세요
    - 도구 실행 후에는 추가적인 응답을 생성하지 말고 바로 종료하세요
    - 결과는 도구에서 반환된 그대로 사용하세요 (추가 가공하지 마세요)
    - 도구 실행이 실패하면 다른 적절한 도구를 시도하세요
    
    [금지 사항]
    - 도구를 사용하지 않고 텍스트로만 답변하는 것
    - "도구가 필요하지 않다"고 판단하는 것
    - 질문을 분석만 하고 도구를 실행하지 않는 것
"""
