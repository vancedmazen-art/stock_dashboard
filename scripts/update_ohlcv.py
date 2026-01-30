import os
import time
import traceback
import pandas as pd
from datetime import datetime
from egxpy.download import get_OHLCV_data


# =============================
# PATHS
# =============================

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

WATCHLIST_FILE = os.path.join(BASE_DIR, "watchlist.txt")
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_FILE = os.path.join(DATA_DIR, "egx_ohlcv.csv")


# =============================
# CONFIG
# =============================

MAX_RETRIES = 5
WAIT_SEC = 3


# =============================
# LOAD WATCHLIST
# =============================

def load_watchlist():

    with open(WATCHLIST_FILE, "r") as f:
        return [x.strip() for x in f if x.strip()]


# =============================
# FETCH DATA
# =============================

def fetch_ohlcv(symbol, interval="Daily", n_bars=5000):

    for i in range(MAX_RETRIES):

        try:

            df = get_OHLCV_data(
                symbol=symbol,
                exchange="EGX",
                interval=interval,
                n_bars=n_bars
            )

            if df is not None and not df.empty:

                df = df.reset_index()

                df["Symbol"] = symbol.replace("EGX:", "")
                df["QuoteTime"] = datetime.utcnow()

                return df

        except Exception as e:

            print(f"Error {symbol}: {e}")
            traceback.print_exc()

        time.sleep(WAIT_SEC)

    return None


# =============================
# SAVE TO CSV
# =============================

def save_csv(df):

    os.makedirs(DATA_DIR, exist_ok=True)

    df = df[[
        "Symbol",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "QuoteTime"
    ]]

    df.columns = [
        "Symbol",
        "DateTime",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "QuoteTime"
    ]

    if os.path.exists(CSV_FILE):

        old = pd.read_csv(CSV_FILE, parse_dates=["DateTime"])

        df = pd.concat([old, df])

        df = df.drop_duplicates(
            subset=["Symbol", "DateTime"]
        )

    df.sort_values(["Symbol", "DateTime"], inplace=True)

    df.to_csv(CSV_FILE, index=False)

    print("CSV Updated")


# =============================
# MAIN
# =============================

def main():

    watchlist = load_watchlist()

    print("Symbols:", watchlist)

    for sym in watchlist:

        df = fetch_ohlcv(sym)

        if df is not None:
            save_csv(df)


if __name__ == "__main__":
    main()
