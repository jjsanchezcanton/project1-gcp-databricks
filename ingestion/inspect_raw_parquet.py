"""
Quick inspection of a raw NYC TLC Parquet file.

Prints schema, row count, null distribution, basic stats, and a couple of
representative rows. Useful as a sanity check before designing the ingestor
and Bronze/Silver transformations.

Usage:
    python ingestion/inspect_raw_parquet.py data/raw/yellow_tripdata_2024-01.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


def inspect(path: Path) -> None:
    if not path.is_file():
        print(f"ERROR: file not found: {path}")
        sys.exit(1)

    print(f"=== File: {path} ===")
    print(f"Size on disk: {path.stat().st_size / (1024 * 1024):.2f} MB\n")

    # --- Parquet-level metadata (no full read needed) ---
    pq_file = pq.ParquetFile(path)
    print(f"Parquet row groups: {pq_file.num_row_groups}")
    print(f"Total rows (metadata): {pq_file.metadata.num_rows:,}")
    print(f"Compression of first column: {pq_file.metadata.row_group(0).column(0).compression}\n")

    # --- Schema as Arrow sees it ---
    print("=== Arrow schema ===")
    print(pq_file.schema_arrow)
    print()

    # --- Load into pandas for stats ---
    df = pd.read_parquet(path)
    print(f"=== Pandas-loaded shape ===")
    print(f"Rows: {len(df):,}  Columns: {len(df.columns)}\n")

    print("=== Dtypes ===")
    print(df.dtypes.to_string())
    print()

    print("=== Null counts per column ===")
    nulls = df.isnull().sum()
    nulls_pct = (nulls / len(df) * 100).round(2)
    null_summary = pd.DataFrame({"null_count": nulls, "null_pct": nulls_pct})
    print(null_summary[null_summary["null_count"] > 0].to_string()
          if (nulls > 0).any() else "(no nulls)")
    print()

    print("=== Numeric stats (first 8 numeric columns) ===")
    numeric_cols = df.select_dtypes(include="number").columns[:8]
    print(df[numeric_cols].describe().round(2).to_string())
    print()

    print("=== Date range ===")
    for col in df.columns:
        if "datetime" in str(df[col].dtype) or "date" in str(df[col].dtype).lower():
            print(f"  {col}: {df[col].min()} → {df[col].max()}")
    print()

    print("=== First 3 rows (transposed for readability) ===")
    print(df.head(3).T.to_string())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python inspect_raw_parquet.py <path-to-parquet>")
        sys.exit(2)
    inspect(Path(sys.argv[1]))
