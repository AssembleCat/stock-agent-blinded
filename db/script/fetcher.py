from pykrx import stock as krx
import yfinance as yf
from datetime import datetime


def get_all_tickers_and_names(start_date: str, end_date: str, verbose=True):
    """
    지정된 기간의 모든 종목 리스트를 수집합니다.

    Args:
        start_date: 시작일자 (YYYY-MM-DD 형식)
        end_date: 끝일자 (YYYY-MM-DD 형식)
        verbose: 상세 출력 여부

    Returns:
        tuple: (tickers, names, markets)
    """
    # 날짜 형식을 pykrx 형식으로 변환 (YYYY-MM-DD -> YYYYMMDD)
    start_date_pykrx = start_date.replace("-", "")
    end_date_pykrx = end_date.replace("-", "")

    # pykrx에서 영업일만 추출
    business_days = krx.get_previous_business_days(
        fromdate=start_date_pykrx, todate=end_date_pykrx
    )
    all_tickers = set()
    ticker_info = dict()  # {ticker: (name, market)}

    for idx, date in enumerate(business_days, 1):
        date_str = date.strftime("%Y%m%d")
        if verbose and (idx % 10 == 0 or idx == 1 or idx == len(business_days)):
            print(f"  - 영업일 {idx}/{len(business_days)}: {date_str}")
        for market in ["KOSPI", "KOSDAQ"]:
            try:
                tlist = krx.get_market_ticker_list(date_str, market=market)
                if verbose:
                    print(f"    > {date_str} {market}: {len(tlist)}개 종목")
                for t in tlist:
                    all_tickers.add(t)
                    ticker_info[t] = (krx.get_market_ticker_name(t), market)
            except Exception as e:
                if verbose:
                    print(f"    ! Error on {date_str} {market}: {e}")
                pass

    tickers, names, markets = [], [], []
    for t in sorted(all_tickers):
        n, m = ticker_info[t]
        tickers.append(t)
        names.append(n)
        markets.append(m)

    if verbose:
        print(f"  - 최종 통합 종목 수: {len(tickers)}개")
    return tickers, names, markets

def to_yf_ticker(ticker, market):
    return f"{ticker}.KS" if market == "KOSPI" else f"{ticker}.KQ"
