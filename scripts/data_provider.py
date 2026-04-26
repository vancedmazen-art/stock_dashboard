from egxpy.download import get_OHLCV_data as egx_get_data

def get_OHLCV_data(symbol, exchange="EGX", interval="Daily", n_bars=1000):

    df = egx_get_data(
        symbol=symbol,
        exchange=exchange,
        interval=interval,
        n_bars=n_bars
    )

    # safety checks only (NO MOCKING)
    if df is None or df.empty:
        raise ValueError(f"No data returned for {symbol}")

    return df
