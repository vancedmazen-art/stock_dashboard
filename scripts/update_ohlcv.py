import json
import os
import csv
import pandas as pd
from investiny import historical_data, search_assets
from datetime import datetime, timedelta

# =============================
# PATHS
# =============================
REPO_ROOT  = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR   = os.path.join(REPO_ROOT, "data")
JSON_DIR   = os.path.join(DATA_DIR, "json")
CSV_OUTPUT = os.path.join(DATA_DIR, "all_tickers.csv")
OHLCV_FILE = os.path.join(DATA_DIR, "ohlcv.csv")
CACHE_FILE = os.path.join(REPO_ROOT, "symbol_cache.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)

# =============================
# WATCHLIST
# =============================
watchlist = [
    "EGX30", "AALR", "ABUK", "ACAMD", "ACAP", "ACGC", "ACTF", "ADCI", "ADPC", "AFDI",
    "AIDC", "AIFI", "AIH", "AJWA", "ALCN", "ALUM", "AMER", "AMES", "AMIA", "AMOC",
    "TYCN", "ARAB", "ARCC", "AREH", "ARVA", "ASCM", "ASPI", "ATLC", "ATQA", "AXPH",
    "BINV", "BIOC", "BONY", "BTFH", "CAED", "CCAP", "CCRS", "CEFM", "CERA", "CICH",
    "CIRA", "CLHO", "CNFN", "COPR", "COSG", "CPCI", "CRST", "CSAG", "DAPH", "DEIN",
    "DOMT", "DSCW", "DTPP", "EALR", "EBSC", "ECAP", "EDFM", "EEII", "EFIC", "EFID",
    "EFIH", "EGAL", "EGAS", "EGCH", "EGTS", "EHDR", "ELEC", "ELKA", "ELSH", "EMFD",
    "ENGC", "EPCO", "ETEL", "ETRS", "GBCO", "GDWA", "GGCC", "GIHD", "GPIM", "GRCA",
    "GTWL", "HBCO", "HELI", "ICFC", "ICID", "IDRE", "IEEC", "IFAP", "INEG", "INFI",
    "ISMA", "ISMQ", "ISPH", "JUFO", "KABO", "KRDI", "KZPC", "LCSW", "LUTS", "MAAL",
    "MASR", "MBSC", "MCQE", "MCRO", "MENA", "MEPA", "MFPC", "MICH", "MILS", "MIPH",
    "MOED", "MOSC", "MPCI", "MPCO", "MTIE", "NARE", "NCCW", "NHPS", "NIPH", "OBRI",
    "OCDI", "OCPH", "ODIN", "OFH", "OIH", "OLFI", "ORAS", "ORHD", "ORWE", "PHAR",
    "PHDC", "POUL", "PRCL", "PRDC", "PRMH", "RACC", "RAYA", "RMDA", "RREI", "RUBX",
    "SCEM", "SCFM", "SCTS", "SDTI", "SEIG", "SIPC", "SKPC", "SMFR", "SNFC", "SPIN",
    "SPMD", "SUGR", "SVCE", "SWDY", "TALM", "TANM", "TAQA", "TMGH", "UEFM", "UEGC",
    "UNIP", "UNIT", "WCDF", "WKOL", "VLMRA", "ZEOT", "ZMID",
]

# =============================
# CACHE
# =============================
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
else:
    cache = {}

# =============================
# DATE RANGE (full history)
# =============================
to_date      = datetime.now()
from_date    = to_date - timedelta(days=7000)
from_date_str = from_date.strftime("%m/%d/%Y")
to_date_str   = to_date.strftime("%m/%d/%Y")

# =============================
# LOAD EXISTING OHLCV FOR DEDUP
# =============================
if os.path.exists(OHLCV_FILE):
    existing_df = pd.read_csv(OHLCV_FILE)
    existing_df["Date"] = pd.to_datetime(existing_df["Date"], errors="coerce")
    existing_keys = set(existing_df["Symbol"].astype(str) + "_" + existing_df["Date"].astype(str))
else:
    existing_df   = pd.DataFrame()
    existing_keys = set()

# =============================
# FETCH LOOP
# =============================
all_rows     = []   # for all_tickers.csv  (full refresh)
new_ohlcv    = []   # for ohlcv.csv        (incremental)
failed       = []

for symbol in watchlist:
    print(f"Fetching {symbol}...")

    # ── Resolve investing.com ID ──────────────────────────────────────
    if symbol not in cache:
        try:
            asset_type = "Index" if symbol == "EGX30" else "Stock"
            results = search_assets(query=symbol, limit=1, type=asset_type, exchange="EGX")
            if results:
                cache[symbol] = int(results[0]["ticker"])
        except Exception as e:
            print(f"  ⚠️  Search failed: {e}")

    investing_id = cache.get(symbol)
    if not investing_id:
        print(f"  ❌ Not found in cache/search")
        failed.append(symbol)
        continue

    # ── Fetch ─────────────────────────────────────────────────────────
    try:
        data = historical_data(
            investing_id=investing_id,
            from_date=from_date_str,
            to_date=to_date_str,
        )

        # Save individual JSON
        with open(os.path.join(JSON_DIR, f"{symbol}_data.json"), "w") as f:
            json.dump(data, f)

        dates   = data.get("date",   data.get("Date",   []))
        opens   = data.get("open",   data.get("Open",   [None] * len(dates)))
        highs   = data.get("high",   data.get("High",   [None] * len(dates)))
        lows    = data.get("low",    data.get("Low",    [None] * len(dates)))
        closes  = data.get("close",  data.get("Close",  [None] * len(dates)))
        volumes = data.get("volume", data.get("Volume", [None] * len(dates)))

        for i, date in enumerate(dates):
            row = {
                "Symbol": symbol,
                "Date":   date,
                "Open":   opens[i]   if i < len(opens)   else None,
                "High":   highs[i]   if i < len(highs)   else None,
                "Low":    lows[i]    if i < len(lows)    else None,
                "Close":  closes[i]  if i < len(closes)  else None,
                "Volume": volumes[i] if i < len(volumes) else None,
            }
            all_rows.append(row)

            # Only add to ohlcv if it's a new row
            key = f"{symbol}_{pd.to_datetime(date)}"
            if key not in existing_keys:
                new_ohlcv.append(row)

        print(f"  ✅ {len(dates)} rows | {sum(1 for r in new_ohlcv if r['Symbol'] == symbol)} new")

    except Exception as e:
        print(f"  ❌ Data fetch failed: {e}")
        failed.append(symbol)

# =============================
# SAVE all_tickers.csv (full refresh)
# =============================
fieldnames = ["Symbol", "Date", "Open", "High", "Low", "Close", "Volume"]

if all_rows:
    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\n💾 all_tickers.csv → {len(all_rows)} rows")

# =============================
# SAVE ohlcv.csv (incremental)
# =============================
if new_ohlcv:
    new_df  = pd.DataFrame(new_ohlcv)
    final   = pd.concat([existing_df, new_df], ignore_index=True)
    final   = final.drop_duplicates(subset=["Symbol", "Date"])
    final.to_csv(OHLCV_FILE, index=False)
    print(f"💾 ohlcv.csv → {len(final)} total rows ({len(new_ohlcv)} new)")
else:
    print("⚠️  No new rows for ohlcv.csv")

# =============================
# SAVE cache + report
# =============================
with open(CACHE_FILE, "w") as f:
    json.dump(cache, f, indent=2)

if failed:
    print(f"\n❌ Failed ({len(failed)}): {', '.join(failed)}")

print("✅ Done!")
