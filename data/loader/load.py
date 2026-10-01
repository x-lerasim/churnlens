import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from data.ch import get_client

ROOT = Path(__file__).resolve().parents[2]
DDL_DIR = ROOT / "sql" / "raw"
DATA_DIR = ROOT / "data" / "output"
TABLES = ["clients", "subscriptions", "modules", "activity_daily", "bookings", "support_tickets", "payments"]
BATCH_ROWS = 500_000


def apply_ddl(client, recreate):
    if recreate:
        client.command("DROP DATABASE IF EXISTS raw")
    for f in sorted(DDL_DIR.glob("*.sql")):
        client.command(f.read_text())
        print(f"ddl: {f.name}")


def load_table(client, table, data_dir):
    path = data_dir / f"{table}.parquet"
    client.command(f"TRUNCATE TABLE IF EXISTS raw.{table}")
    pf = pq.ParquetFile(path)
    total = 0
    for batch in pf.iter_batches(batch_size=BATCH_ROWS):
        client.insert_arrow(f"raw.{table}", pa.Table.from_batches([batch]))
        total += batch.num_rows
    print(f"load: {table:<16} {total:>12,}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--data", default=str(DATA_DIR))
    args = ap.parse_args()
    client = get_client()
    apply_ddl(client, args.recreate)
    for t in TABLES:
        load_table(client, t, Path(args.data))


if __name__ == "__main__":
    main()
