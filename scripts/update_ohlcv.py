import os
import time
import traceback
import pandas as pd
from datetime import datetime
from data_provider import get_OHLCV_data

# =============================
# CONFIG
# =============================
import os

WATCHLIST_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "watchlist.txt"
)
DATA_FILE = "data/ohlcv.csv"

MAX_RETRIES = 5
WAIT_SEC = 3


# =============================
# LOAD WATCHLIST
# =============================
def load_watchlist():
    with open(WATCHLIST_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


# =============================
# LOAD EXISTING DATA
# =============================
def load_existing_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame()


# =============================
# FETCH DATA
# =============================
def fetch_ohlcv(symbol, n_bars=720):

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = get_OHLCV_data(
                symbol=symbol,
                exchange="EGX",
                interval="Daily",
                n_bars=n_bars
            )

            if df is None or df.empty:
                continue

            df = df.reset_index()

            df["Symbol"] = symbol.replace("EGX:", "")
            df["QuoteTime"] = datetime.now()

            return df

        except Exception as e:
            print(f"⚠ {symbol} attempt {attempt} failed: {e}")
            traceback.print_exc()

        time.sleep(WAIT_SEC)

    print(f"❌ Failed: {symbol}")
    return None


# =============================
# MAIN PIPELINE
# =============================
def main():

    watchlist = load_watchlist()
    existing_df = load_existing_data()

    all_new_data = []

    print(f"🚀 Processing {len(watchlist)} symbols")

    for symbol in watchlist:

        df = fetch_ohlcv(symbol)

        if df is None:
            continue

        # =============================
        # DEDUP LOGIC (CRITICAL FIX)
        # =============================
        if not existing_df.empty:
            existing_keys = set(
                existing_df["Symbol"].astype(str) + "_" +
                existing_df["datetime"].astype(str)
            )

            df["key"] = df["Symbol"].astype(str) + "_" + df["datetime"].astype(str)
            df = df[~df["key"].isin(existing_keys)]
            df.drop(columns=["key"], inplace=True)

        if not df.empty:
            all_new_data.append(df)
            print(f"✅ {symbol}: {len(df)} new rows")
        else:
            print(f"⏭ {symbol}: no new data")

    # =============================
    # SAVE
    # =============================
    if all_new_data:

        new_df = pd.concat(all_new_data, ignore_index=True)

        final_df = pd.concat([existing_df, new_df], ignore_index=True)

        final_df = final_df.drop_duplicates(
            subset=["Symbol", "datetime"]
        )

        os.makedirs("data", exist_ok=True)
        final_df.to_csv(DATA_FILE, index=False)

        print(f"\n💾 Saved total rows: {len(final_df)}")

    else:
        print("\n⚠ No new data today")


if __name__ == "__main__":
    main()
