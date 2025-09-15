from db.script.models import Base, Stock, OHLCV, MarketIndexOHLCV, TechnicalSignal
from db.script.database import engine, SessionLocal
from db.script.fetcher import (
    get_all_tickers_and_names,
    to_yf_ticker,
)
from pykrx import stock as krx
from datetime import datetime
import yfinance as yf
import pandas as pd
import argparse
import sys
from sqlalchemy import and_

# 1. 테이블 생성
Base.metadata.create_all(bind=engine)

def main(start_date: str, end_date: str):
    """
    주식 데이터베이스 초기 구성을 실행합니다.

    Args:
        start_date: 시작일자 (YYYY-MM-DD 형식)
        end_date: 끝일자 (YYYY-MM-DD 형식)
    """
    # 날짜 형식 검증
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        print(
            "❌ 오류: 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요."
        )
        sys.exit(1)

    # 시작일이 끝일보다 늦은 경우 체크
    if start_date > end_date:
        print("❌ 오류: 시작일이 끝일보다 늦을 수 없습니다.")
        sys.exit(1)

    db = SessionLocal()
    print(f"[1/5] 전체 종목 리스트 수집 중... (기간: {start_date} ~ {end_date})")
    tickers, names, markets = get_all_tickers_and_names(start_date, end_date)
    print(f"  - 종목 수: {len(tickers)}개")

    print("[2/5] 영업일 리스트 수집 중...")
    business_days = krx.get_previous_business_days(
        fromdate=start_date.replace("-", ""), todate=end_date.replace("-", "")
    )
    business_days_set = set([d.date() for d in business_days])
    print(f"  - 영업일 수: {len(business_days)}일")

    print("[3/5] 종목 정보 저장 중...")
    stocks_added = 0
    for t, n, m in zip(tickers, names, markets):
        yf_ticker = to_yf_ticker(t, m)
        stock_obj = db.query(Stock).filter_by(ticker=yf_ticker).first()
        if not stock_obj:
            db.add(Stock(ticker=yf_ticker, name=n, market=m))
            stocks_added += 1
    db.commit()
    print(f"  - 종목 정보 저장 완료 (새로 추가: {stocks_added}개)")

    print("[4/5] 시세/지표 저장 중...")
    # 종목별 전체 데이터 한 번에 받아서 영업일별로 저장
    ticker_to_df = {}
    ohlcv_added = 0
    ohlcv_skipped = 0

    for idx, (t, m) in enumerate(zip(tickers, markets), 1):
        yf_ticker = to_yf_ticker(t, m)
        try:
            df = yf.Ticker(yf_ticker).history(
                start=start_date, end=end_date, auto_adjust=False
            )
            if df.empty:
                continue
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["Date"]).dt.date
            df = df[df["date"].isin(business_days_set)]
            df = df.sort_values("date")
            df = df.fillna(0)  # 결측치 0으로 일괄 대체
            ticker_to_df[yf_ticker] = df

            for i, row in df.iterrows():
                # 거래량이 0인 경우 제거
                if row["Volume"] == 0:
                    continue

                # 중복 체크: ticker + date 조합
                ohlcv_obj = (
                    db.query(OHLCV)
                    .filter(and_(OHLCV.ticker == yf_ticker, OHLCV.date == row["date"]))
                    .first()
                )

                if not ohlcv_obj:
                    # 등락률 계산
                    prev_close = (
                        df[df["date"] < row["date"]]["Close"].iloc[-1]
                        if len(df[df["date"] < row["date"]]) > 0
                        else None
                    )
                    change_rate = (
                        ((row["Close"] - prev_close) / prev_close) * 100
                        if prev_close
                        else None
                    )
                    db.add(
                        OHLCV(
                            ticker=yf_ticker,
                            date=row["date"],
                            open=row["Open"],
                            high=row["High"],
                            low=row["Low"],
                            close=row["Close"],
                            adj_close=row["Adj Close"],
                            volume=int(row["Volume"]),
                            value=int(row["Close"] * row["Volume"]),
                            change_rate=(
                                round(change_rate, 2)
                                if change_rate is not None
                                else None
                            ),
                        )
                    )
                    ohlcv_added += 1
                else:
                    ohlcv_skipped += 1

            if idx % 100 == 0 or idx == len(tickers):
                print(f"  - {idx}/{len(tickers)} 종목 처리 완료")
        except Exception as e:
            print(f"    ! {yf_ticker} 전체 데이터 적재 에러: {e}")
        db.commit()
    print(
        f"  - 시세 저장 완료 (새로 추가: {ohlcv_added}건, 중복 건너뜀: {ohlcv_skipped}건)"
    )

    print("[5/5] 시장지수 저장 중...")
    # 영업일별, 시장별로 거래대금 합산
    market_index_added = 0
    market_index_skipped = 0

    for day_idx, date in enumerate(business_days, 1):
        date_val = date.date()
        date_str = date_val.strftime("%Y-%m-%d")
        for market, yf_code in [("KOSPI", "^KS11"), ("KOSDAQ", "^KQ11")]:
            market_tickers = [t for t, mkt in zip(tickers, markets) if mkt == market]
            total_value = 0
            for t in market_tickers:
                df = ticker_to_df.get(to_yf_ticker(t, market))
                if df is not None:
                    row = df[df["date"] == date_val]
                    if not row.empty:
                        total_value += row.iloc[0]["Close"] * row.iloc[0]["Volume"]

            # 중복 체크: market + date 조합
            idx_obj = (
                db.query(MarketIndexOHLCV)
                .filter(
                    and_(
                        MarketIndexOHLCV.market == market,
                        MarketIndexOHLCV.date == date_val,
                    )
                )
                .first()
            )

            if not idx_obj:
                # end를 하루 뒤로 지정 (yfinance는 end exclusive)
                from datetime import timedelta

                next_date_val = date_val + timedelta(days=1)
                next_date_str = next_date_val.strftime("%Y-%m-%d")
                idx_df = yf.Ticker(yf_code).history(start=date_str, end=next_date_str)
                if not idx_df.empty:
                    idx_today = idx_df.iloc[0]
                    db.add(
                        MarketIndexOHLCV(
                            market=market,
                            date=date_val,
                            open=idx_today["Open"],
                            high=idx_today["High"],
                            low=idx_today["Low"],
                            close=idx_today["Close"],
                            volume=int(idx_today["Volume"]),
                            value=int(total_value),
                        )
                    )
                    market_index_added += 1
            else:
                market_index_skipped += 1

        if day_idx % 10 == 0 or day_idx == len(business_days):
            print(f"  - {day_idx}/{len(business_days)} 영업일 시장지수 처리 완료")
        db.commit()
    print(
        f"  - 시장지수 저장 완료 (새로 추가: {market_index_added}건, 중복 건너뜀: {market_index_skipped}건)"
    )
    db.close()
    print(f"[완료] {start_date} ~ {end_date} 기간의 모든 데이터 적재가 끝났습니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="주식 데이터베이스 초기 구성")
    parser.add_argument(
        "--start-date", type=str, required=True, help="시작일자 (YYYY-MM-DD 형식)"
    )
    parser.add_argument(
        "--end-date", type=str, required=True, help="끝일자 (YYYY-MM-DD 형식)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📊 주식 데이터베이스 초기 구성 시작")
    print(f"📅 기간: {args.start_date} ~ {args.end_date}")
    print("=" * 60)

    main(args.start_date, args.end_date)
