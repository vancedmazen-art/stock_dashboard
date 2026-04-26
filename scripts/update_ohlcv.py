import os
import time
import traceback
import pandas as pd
from datetime import datetime, timezone
from data_provider import get_OHLCV_data

# =============================
# CONFIG
# =============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WATCHLIST_FILE = os.path.join(BASE_DIR, "..", "watchlist.txt")
DATA_FILE = os.path.join(BASE_DIR, "..", "data", "ohlcv.csv")

MAX_RETRIES = 5
WAIT_SEC = 3


# =============================
# LOAD WATCHLIST
# =============================
def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        raise FileNotFoundError(f"Watchlist not found: {WATCHLIST_FILE}")

    with open(WATCHLIST_FILE, "r") as f:
        symbols = [line.strip() for line in f if line.strip()]

    if not symbols:
        raise ValueError("Watchlist is empty")

    return symbols


# =============================
# LOAD EXISTING DATA
# =============================
def load_existing_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)

        # ensure schema consistency
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

        return df

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
                raise ValueError("Empty dataframe returned")

            # =============================
            # NORMALIZATION (CRITICAL)
            # =============================
            df = df.reset_index(drop=True)

            # enforce datetime column
            if "datetime" not in df.columns:
                raise ValueError("Missing 'datetime' column from provider")

            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

            df["Symbol"] = symbol.replace("EGX:", "")
            df["QuoteTime"] = datetime.now(timezone.utc)

            return df

        except Exception as e:
            print(f"⚠ {symbol} attempt {attempt}/{MAX_RETRIES} failed: {e}")
            traceback.print_exc()

            if attempt < MAX_RETRIES:
                time.sleep(WAIT_SEC)

    print(f"❌ Failed completely: {symbol}")
    return None


# =============================
# MAIN PIPELINE
# =============================
def main():

    print("🚀 EGX Pipeline started")

    watchlist = load_watchlist()
    existing_df = load_existing_data()

    all_new_data = []

    print(f"📊 Processing {len(watchlist)} symbols")

    # Precompute existing keys ONCE (big performance win)
    if not existing_df.empty:
        existing_df["datetime"] = pd.to_datetime(existing_df["datetime"], errors="coerce")

        existing_keys = set(
            existing_df["Symbol"].astype(str) + "_" +
            existing_df["datetime"].astype(str)
        )
    else:
        existing_keys = set()

    for symbol in watchlist:

        df = fetch_ohlcv(symbol)

        if df is None:
            continue

        # =============================
        # DEDUP LOGIC
        # =============================
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

        # ensure directory exists
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

        final_df.to_csv(DATA_FILE, index=False)

        print(f"\n💾 Saved total rows: {len(final_df)}")

    else:
        print("\n⚠ No new data today")


if __name__ == "__main__":
    main()
