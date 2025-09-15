from langchain_core.prompts import ChatPromptTemplate
from langchain_naver import ChatClovaX
from rag.stock_agent.graph.state import StockAgentState
from utils.logger import get_logger
from rag.stock_agent.graph.prompts import (
    GENERATE_RESPONSE_SYSTEM_MSG as SYSTEM_MSG,
    CLARIFIED_QUERY_SYSTEM_MSG,
)

logger = get_logger(__name__)

llm = ChatClovaX(model="HCX-005", temperature=0)


def format_data_for_llm(data, data_type: str = "데이터") -> str:
    """
    데이터를 LLM이 이해하기 쉬운 형태로 포맷팅합니다.
    모든 카테고리(fetch, conditional, signal, sql)의 데이터 구조를 지원합니다.
    """
    if not data:
        return ""

    # 디버깅을 위한 로그 추가
    logger.info(f"--format_data_for_llm input data: {data}--")

    # 데이터 소스별 처리
    source = data.get("source", "")

    # === fetch_stock_data 카테고리 처리 ===
    if source == "fetch":
        results = data.get("results", [])
        if not results:
            return "조회된 데이터가 없습니다."

        formatted_results = []

        # results는 리스트이므로 첫 번째 항목을 가져옴
        if results and isinstance(results[0], dict):
            fetch_result = results[0]

            # get_historical_data 결과 처리
            if "get_historical_data" in fetch_result:
                tool_data = fetch_result["get_historical_data"]
                if isinstance(tool_data, dict) and "error" not in tool_data:
                    # 새로운 데이터 구조 처리
                    ticker = tool_data.get("ticker", "")
                    date = tool_data.get("date", "")

                    # results 배열에서 실제 데이터 가져오기
                    results_data = tool_data.get("results", [])
                    if (
                        results_data
                        and isinstance(results_data, list)
                        and len(results_data) > 0
                    ):
                        # 첫 번째 결과 데이터 사용
                        stock_data = results_data[0]

                        # 단일 날짜 조회 결과
                        if "시가" in stock_data:
                            open_price = stock_data.get("시가", "")
                            high = stock_data.get("고가", "")
                            low = stock_data.get("저가", "")
                            close = stock_data.get("종가", "")
                            volume = stock_data.get("거래량", "")
                            change_rate = stock_data.get("등락률", "")
                            value = stock_data.get("거래대금", "")
                            data_date = stock_data.get(
                                "날짜", date
                            )  # 날짜는 stock_data에서 가져오거나 tool_data에서 가져옴

                            # 숫자 포맷팅
                            if isinstance(open_price, (int, float)):
                                open_price = f"{open_price:,.0f}"
                            if isinstance(high, (int, float)):
                                high = f"{high:,.0f}"
                            if isinstance(low, (int, float)):
                                low = f"{low:,.0f}"
                            if isinstance(close, (int, float)):
                                close = f"{close:,.0f}"
                            if isinstance(volume, (int, float)):
                                volume = f"{volume:,}"
                            if isinstance(change_rate, (int, float)):
                                # 등락률을 퍼센트 형식으로 변환 (+ 또는 - 기호 포함)
                                if change_rate > 0:
                                    change_rate = f"+{change_rate:.2f}%"
                                elif change_rate < 0:
                                    change_rate = f"{change_rate:.2f}%"
                                else:
                                    change_rate = f"{change_rate:.2f}%"
                            if isinstance(value, (int, float)):
                                # 거래대금을 천 단위 구분자와 함께 표시
                                value = f"{value:,}원"

                            result_parts = []
                            if ticker:
                                result_parts.append(f"**{ticker}**")
                            if data_date:
                                result_parts.append(f"({data_date})")
                            if close:
                                result_parts.append(f"종가: {close}원")
                            if open_price:
                                result_parts.append(f"시가: {open_price}원")
                            if high:
                                result_parts.append(f"고가: {high}원")
                            if low:
                                result_parts.append(f"저가: {low}원")
                            if volume:
                                result_parts.append(f"거래량: {volume}주")
                            if change_rate:
                                result_parts.append(f"등락률: {change_rate}")
                            if value:
                                result_parts.append(f"거래대금: {value}")

                            formatted_results.append(" ".join(result_parts))

            # get_stock_comparison 결과 처리
            elif "get_stock_comparison" in fetch_result:
                tool_data = fetch_result["get_stock_comparison"]
                if isinstance(tool_data, dict) and "error" not in tool_data:
                    date = tool_data.get("date", "")
                    comparison_summary = tool_data.get("comparison_summary", {})
                    companies_count = tool_data.get("companies_count", 0)

                    result_parts = []
                    if date:
                        result_parts.append(f"**날짜: {date}**")

                    # 각 지표별 비교 결과 포맷팅
                    for metric, summary in comparison_summary.items():
                        metric_name = {
                            "close": "종가",
                            "volume": "거래량",
                            "change_rate": "등락률",
                            "value": "거래대금",
                            "market_cap": "시가총액",
                        }.get(metric, metric)

                        result_parts.append(f"\n**{metric_name} 비교:**")

                        # 모든 회사 정보 표시
                        all_companies = summary.get("all_companies", [])
                        for company in all_companies:
                            name = company.get("name", "")
                            value = company.get("value", 0)
                            ticker = company.get("ticker", "")

                            # 값 포맷팅
                            if metric == "close":
                                formatted_value = f"{value:,.0f}원"
                            elif metric == "volume":
                                formatted_value = f"{value:,}주"
                            elif metric == "change_rate":
                                if value > 0:
                                    formatted_value = f"+{value:.2f}%"
                                elif value < 0:
                                    formatted_value = f"{value:.2f}%"
                                else:
                                    formatted_value = f"{value:.2f}%"
                            elif metric == "value":
                                formatted_value = f"{value:,}원"
                            elif metric == "market_cap":
                                # 시가총액을 조 단위로 포맷팅
                                if value >= 1e12:  # 1조 이상
                                    formatted_value = f"{value/1e12:.1f}조원"
                                elif value >= 1e8:  # 1억 이상
                                    formatted_value = f"{value/1e8:.1f}억원"
                                else:
                                    formatted_value = f"{value:,.0f}원"
                            else:
                                formatted_value = str(value)

                            result_parts.append(
                                f"- {name} ({ticker}): {formatted_value}"
                            )

                        # 최고/최저 정보 추가
                        highest = summary.get("highest", {})
                        lowest = summary.get("lowest", {})

                        if highest and highest.get("name") != lowest.get("name"):
                            highest_name = highest.get("name", "")
                            highest_value = highest.get("value", 0)
                            if metric == "close":
                                highest_formatted = f"{highest_value:,.0f}원"
                            elif metric == "volume":
                                highest_formatted = f"{highest_value:,}주"
                            elif metric == "change_rate":
                                if highest_value > 0:
                                    highest_formatted = f"+{highest_value:.2f}%"
                                else:
                                    highest_formatted = f"{highest_value:.2f}%"
                            elif metric == "market_cap":
                                # 시가총액을 조 단위로 포맷팅
                                if highest_value >= 1e12:  # 1조 이상
                                    highest_formatted = f"{highest_value/1e12:.1f}조원"
                                elif highest_value >= 1e8:  # 1억 이상
                                    highest_formatted = f"{highest_value/1e8:.1f}억원"
                                else:
                                    highest_formatted = f"{highest_value:,.0f}원"
                            else:
                                highest_formatted = f"{highest_value:,}원"

                            result_parts.append(
                                f"  → **최고: {highest_name} ({highest_formatted})**"
                            )

                    formatted_results.append(" ".join(result_parts))

            # get_market_ohlcv 결과 처리
            elif "get_market_ohlcv" in fetch_result:
                tool_data = fetch_result["get_market_ohlcv"]
                if isinstance(tool_data, list) and tool_data:
                    # 모든 시장 데이터 처리
                    for market_data in tool_data:
                        market = market_data.get("market", "")
                        date = market_data.get("date", "")
                        open_price = market_data.get("open", "")
                        high = market_data.get("high", "")
                        low = market_data.get("low", "")
                        close = market_data.get("close", "")
                        volume = market_data.get("volume", "")

                        # 숫자 포맷팅
                        if isinstance(open_price, (int, float)):
                            open_price = f"{open_price:.2f}"
                        if isinstance(high, (int, float)):
                            high = f"{high:.2f}"
                        if isinstance(low, (int, float)):
                            low = f"{low:.2f}"
                        if isinstance(close, (int, float)):
                            close = f"{close:.2f}"
                        if isinstance(volume, (int, float)):
                            volume = f"{volume:,}"

                        result_parts = []
                        if market:
                            result_parts.append(f"**{market}**")
                        if date:
                            result_parts.append(f"({date})")
                        if close:
                            result_parts.append(f"종가: {close}")
                        if open_price:
                            result_parts.append(f"시가: {open_price}")
                        if high:
                            result_parts.append(f"고가: {high}")
                        if low:
                            result_parts.append(f"저가: {low}")
                        if volume:
                            result_parts.append(f"거래량: {volume}")

                        formatted_results.append(" ".join(result_parts))

            # get_stock_ranking 결과 처리
            elif "get_stock_ranking" in fetch_result:
                tool_data = fetch_result["get_stock_ranking"]
                if isinstance(tool_data, dict) and "error" not in tool_data:
                    stock_name = tool_data.get("stock_name", "")
                    date = tool_data.get("date", "")
                    rank = tool_data.get("rank", "")
                    total_stocks = tool_data.get("total_stocks", "")
                    value = tool_data.get("value", "")
                    rank_by = tool_data.get("rank_by", "")

                    # 순위 기준 한글화
                    rank_by_name = {
                        "volume": "거래량",
                        "close": "종가",
                        "change_rate": "등락률",
                    }.get(rank_by, rank_by)

                    # 거래량 포맷팅
                    if isinstance(value, (int, float)):
                        if rank_by == "volume":
                            formatted_value = f"{value:,}주"
                        elif rank_by == "close":
                            formatted_value = f"{value:,.0f}원"
                        elif rank_by == "change_rate":
                            if value > 0:
                                formatted_value = f"+{value:.2f}%"
                            else:
                                formatted_value = f"{value:.2f}%"
                        else:
                            formatted_value = str(value)
                    else:
                        formatted_value = str(value)

                    result_parts = []
                    if stock_name:
                        result_parts.append(f"**{stock_name}**")
                    if date:
                        result_parts.append(f"({date})")
                    if rank:
                        result_parts.append(f"{rank_by_name} 순위: {rank}위")
                    if formatted_value:
                        result_parts.append(f"{rank_by_name}: {formatted_value}")

                    formatted_results.append(" ".join(result_parts))

            # get_market_average_comparison 결과 처리
            elif "get_market_average_comparison" in fetch_result:
                tool_data = fetch_result["get_market_average_comparison"]
                if isinstance(tool_data, dict) and "error" not in tool_data:
                    stock_name = tool_data.get("stock_name", "")
                    date = tool_data.get("date", "")
                    compare_by = tool_data.get("compare_by", "")
                    stock_value = tool_data.get("stock_value", "")
                    market_average = tool_data.get("market_average", "")
                    difference = tool_data.get("difference", "")
                    is_higher_than_average = tool_data.get("is_higher_than_average", "")
                    total_stocks_in_market = tool_data.get("total_stocks_in_market", "")

                    # 비교 기준 한글화
                    compare_by_name = {"change_rate": "등락률", "volume": "거래량"}.get(
                        compare_by, compare_by
                    )

                    # 값 포맷팅
                    if isinstance(stock_value, (int, float)):
                        if compare_by == "change_rate":
                            if stock_value > 0:
                                stock_formatted = f"+{stock_value:.2f}%"
                            else:
                                stock_formatted = f"{stock_value:.2f}%"
                        elif compare_by == "volume":
                            stock_formatted = f"{stock_value:,}주"
                        else:
                            stock_formatted = str(stock_value)
                    else:
                        stock_formatted = str(stock_value)

                    if isinstance(market_average, (int, float)):
                        if compare_by == "change_rate":
                            if market_average > 0:
                                market_formatted = f"+{market_average:.2f}%"
                            else:
                                market_formatted = f"{market_average:.2f}%"
                        elif compare_by == "volume":
                            market_formatted = f"{market_average:,}주"
                        else:
                            market_formatted = str(market_average)
                    else:
                        market_formatted = str(market_average)

                    if isinstance(difference, (int, float)):
                        if compare_by == "change_rate":
                            if difference > 0:
                                diff_formatted = f"+{difference:.2f}%"
                            else:
                                diff_formatted = f"{difference:.2f}%"
                        else:
                            diff_formatted = f"{difference:,}"
                    else:
                        diff_formatted = str(difference)

                    result_parts = []
                    if stock_name:
                        result_parts.append(f"**{stock_name}**")
                    if date:
                        result_parts.append(f"({date})")
                    if stock_formatted:
                        result_parts.append(f"{compare_by_name}: {stock_formatted}")
                    if market_formatted:
                        result_parts.append(f"시장 평균: {market_formatted}")
                    if diff_formatted:
                        result_parts.append(f"차이: {diff_formatted}")
                    if is_higher_than_average is not None:
                        if is_higher_than_average:
                            result_parts.append("**시장 평균보다 높음**")
                        else:
                            result_parts.append("**시장 평균보다 낮음**")

                    formatted_results.append(" ".join(result_parts))

            # get_market_ratio 결과 처리
            elif "get_market_ratio" in fetch_result:
                tool_data = fetch_result["get_market_ratio"]
                if isinstance(tool_data, dict) and "error" not in tool_data:
                    stock_name = tool_data.get("stock_name", "")
                    date = tool_data.get("date", "")
                    ratio_by = tool_data.get("ratio_by", "")
                    stock_value = tool_data.get("stock_value", "")
                    market_total = tool_data.get("market_total", "")
                    ratio_percentage = tool_data.get("ratio_percentage", "")

                    # 비율 기준 한글화
                    ratio_by_name = {"volume": "거래량", "value": "거래대금"}.get(
                        ratio_by, ratio_by
                    )

                    # 값 포맷팅
                    if isinstance(stock_value, (int, float)):
                        if ratio_by == "volume":
                            stock_formatted = f"{stock_value:,}주"
                        elif ratio_by == "value":
                            stock_formatted = f"{stock_value:,}원"
                        else:
                            stock_formatted = str(stock_value)
                    else:
                        stock_formatted = str(stock_value)

                    if isinstance(market_total, (int, float)):
                        if ratio_by == "volume":
                            market_formatted = f"{market_total:,}주"
                        elif ratio_by == "value":
                            market_formatted = f"{market_total:,}원"
                        else:
                            market_formatted = str(market_total)
                    else:
                        market_formatted = str(market_total)

                    if isinstance(ratio_percentage, (int, float)):
                        ratio_formatted = f"{ratio_percentage:.2f}%"
                    else:
                        ratio_formatted = str(ratio_percentage)

                    result_parts = []
                    if stock_name:
                        result_parts.append(f"**{stock_name}**")
                    if date:
                        result_parts.append(f"({date})")
                    if stock_formatted:
                        result_parts.append(f"{ratio_by_name}: {stock_formatted}")
                    if market_formatted:
                        result_parts.append(f"시장 전체: {market_formatted}")
                    if ratio_formatted:
                        result_parts.append(f"**시장 비율: {ratio_formatted}**")

                    formatted_results.append(" ".join(result_parts))

        result = "\n".join(formatted_results)
        logger.info(f"--format_data_for_llm fetch result: {result}--")
        return result

    # === conditional_stock_data 카테고리 처리 ===
    elif source == "conditional":
        results = data.get("results", [])
        total_count = data.get("total_count", 0)

        if not results:
            return "조건에 해당하는 종목이 없습니다."

        formatted_results = []
        for i, row in enumerate(results[:10], 1):  # 최대 10개까지 표시
            if isinstance(row, dict):
                name = row.get("name", "")
                close = row.get("close", "")
                change_rate = row.get("change_rate", "")
                volume = row.get("volume", "")
                current_volume = row.get("current_volume", "")
                prev_volume = row.get("prev_volume", "")
                volume_change_percent = row.get("volume_change_percent", "")
                volume_ratio = row.get("volume_ratio", "")

                # 소수점 자릿수 제한
                if isinstance(change_rate, (int, float)):
                    change_rate = round(change_rate, 2)
                if isinstance(volume_change_percent, (int, float)):
                    volume_change_percent = round(volume_change_percent, 2)
                if isinstance(volume_ratio, (int, float)):
                    volume_ratio = round(volume_ratio, 2)

                # 숫자 포맷팅
                if isinstance(close, (int, float)):
                    close = f"{close:,.0f}"
                if isinstance(volume, (int, float)):
                    volume = f"{volume:,}"
                if isinstance(current_volume, (int, float)):
                    current_volume = f"{current_volume:,}"
                if isinstance(prev_volume, (int, float)):
                    prev_volume = f"{prev_volume:,}"

                # 결과 구성
                result_parts = [f"{i}. **{name}**"]

                # 기본 정보
                if close:
                    result_parts.append(f"{close}원")
                if change_rate is not None and change_rate != "":
                    if isinstance(change_rate, (int, float)) and change_rate < 0:
                        result_parts.append(f"({change_rate}%)")
                    else:
                        result_parts.append(f"(+{change_rate}%)")

                # 거래량 정보
                if volume:
                    result_parts.append(f"거래량: {volume}주")
                if current_volume and prev_volume:
                    result_parts.append(
                        f"거래량: {current_volume}주 (전일: {prev_volume}주)"
                    )
                if volume_change_percent:
                    result_parts.append(f"증가율: {volume_change_percent}%")
                if volume_ratio:
                    result_parts.append(f"비율: {volume_ratio}배")

                formatted_results.append(" ".join(result_parts))
            else:
                formatted_results.append(f"{i}. {row}")

        # 전체 개수 정보 추가
        if total_count > 0:
            return f"총 {total_count}개 종목\n" + "\n".join(formatted_results)
        return "\n".join(formatted_results)

    # === signal_stock_data 카테고리 처리 ===
    elif source == "signal":
        results = data.get("results", [])
        total_count = data.get("total_count", 0)

        if not results:
            return "신호 조건에 해당하는 종목이 없습니다."

        # get_cross_signal_count_by_stock 결과 처리 (단일 종목 크로스 신호 횟수)
        if len(results) == 1 and isinstance(results[0], dict):
            result = results[0]
            if "golden_cross_count" in result and "dead_cross_count" in result:
                name = result.get("name", "")
                golden_count = result.get("golden_cross_count", 0)
                dead_count = result.get("dead_cross_count", 0)
                total_count = result.get("total_cross_count", 0)
                start_date = result.get("start_date", "")
                end_date = result.get("end_date", "")
                message = result.get("message", "")

                if message:
                    return f"**{name}**: {message}"

                result_parts = [f"**{name}**"]
                if start_date and end_date:
                    result_parts.append(f"({start_date} ~ {end_date})")

                result_parts.append(f"골든크로스: {golden_count}회")
                result_parts.append(f"데드크로스: {dead_count}회")
                result_parts.append(f"총 크로스 신호: {total_count}회")

                return " ".join(result_parts)

        # 기존 다중 종목 결과 처리
        formatted_results = []
        for i, row in enumerate(results[:10], 1):  # 최대 10개까지 표시
            if isinstance(row, dict):
                # 종목명과 주요 수치만 추출
                name = row.get("name", "")
                close = row.get("close", "")
                change_rate = row.get("change_rate", "")
                volume = row.get("volume", "")
                current_volume = row.get("current_volume", "")
                prev_volume = row.get("prev_volume", "")
                volume_change_percent = row.get("volume_change_percent", "")
                volume_ratio = row.get("volume_ratio", "")

                # 기술적 지표 데이터 추가
                rsi = row.get("rsi", "")
                band_value = row.get("band_value", "")
                touch_type = row.get("touch_type", "")
                ma_value = row.get("ma_value", "")
                deviation = row.get("deviation", "")
                signal_type = row.get("signal_type", "")
                date = row.get("date", "")

                # 소수점 자릿수 제한
                if isinstance(change_rate, (int, float)):
                    change_rate = round(change_rate, 2)
                if isinstance(volume_change_percent, (int, float)):
                    volume_change_percent = round(volume_change_percent, 2)
                if isinstance(volume_ratio, (int, float)):
                    volume_ratio = round(volume_ratio, 2)
                if isinstance(rsi, (int, float)):
                    rsi = round(rsi, 2)
                if isinstance(band_value, (int, float)):
                    band_value = round(band_value, 2)
                if isinstance(ma_value, (int, float)):
                    ma_value = round(ma_value, 2)
                if isinstance(deviation, (int, float)):
                    deviation = round(deviation, 2)

                # 숫자 포맷팅
                if isinstance(close, (int, float)):
                    close = f"{close:,.0f}"
                if isinstance(volume, (int, float)):
                    volume = f"{volume:,}"
                if isinstance(current_volume, (int, float)):
                    current_volume = f"{current_volume:,}"
                if isinstance(prev_volume, (int, float)):
                    prev_volume = f"{prev_volume:,}"

                # 결과 구성
                result_parts = [f"{i}. **{name}**"]

                # 기본 정보
                if close:
                    result_parts.append(f"{close}원")
                if change_rate is not None and change_rate != "":
                    if isinstance(change_rate, (int, float)) and change_rate < 0:
                        result_parts.append(f"({change_rate}%)")
                    else:
                        result_parts.append(f"(+{change_rate}%)")

                # 거래량 정보
                if volume:
                    result_parts.append(f"거래량: {volume}주")
                if current_volume and prev_volume:
                    result_parts.append(
                        f"거래량: {current_volume}주 (전일: {prev_volume}주)"
                    )
                if volume_change_percent:
                    result_parts.append(f"증가율: {volume_change_percent}%")
                if volume_ratio:
                    result_parts.append(f"비율: {volume_ratio}배")

                # 기술적 지표 정보
                if rsi:
                    result_parts.append(f"RSI: {rsi}")
                if band_value:
                    result_parts.append(f"밴드값: {band_value}원 ({touch_type})")
                if ma_value:
                    result_parts.append(f"MA: {ma_value}원")
                if deviation:
                    result_parts.append(f"편차: {deviation}%")
                if signal_type:
                    result_parts.append(f"신호: {signal_type}")
                if date:
                    result_parts.append(f"날짜: {date}")

                formatted_results.append(" ".join(result_parts))
            else:
                formatted_results.append(f"{i}. {row}")

        # 전체 개수 정보 추가
        if total_count > 0:
            return f"총 {total_count}개 종목\n" + "\n".join(formatted_results)
        return "\n".join(formatted_results)

    # === sql_generation 카테고리 처리 ===
    elif source == "sql":
        results = data.get("results", [])
        total_count = data.get("total_count", 0)

        if not results:
            return "SQL 쿼리 결과가 없습니다."

        formatted_results = []
        for i, row in enumerate(results[:10], 1):  # 최대 10개까지 표시
            if isinstance(row, dict):
                # SQL 결과의 모든 컬럼을 처리
                result_parts = [f"{i}."]

                for key, value in row.items():
                    if key.lower() in ["name", "종목명", "stock_name"]:
                        result_parts.append(f"**{value}**")
                    elif key.lower() in ["close", "종가", "price"]:
                        if isinstance(value, (int, float)):
                            result_parts.append(f"{value:,.0f}원")
                        else:
                            result_parts.append(f"{value}")
                    elif key.lower() in ["volume", "거래량"]:
                        if isinstance(value, (int, float)):
                            result_parts.append(f"거래량: {value:,}주")
                        else:
                            result_parts.append(f"거래량: {value}")
                    elif key.lower() in ["change_rate", "등락률", "변동률"]:
                        if isinstance(value, (int, float)):
                            if value < 0:
                                result_parts.append(f"({value}%)")
                            else:
                                result_parts.append(f"(+{value}%)")
                        else:
                            result_parts.append(f"({value})")
                    else:
                        # 기타 컬럼들
                        if isinstance(value, (int, float)):
                            if value > 1000:  # 큰 숫자는 천 단위 구분자 적용
                                result_parts.append(f"{key}: {value:,}")
                            else:
                                result_parts.append(f"{key}: {value}")
                        else:
                            result_parts.append(f"{key}: {value}")

                formatted_results.append(" ".join(result_parts))
            else:
                formatted_results.append(f"{i}. {row}")

        # 전체 개수 정보 추가
        if total_count > 0:
            return f"총 {total_count}개 종목\n" + "\n".join(formatted_results)
        return "\n".join(formatted_results)

    # === 기본 처리 (구조화된 결과) ===
    elif isinstance(data, dict) and "total_count" in data:
        total = data["total_count"]
        results = data["results"]
        summary = data.get("summary", f"총 {total}개")

        if not results:
            return ""

        # 핵심 정보만 추출하여 간결하게 표시
        formatted_results = []
        for i, row in enumerate(results[:5], 1):  # 최대 5개만 표시
            if isinstance(row, dict):
                # 종목명과 주요 수치만 추출
                name = row.get("name", "")
                close = row.get("close", "")
                change_rate = row.get("change_rate", "")
                volume = row.get("volume", "")
                current_volume = row.get("current_volume", "")
                prev_volume = row.get("prev_volume", "")
                volume_change_percent = row.get("volume_change_percent", "")
                volume_ratio = row.get("volume_ratio", "")

                # 기술적 지표 데이터 추가
                rsi = row.get("rsi", "")
                band_value = row.get("band_value", "")
                touch_type = row.get("touch_type", "")
                ma_value = row.get("ma_value", "")
                deviation = row.get("deviation", "")
                signal_type = row.get("signal_type", "")
                date = row.get("date", "")

                # 소수점 자릿수 제한
                if isinstance(change_rate, (int, float)):
                    change_rate = round(change_rate, 2)
                if isinstance(volume_change_percent, (int, float)):
                    volume_change_percent = round(volume_change_percent, 2)
                if isinstance(volume_ratio, (int, float)):
                    volume_ratio = round(volume_ratio, 2)
                if isinstance(rsi, (int, float)):
                    rsi = round(rsi, 2)
                if isinstance(band_value, (int, float)):
                    band_value = round(band_value, 2)
                if isinstance(ma_value, (int, float)):
                    ma_value = round(ma_value, 2)
                if isinstance(deviation, (int, float)):
                    deviation = round(deviation, 2)

                # 숫자 포맷팅
                if isinstance(close, (int, float)):
                    close = f"{close:,.0f}"
                if isinstance(volume, (int, float)):
                    volume = f"{volume:,}"
                if isinstance(current_volume, (int, float)):
                    current_volume = f"{current_volume:,}"
                if isinstance(prev_volume, (int, float)):
                    prev_volume = f"{prev_volume:,}"

                # 결과 구성
                result_parts = [f"{i}. **{name}**"]

                # 기본 정보
                if close:
                    result_parts.append(f"{close}원")
                if change_rate is not None and change_rate != "":
                    if isinstance(change_rate, (int, float)) and change_rate < 0:
                        result_parts.append(f"({change_rate}%)")
                    else:
                        result_parts.append(f"(+{change_rate}%)")

                # 거래량 정보
                if volume:
                    result_parts.append(f"거래량: {volume}주")
                if current_volume and prev_volume:
                    result_parts.append(
                        f"거래량: {current_volume}주 (전일: {prev_volume}주)"
                    )
                if volume_change_percent:
                    result_parts.append(f"증가율: {volume_change_percent}%")
                if volume_ratio:
                    result_parts.append(f"비율: {volume_ratio}배")

                # 기술적 지표 정보
                if rsi:
                    result_parts.append(f"RSI: {rsi}")
                if band_value:
                    result_parts.append(f"밴드값: {band_value}원 ({touch_type})")
                if ma_value:
                    result_parts.append(f"MA: {ma_value}원")
                if deviation:
                    result_parts.append(f"편차: {deviation}%")
                if signal_type:
                    result_parts.append(f"신호: {signal_type}")
                if date:
                    result_parts.append(f"날짜: {date}")

                formatted_results.append(" ".join(result_parts))
            else:
                formatted_results.append(f"{i}. {row}")

        # 전체 개수 정보 추가
        if total > 0:
            return f"총 {total}개 종목\n" + "\n".join(formatted_results)
        return "\n".join(formatted_results)

    # === 단순 리스트 처리 ===
    elif isinstance(data, list):
        formatted_results = []
        for i, item in enumerate(data[:5], 1):  # 최대 5개만 표시
            if isinstance(item, dict):
                name = item.get("name", "")
                close = item.get("close", "")
                if isinstance(close, (int, float)):
                    close = f"{close:,.0f}"
                formatted_results.append(f"{i}. **{name}**: {close}원")
            else:
                formatted_results.append(f"{i}. {item}")
        return "\n".join(formatted_results)

    # === 단일 값 처리 ===
    else:
        return str(data)


def generate_response(state: StockAgentState) -> StockAgentState:
    query = state["query"]
    clarification_info = state.get("clarification_info", {})

    # 통합된 data state에서 데이터 포맷팅
    data = state["data"]
    data_formatted = format_data_for_llm(data, f"{data.get('source', '조회')} 데이터")

    # SQL 정보 추가 (SQL 관련인 경우)
    sql_info = ""
    if data.get("sql"):
        sql_info = f"\n생성된 SQL: {data['sql']}"

    # 구체화 정보가 있는 경우 설명 추가
    clarification_explanation = ""
    if clarification_info:
        original_query = clarification_info.get("original_query", "")
        start_date = clarification_info.get("start_date", "")
        end_date = clarification_info.get("end_date", "")
        primary_criteria = clarification_info.get("primary_criteria", "")

        logger.info(f"--Clarification info found: {clarification_info}--")

        if original_query and primary_criteria:
            # 구체화 정보가 있음을 표시 (LLM이 직접 처리하도록)
            clarification_explanation = True
            logger.info(f"--Clarification info available for LLM processing--")
    else:
        logger.info("--No clarification info found--")

        # 구체화 과정 여부에 따라 프롬프트 선택
    if clarification_explanation:
        # 구체화된 질문용 프롬프트 사용
        selected_system_msg = CLARIFIED_QUERY_SYSTEM_MSG
        logger.info("--Using clarified query prompt--")
    else:
        # 일반 질문용 프롬프트 사용
        selected_system_msg = SYSTEM_MSG
        logger.info("--Using general query prompt--")

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", selected_system_msg),
            (
                "user",
                """
            질문: {query}
            배경지식: {context}
            {data}
""",
            ),
        ]
    )

    # 데이터 준비 (구체화 정보가 있으면 포함)
    final_data = data_formatted + sql_info
    if clarification_explanation:
        final_data = f"원본 질문: {original_query}\n구체화된 질문: {clarification_info.get('clarified_query', '')}\n기간: {start_date} ~ {end_date}\n조건: {primary_criteria}\n\n[조회 결과]\n{final_data}"

    response = llm.invoke(
        prompt.invoke(
            {
                "query": state["query"],
                "context": state["context"],
                "data": final_data,
            }
        )
    )

    state["response"] = response.content

    logger.info(f"--Generated Response: {state['response']}--")
    return state
