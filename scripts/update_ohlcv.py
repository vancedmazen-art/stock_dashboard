import os
import json
import time
import traceback
import pandas as pd
from datetime import datetime, timezone

# data_provider.py lives one level up (repo root)
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data_provider import get_OHLCV_data

# =============================
# CONFIG
# =============================
REPO_ROOT      = os.path.join(os.path.dirname(__file__), "..")
WATCHLIST_FILE = os.path.join(REPO_ROOT, "watchlist.txt")

DATA_DIR       = os.path.join(REPO_ROOT, "data")
JSON_DIR       = os.path.join(DATA_DIR, "json")
OHLCV_FILE     = os.path.join(DATA_DIR, "ohlcv.csv")
CSV_OUTPUT     = os.path.join(DATA_DIR, "all_tickers.csv")

MAX_RETRIES    = 5
WAIT_SEC       = 3

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)


# =============================
# LOAD WATCHLIST
# =============================
def load_watchlist() -> list[str]:
    if not os.path.exists(WATCHLIST_FILE):
        raise FileNotFoundError(f"Watchlist not found: {WATCHLIST_FILE}")
    with open(WATCHLIST_FILE, "r") as f:
        symbols = [l.strip() for l in f if l.strip()]
    if not symbols:
        raise ValueError("Watchlist is empty")
    return symbols


# =============================
# LOAD EXISTING OHLCV
# =============================
def load_existing() -> pd.DataFrame:
    if os.path.exists(OHLCV_FILE):
        df = pd.read_csv(OHLCV_FILE)
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        return df
    return pd.DataFrame()


# =============================
# FETCH WITH RETRIES
# =============================
def fetch(symbol: str, n_bars: int = 720) -> pd.DataFrame | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = get_OHLCV_data(symbol=symbol, exchange="EGX", interval="Daily", n_bars=n_bars)
            if df is None or df.empty:
                raise ValueError("Empty dataframe")
            df["QuoteTime"] = datetime.now(timezone.utc)
            return df
        except Exception as e:
            print(f"  ⚠ {symbol} attempt {attempt}/{MAX_RETRIES}: {e}")
            traceback.print_exc()
            if attempt < MAX_RETRIES:
                time.sleep(WAIT_SEC)
    print(f"  ❌ Giving up on {symbol}")
    return None


# =============================
# MAIN
# =============================
def main():
    print("🚀 EGX Pipeline started")

    watchlist   = load_watchlist()
    existing_df = load_existing()
    print(f"📊 {len(watchlist)} symbols | {len(existing_df)} existing rows")

    # Precompute dedup keys once
    existing_keys = (
        set(existing_df["Symbol"].astype(str) + "_" + existing_df["datetime"].astype(str))
        if not existing_df.empty else set()
    )

    new_ohlcv_frames = []   # for ohlcv.csv
    all_ticker_rows  = []   # for all_tickers.csv (full history every run)

    for symbol in watchlist:
        print(f"\n→ {symbol}")
        df = fetch(symbol)
        if df is None:
            continue

        clean      = df.attrs.get("clean_symbol", symbol.replace("EGX:", ""))
        raw_json   = df.attrs.get("raw_json", {})

        # ── 1. Individual JSON ─────────────────────────────────────────
        json_path = os.path.join(JSON_DIR, f"{clean}_data.json")
        with open(json_path, "w") as f:
            json.dump(raw_json, f)

        # ── 2. all_tickers.csv rows (full history, overwritten each run) ─
        ticker_df = df[["Symbol", "datetime", "open", "high", "low", "close", "volume"]].copy()
        ticker_df = ticker_df.rename(columns={
            "datetime": "Date", "open": "Open", "high": "High",
            "low": "Low",       "close": "Close", "volume": "Volume",
        })
        all_ticker_rows.append(ticker_df)

        # ── 3. ohlcv.csv — only truly new rows ────────────────────────
        df["_key"] = df["Symbol"].astype(str) + "_" + df["datetime"].astype(str)
        new_rows   = df[~df["_key"].isin(existing_keys)].drop(columns=["_key"])

        if not new_rows.empty:
            new_ohlcv_frames.append(new_rows)
            print(f"  ✅ {len(new_rows)} new rows")
        else:
            print(f"  ⏭  no new rows")

    # ── Save ohlcv.csv ─────────────────────────────────────────────────
    if new_ohlcv_frames:
        combined = pd.concat([existing_df] + new_ohlcv_frames, ignore_index=True)
        combined = combined.drop_duplicates(subset=["Symbol", "datetime"])
        combined.to_csv(OHLCV_FILE, index=False)
        print(f"\n💾 ohlcv.csv → {len(combined)} total rows")
    else:
        print("\n⚠  No new rows — ohlcv.csv unchanged")

    # ── Save all_tickers.csv (full refresh every run) ──────────────────
    if all_ticker_rows:
        all_df = pd.concat(all_ticker_rows, ignore_index=True)
        all_df.to_csv(CSV_OUTPUT, index=False)
        print(f"💾 all_tickers.csv → {len(all_df)} rows across {len(all_ticker_rows)} symbols")

    print("\n✅ Pipeline complete — git step will commit & push")


if __name__ == "__main__":
    main()
