import json
import os
import pandas as pd
from datetime import datetime, timedelta
from investiny import historical_data, search_assets

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbol_cache.json")


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_OHLCV_data(
    symbol: str,
    exchange: str = "EGX",
    interval: str = "Daily",
    n_bars: int = 720,
) -> pd.DataFrame | None:

    cache = _load_cache()
    clean = symbol.replace(f"{exchange}:", "").strip()
    print(f"    [dp] resolving '{clean}'")

    # ── Resolve investing.com ID ──────────────────────────────────────
    if clean not in cache:
        print(f"    [dp] not in cache, searching investing.com...")
        try:
            asset_type = "Index" if clean == "EGX30" else "Stock"
            results = search_assets(query=clean, limit=5, type=asset_type, exchange=exchange)
            print(f"    [dp] search returned: {results}")

            if results:
                cache[clean] = int(results[0]["ticker"])
                _save_cache(cache)
                print(f"    [dp] cached ID={cache[clean]}")
            else:
                print(f"    [dp] ❌ no results from search_assets")
                return None

        except Exception as e:
            print(f"    [dp] ❌ search_assets exception: {type(e).__name__}: {e}")
            return None
    else:
        print(f"    [dp] found in cache: ID={cache[clean]}")

    investing_id = cache.get(clean)
    if not investing_id:
        print(f"    [dp] ❌ investing_id is None/0 after cache lookup")
        return None

    # ── Fetch historical data ─────────────────────────────────────────
    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=int(n_bars * 1.45))
    from_str = from_dt.strftime("%m/%d/%Y")
    to_str   = to_dt.strftime("%m/%d/%Y")
    print(f"    [dp] fetching ID={investing_id}  {from_str} → {to_str}")

    try:
        raw = historical_data(
            investing_id=investing_id,
            from_date=from_str,
            to_date=to_str,
        )
        print(f"    [dp] raw keys: {list(raw.keys()) if isinstance(raw, dict) else type(raw)}")
        if isinstance(raw, dict):
            for k, v in raw.items():
                print(f"    [dp]   {k}: {len(v) if isinstance(v, list) else v} items")

    except Exception as e:
        print(f"    [dp] ❌ historical_data exception: {type(e).__name__}: {e}")
        return None

    # ── Normalize ─────────────────────────────────────────────────────
    dates   = raw.get("date",   raw.get("Date",   []))
    opens   = raw.get("open",   raw.get("Open",   [None] * len(dates)))
    highs   = raw.get("high",   raw.get("High",   [None] * len(dates)))
    lows    = raw.get("low",    raw.get("Low",    [None] * len(dates)))
    closes  = raw.get("close",  raw.get("Close",  [None] * len(dates)))
    volumes = raw.get("volume", raw.get("Volume", [None] * len(dates)))

    print(f"    [dp] dates found: {len(dates)}")

    if not dates:
        print(f"    [dp] ❌ dates list is empty — returning None")
        return None

    df = pd.DataFrame({
        "datetime": pd.to_datetime(dates, errors="coerce"),
        "open":     opens,
        "high":     highs,
        "low":      lows,
        "close":    closes,
        "volume":   volumes,
        "Symbol":   clean,
    })

    print(f"    [dp] ✅ built DataFrame: {len(df)} rows")
    df.attrs["raw_json"]     = raw
    df.attrs["clean_symbol"] = clean
    return df
