"""Run every query in sql/ with DuckDB and export the results to data/out/.

Views:
  ga4_real  = public GA4 sample (data/raw/ga4_events_slim.parquet, PUBLIC DATA, see src/extract_ga4.py)
  <name>    = every simulated table data/sim/<name>.parquet (SIMULATED, see src/simulate_tracking.py)
Files run in name order (01 ... 08, then 99_tests.sql). Inside a file a statement ends with ';' at the end of
a line. A statement preceded by '-- output: <name>' is exported to data/out/<name>.csv.
99_tests.sql uses DuckDB's error(): any failed assertion stops the run with a non-zero exit code.

    python src/run_sql.py            (all files)
    python src/run_sql.py 03 99      (only files starting with these prefixes)
"""
import os
import re
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM, OUT, SQL = ROOT / "data" / "sim", ROOT / "data" / "out", ROOT / "sql"
GA4 = ROOT / "data" / "raw" / "ga4_events_slim.parquet"


def main() -> None:
    os.chdir(ROOT)                                   # 99_tests.sql reads repository files with relative paths
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    if GA4.exists():
        con.execute(f"CREATE OR REPLACE VIEW ga4_real AS SELECT * FROM read_parquet('{GA4.as_posix()}')")
    con.execute(f"CREATE OR REPLACE VIEW holidays AS SELECT * FROM read_csv_auto('{(ROOT / 'data/reference/holidays_2026.csv').as_posix()}')")
    for f in sorted(SIM.glob("*.parquet")):
        con.execute(f"CREATE OR REPLACE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
    prefixes = sys.argv[1:]
    for sql_file in sorted(SQL.glob("*.sql")):
        if prefixes and not sql_file.name.startswith(tuple(prefixes)):
            continue
        if sql_file.name.startswith(("01", "02")) and not GA4.exists():
            print(f"skip {sql_file.name}: run src/extract_ga4.py first (its outputs are already in data/out)")
            continue
        t0 = time.time()
        for statement in re.split(r";\s*$", sql_file.read_text(encoding="utf-8"), flags=re.MULTILINE):
            if not re.search(r"^\s*[A-Za-z(]", statement, flags=re.MULTILINE):
                continue
            match = re.search(r"--\s*output:\s*(\w+)", statement)
            if match:
                df = con.execute(statement).df()
                for c in df.select_dtypes("float").columns:
                    df[c] = df[c].map(lambda v: float(f"{v:.8g}") if pd.notna(v) else v)
                df.to_csv(OUT / f"{match.group(1)}.csv", index=False)
                print(f"  {sql_file.name:32s} -> {match.group(1)}.csv ({len(df):,} rows)")
            else:
                con.execute(statement)
        print(f"{sql_file.name} done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
