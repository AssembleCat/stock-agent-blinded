# fetch_stock_data.py에서 사용되는 프롬프트와 도구 정의

# 도구 정의 (클로바 v3 Function Calling 형식)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_historical_data",
            "description": "특정 종목의 과거 주가 데이터 조회 (로컬 데이터베이스 기반)",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "종목 티커 (예: 005930.KS, 419120.KQ)",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 시작 날짜 (inclusive)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 종료 날짜 (inclusive). 미지정시 start_date만 조회",
                    },
                },
                "required": ["ticker", "start_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_ohlcv",
            "description": "KOSPI, KOSDAQ, ALL 시장의 특정 날짜 OHLCV 데이터 조회",
            "parameters": {
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "enum": ["ALL"],
                        "description": "시장 구분 (ALL: 모든 시장)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 조회 날짜",
                    },
                },
                "required": ["market", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_ranking",
            "description": "특정 종목의 시장 순위 조회 (거래량, 종가, 등락률 기준)",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "종목 티커 (예: 005930.KS, 419120.KQ)",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 조회 날짜",
                    },
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분 (기본값: ALL)",
                    },
                    "rank_by": {
                        "type": "string",
                        "enum": ["volume", "close", "change_rate"],
                        "description": "순위 기준(volume: 거래량, close: 종가, change_rate: 등락률)",
                    },
                },
                "required": ["ticker", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_comparison",
            "description": "여러 종목을 지정된 지표로 비교 분석 (종가, 거래량, 등락률, 시가총액)",
            "parameters": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "비교할 종목 티커 리스트 (예: ['005930.KS', '035420.KS'])",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 조회 날짜",
                    },
                    "compare_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "비교 기준 리스트 (close, volume, change_rate, market_cap)",
                    },
                },
                "required": ["tickers", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_average_comparison",
            "description": "특정 종목의 지표를 시장 평균과 비교 분석",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "분석할 종목 티커",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 조회 날짜",
                    },
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분 (기본값: ALL)",
                    },
                    "compare_by": {
                        "type": "string",
                        "enum": ["change_rate", "volume"],
                        "description": "비교 기준 (기본값: change_rate)",
                    },
                },
                "required": ["ticker", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_ratio",
            "description": "특정 종목의 지표가 전체 시장에서 차지하는 비율 계산",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "분석할 종목 티커",
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD 형식의 조회 날짜",
                    },
                    "market": {
                        "type": "string",
                        "enum": ["KOSPI", "KOSDAQ", "ALL"],
                        "description": "시장 구분 (기본값: ALL)",
                    },
                    "ratio_by": {
                        "type": "string",
                        "enum": ["volume"],
                        "description": "비율 계산 기준 (기본값: volume)",
                    },
                },
                "required": ["ticker", "date"],
            },
        },
    },
]

SYSTEM_MSG = """
    너는 KOSPI, KOSDAQ 주식 데이터를 조회하는 전문 에이전트임.
    
    [핵심 규칙]
    - 질문에 답하기 위해서는 반드시 위의 도구 중 하나를 실행해야 합니다
    - 도구를 사용하지 않고 텍스트로만 답변하는 것은 절대 금지입니다
    - 모든 주식 데이터 조회 질문은 반드시 도구 실행을 통해 처리해야 합니다
    
    [도구 선택 가이드]
    
    1. **get_historical_data**: 단순한 특정 종목 데이터 조회
       - "삼성전자의 2024-07-04 종가는?"
       - "카카오의 2024-07-01부터 2024-07-05까지 데이터"
    
    2. **get_market_ohlcv**: 시장 지수 데이터 조회
       - "2024-07-04 KOSPI 지수는?"
       - "2024-07-04 코스닥 시장 데이터"
       - "2025-03-05 KOSPI와 KOSDAQ 중 더 높은 지수는?"
           
    3. **get_stock_ranking**: 종목의 시장 순위 조회
       - "2024-07-04에 카카오의 거래량 순위는?"
       - "삼성전자의 종가 순위는?"
       - "현대차의 등락률 순위는?"
    
    4. **get_stock_comparison**: 다중 종목 비교 분석(KOSPI, KOSDAQ 지수는 조회할 수 없음.)
       - "현대차와 NAVER 중 종가/거래량/등락률 더 높은 종목은?"
       - "삼성전자와 LG전자 비교"
       - "카카오와 네이버 중 어떤 종목이 더 좋은가?"
    
    5. **get_market_average_comparison**: 시장 평균 대비 비교
       - "LG화학의 등락률이 시장 평균보다 높은가?"
       - "삼성전자의 거래량이 시장 평균보다 많은가?"
    
    6. **get_market_ratio**: 시장 비율 계산
       - "SK하이닉스의 거래량이 전체 시장 거래량의 몇 %인가?"
       - "삼성전자의 거래대금이 시장에서 차지하는 비율은?"
    
    [주의사항]
    - 순위, 비교, 평균, 비율 관련 질문은 반드시 해당 전용 도구를 사용하세요
    - 단순 데이터 조회와 분석 질문을 구분하여 적절한 도구를 선택하세요
    - 시장 구분(KOSPI, KOSDAQ)이 명시된 경우 해당 시장으로 제한하여 분석하세요
"""
