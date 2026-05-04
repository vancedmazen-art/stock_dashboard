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
    """
    Fetch OHLCV data for an EGX symbol via investiny.
    Returns a DataFrame with columns: datetime, open, high, low, close, volume, Symbol
    Also attaches raw_json and clean_symbol to df.attrs for the pipeline to use.
    """
    cache = _load_cache()
    clean = symbol.replace(f"{exchange}:", "").strip()

    # ── Resolve investing.com numeric ID ─────────────────────────────
    if clean not in cache:
        try:
            asset_type = "Index" if clean == "EGX30" else "Stock"
            results = search_assets(query=clean, limit=1, type=asset_type, exchange=exchange)
            if results:
                cache[clean] = int(results[0]["ticker"])
                _save_cache(cache)
            else:
                print(f"  ❌ {clean}: not found on investing.com")
                return None
        except Exception as e:
            print(f"  ❌ {clean}: search failed — {e}")
            return None

    investing_id = cache.get(clean)
    if not investing_id:
        return None

    # ── Date range (n_bars trading days → calendar days with buffer) ──
    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=int(n_bars * 1.45))

    try:
        raw = historical_data(
            investing_id=investing_id,
            from_date=from_dt.strftime("%m/%d/%Y"),
            to_date=to_dt.strftime("%m/%d/%Y"),
        )
    except Exception as e:
        print(f"  ❌ {clean}: historical_data failed — {e}")
        return None

    # ── Normalize keys (investiny returns lowercase, but guard anyway) ─
    dates   = raw.get("date",   raw.get("Date",   []))
    opens   = raw.get("open",   raw.get("Open",   [None] * len(dates)))
    highs   = raw.get("high",   raw.get("High",   [None] * len(dates)))
    lows    = raw.get("low",    raw.get("Low",    [None] * len(dates)))
    closes  = raw.get("close",  raw.get("Close",  [None] * len(dates)))
    volumes = raw.get("volume", raw.get("Volume", [None] * len(dates)))

    if not dates:
        print(f"  ⚠  {clean}: empty response")
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

    df.attrs["raw_json"]     = raw
    df.attrs["clean_symbol"] = clean
    return df
