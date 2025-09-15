from enum import Enum


class QueryCategory(Enum):
    FETCH_STOCK_DATA = "fetch_stock_data"
    CONDITIONAL_STOCK_DATA = "conditional_stock_data"
    SIGNAL_STOCK_DATA = "signal_stock_data"
    AMBIGUOUS_QUERY = "ambiguous_query"


CATEGORY_DESCRIPTIONS = {
    QueryCategory.FETCH_STOCK_DATA.value: "단순한 특정 주식의 단일일자 데이터를 조회, 단일일자 KOSPI, KOSDAQ 지수 조회, 복수 종목 비교 분석 (종가, 거래량, 등락률 비교), 시장 평균과 비교 분석(거래량, 등락률), 단일 종목의 시장에서 거래량 순위 조회",
    QueryCategory.CONDITIONAL_STOCK_DATA.value: "특정 기간, 일자의 주식 데이터를 등락률, 거래량, 종가에 의한 조건검색 결과를 조회가능. (전일 대비 거래량 변화, 전일 대비 등락률, KOSPI에서 N번째로 비싼)",
    QueryCategory.SIGNAL_STOCK_DATA.value: "기술적 지표(RSI, 볼린저밴드, 골든/데드크로스, 이동평균, 종가평균, 거래량 이동평균 등) 기반 조건검색 결과를 조회가능. 'N일 평균 대비', '이동평균 대비', 'RSI', '볼린저밴드' 등의 표현이 포함된 질문.",
    QueryCategory.AMBIGUOUS_QUERY.value: "질문이 일자, 수치, 기준이 명확히 제시하지않아 구체화할 필요성이 있음.",
}

category_list = "\n".join(
    f"- {cat.value}: {CATEGORY_DESCRIPTIONS[cat.value]}" for cat in QueryCategory
)
