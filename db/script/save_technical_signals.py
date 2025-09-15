from db.script.models import TechnicalSignal, OHLCV
from db.script.database import SessionLocal
import pandas as pd
import pandas_ta as ta
import argparse
import sys
from datetime import datetime
from collections import defaultdict
from sqlalchemy import and_


def save_technical_signals_from_ohlcv(start_date: str, end_date: str):
    """
    OHLCV 데이터를 기반으로 기술적 지표를 계산하고 저장합니다.

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

    pd.set_option("display.max_columns", None)
    db = SessionLocal()
    print(f"[1/2] OHLCV 데이터 조회 중... (기간: {start_date} ~ {end_date})")

    # 지정된 기간의 OHLCV 데이터만 조회
    ohlcv_rows = (
        db.query(OHLCV)
        .filter(and_(OHLCV.date >= start_dt.date(), OHLCV.date <= end_dt.date()))
        .all()
    )

    if not ohlcv_rows:
        print(f"  - {start_date} ~ {end_date} 기간의 OHLCV 데이터가 없습니다.")
        return

    print(f"  - 조회된 데이터: {len(ohlcv_rows)}건")

    ticker_to_rows = defaultdict(list)
    for row in ohlcv_rows:
        ticker_to_rows[row.ticker].append(row)

    to_save = []
    signals_added = 0
    signals_skipped = 0

    for ticker, rows in ticker_to_rows.items():
        rows = sorted(rows, key=lambda x: x.date)
        # close 컬럼에 adj_close 값을 할당하여 수정종가 기준으로 지표 연산
        df = pd.DataFrame(
            [
                {
                    "date": r.date,
                    "close": r.adj_close,  # 수정종가만 사용
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "volume": r.volume,
                    "value": r.value,
                }
                for r in rows
            ]
        )
        if df.empty:
            continue
        df = df.sort_values("date")
        df = df.fillna(0)
        df.set_index("date", inplace=True)
        # pandas-ta로 기술적 지표 연산 (close=adj_close 기준)
        df.ta.sma(length=5, append=True)
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=60, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, append=True)

        # 거래량 이동평균 계산 (수동으로 계산)
        df["VOLUME_MA_5"] = df["volume"].rolling(window=5).mean()
        df["VOLUME_MA_20"] = df["volume"].rolling(window=20).mean()
        df["VOLUME_MA_60"] = df["volume"].rolling(window=60).mean()
        # 골든/데드크로스 신호 (SMA_5, SMA_20 컬럼이 있을 때만)
        if "SMA_5" in df.columns and "SMA_20" in df.columns:
            df["GOLDEN_CROSS"] = (df["SMA_5"] > df["SMA_20"]) & (
                df["SMA_5"].shift(1) <= df["SMA_20"].shift(1)
            )
            df["DEAD_CROSS"] = (df["SMA_5"] < df["SMA_20"]) & (
                df["SMA_5"].shift(1) >= df["SMA_20"].shift(1)
            )
        else:
            df["GOLDEN_CROSS"] = False
            df["DEAD_CROSS"] = False
        df = df.reset_index()

        for i, row in df.iterrows():
            date_val = row["date"]

            # 중복 체크: ticker + date + indicator 조합
            existing_signals = (
                db.query(TechnicalSignal)
                .filter(
                    and_(
                        TechnicalSignal.ticker == ticker,
                        TechnicalSignal.date == date_val,
                    )
                )
                .all()
            )
            existing_indicators = {signal.indicator for signal in existing_signals}

            # RSI
            if pd.notnull(row.get("RSI_14")) and "RSI_14" not in existing_indicators:
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="RSI_14",
                        value=row["RSI_14"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("RSI_14")):
                signals_skipped += 1

            # 볼린저밴드 상단/하단
            if (
                pd.notnull(row.get("BBU_20_2.0"))
                and "BOLLINGER_UPPER" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="BOLLINGER_UPPER",
                        value=row["BBU_20_2.0"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("BBU_20_2.0")):
                signals_skipped += 1

            if (
                pd.notnull(row.get("BBL_20_2.0"))
                and "BOLLINGER_LOWER" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="BOLLINGER_LOWER",
                        value=row["BBL_20_2.0"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("BBL_20_2.0")):
                signals_skipped += 1

            # 이동평균선
            if pd.notnull(row.get("SMA_5")) and "MA_5" not in existing_indicators:
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="MA_5",
                        value=row["SMA_5"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("SMA_5")):
                signals_skipped += 1

            if pd.notnull(row.get("SMA_20")) and "MA_20" not in existing_indicators:
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="MA_20",
                        value=row["SMA_20"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("SMA_20")):
                signals_skipped += 1

            if pd.notnull(row.get("SMA_60")) and "MA_60" not in existing_indicators:
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="MA_60",
                        value=row["SMA_60"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("SMA_60")):
                signals_skipped += 1

            # 거래량 이동평균
            if (
                pd.notnull(row.get("VOLUME_MA_5"))
                and "VOLUME_MA_5" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="VOLUME_MA_5",
                        value=row["VOLUME_MA_5"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("VOLUME_MA_5")):
                signals_skipped += 1

            if (
                pd.notnull(row.get("VOLUME_MA_20"))
                and "VOLUME_MA_20" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="VOLUME_MA_20",
                        value=row["VOLUME_MA_20"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("VOLUME_MA_20")):
                signals_skipped += 1

            if (
                pd.notnull(row.get("VOLUME_MA_60"))
                and "VOLUME_MA_60" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="VOLUME_MA_60",
                        value=row["VOLUME_MA_60"],
                    )
                )
                signals_added += 1
            elif pd.notnull(row.get("VOLUME_MA_60")):
                signals_skipped += 1

            # 골든/데드크로스 신호
            if (
                row.get("GOLDEN_CROSS") is True
                and "GOLDEN_CROSS" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="GOLDEN_CROSS",
                        value=1.0,
                    )
                )
                signals_added += 1
            elif row.get("GOLDEN_CROSS") is True:
                signals_skipped += 1

            if (
                row.get("DEAD_CROSS") is True
                and "DEAD_CROSS" not in existing_indicators
            ):
                to_save.append(
                    TechnicalSignal(
                        ticker=ticker,
                        date=date_val,
                        indicator="DEAD_CROSS",
                        value=1.0,
                    )
                )
                signals_added += 1
            elif row.get("DEAD_CROSS") is True:
                signals_skipped += 1

        print(f"  - {ticker} 기술적 지표 저장 준비 완료")
    print(f"[2/2] {len(to_save)}건 bulk 저장 중...")
    if to_save:
        db.add_all(to_save)
        db.commit()
        print(f"  - {len(to_save)}건 저장 완료")
    else:
        print("  - 저장할 새로운 데이터가 없습니다.")
    db.close()
    print(
        f"[완료] {start_date} ~ {end_date} 기간의 모든 종목 기술적 지표 저장이 끝났습니다."
    )
    print(f"  - 새로 추가: {signals_added}건, 중복 건너뜀: {signals_skipped}건")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="기술적 지표 계산 및 저장")
    parser.add_argument(
        "--start-date", type=str, required=True, help="시작일자 (YYYY-MM-DD 형식)"
    )
    parser.add_argument(
        "--end-date", type=str, required=True, help="끝일자 (YYYY-MM-DD 형식)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📈 기술적 지표 계산 및 저장 시작")
    print(f"📅 기간: {args.start_date} ~ {args.end_date}")
    print("=" * 60)

    save_technical_signals_from_ohlcv(args.start_date, args.end_date)
