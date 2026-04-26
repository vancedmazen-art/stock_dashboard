import pandas as pd
import numpy as np

def get_OHLCV_data(symbol, exchange="EGX", interval="Daily", n_bars=20000):

    # TEMP MOCK DATA (so pipeline works)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=200)

    df = pd.DataFrame({
        "datetime": dates,
        "open": np.random.rand(len(dates)) * 100,
        "high": np.random.rand(len(dates)) * 100,
        "low": np.random.rand(len(dates)) * 100,
        "close": np.random.rand(len(dates)) * 100,
        "volume": np.random.randint(1000, 5000, len(dates)),
    })

    return df
