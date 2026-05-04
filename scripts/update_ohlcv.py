import json
import os
import csv
import pandas as pd
from investiny import historical_data
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
INVESTING_IDS = {
    {"COMI": 12865, "ENGC": 12914, "ABUK": 12964, "HRHO": 12875, "EGX30": 12860, "AALR": 40558, "ACAMD": 1115767,
     "ACAP": 1203006, "ACGC": 12861, "ACTF": 1218756, "ADCI": 40559, "ADPC": 40560, "AFDI": 12894, "AIDC": 1233877,
     "AIFI": 40565, "AIH": 40561, "AJWA": 12862, "ALCN": 40563, "ALUM": 40566, "AMER": 40567, "AMES": 40568,
     "AMIA": 40569, "AMOC": 12971, "TYCN": 40570, "ARAB": 960753, "ARCC": 950023, "AREH": 12897, "ARVA": 40573,
     "ASCM": 12898, "ASPI": 12884, "ATLC": 1057138, "ATQA": 40574, "AXPH": 12974, "BINV": 1073052, "BIOC": 12975,
     "BONY": 1233358, "BTFH": 40576, "CAED": 40577, "CCAP": 12864, "CCRS": 12900, "CEFM": 12901, "CERA": 40579,
     "CICH": 1075451, "CIRA": 40580, "CLHO": 985148, "CNFN": 1121784, "COPR": 12879, "COSG": 12903, "CPCI": 12981,
     "CRST": 12866, "CSAG": 12904, "DAPH": 12905, "DEIN": 12983, "DOMT": 969108, "DSCW": 40581, "DTPP": 12908,
     "EALR": 40582, "EBSC": 40584, "ECAP": 12909, "EDFM": 12987, "EEII": 40586, "EFIC": 12910, "EFID": 992622,
     "EFIH": 1178529, "EGAL": 40587, "EGAS": 12989, "EGCH": 12992, "EGTS": 12867, "EHDR": 12911, "ELEC": 12869,
     "ELKA": 12870, "ELSH": 12913, "EMFD": 960752, "EPCO": 12872, "ETEL": 12874, "ETRS": 12915, "GBCO": 12899,
     "GDWA": 1178527, "GGCC": 12916, "GIHD": 12917, "GPIM": 40590, "GRCA": 12920, "GTWL": 40599, "HBCO": 1224792,
     "HELI": 12922, "ICFC": 1052616, "ICID": 12923, "IDRE": 40602, "IEEC": 950024, "IFAP": 12925, "INEG": 1052608,
     "INFI": 40603, "ISMA": 12927, "ISMQ": 1174541, "ISPH": 1056341, "JUFO": 40604, "KABO": 12928, "KRDI": 1184823,
     "KZPC": 13008, "LCSW": 12929, "LUTS": 1203038, "MAAL": 1171365, "MASR": 12932, "MBSC": 12965, "MCQE": 12966,
     "MCRO": 1185538, "MENA": 12930, "MEPA": 40609, "MFPC": 997882, "MICH": 12931, "MILS": 12972, "MIPH": 40610,
     "MOED": 1052619, "MOSC": 12933, "MPCI": 40612, "MPCO": 12934, "MTIE": 1010530, "NARE": 40622, "NCCW": 12937,
     "NHPS": 40616, "NIPH": 12980, "OBRI": 40618, "OCDI": 12880, "OCPH": 40619, "ODIN": 12892, "OFH": 1170419,
     "OIH": 40621, "OLFI": 994418, "ORAS": 950025, "ORHD": 40620, "ORWE": 12943, "PHAR": 12990, "PHDC": 12883,
     "POUL": 12945, "PRCL": 12946, "PRDC": 1178528, "PRMH": 12994, "RACC": 1036884, "RAYA": 12948, "RMDA": 1156268,
     "RREI": 40623, "RUBX": 12950, "SCEM": 12998, "SCFM": 12999, "SCTS": 40625, "SDTI": 40626, "SEIG": 13000, "SIPC": 992995,
     "SKPC": 12886, "SMFR": 12953, "SNFC": 12954, "SPIN": 12955, "SPMD": 1129365, "SUGR": 12956, "SVCE": 12887, "SWDY": 12888,
     "TALM": 1172876, "TANM": 1174905, "TAQA": 1204783, "TMGH": 12889, "UEFM": 13005, "UEGC": 12890, "UNIP": 12959,
     "UNIT": 12960, "WCDF": 13007, "WKOL": 40638, "VLMRA": 1178525, "ZEOT": 12961, "ZMID": 12962}
    }
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
    
    # handle both old schema ("datetime") and new schema ("Date")
    if "datetime" in existing_df.columns and "Date" not in existing_df.columns:
        existing_df.rename(columns={"datetime": "Date"}, inplace=True)
    
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
    investing_id = INVESTING_IDS.get(symbol)
    if not investing_id:
        print(f"  ❌ No investing_id for {symbol}")
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
