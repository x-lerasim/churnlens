"""CLI: python -m generator --out data/raw [--clients 5000] [--seed 42] [--format csv|parquet]"""
import argparse
import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from .config import GenConfig
from .simulate import Simulator


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--clients", type=int, default=GenConfig.n_clients)
    ap.add_argument("--seed", type=int, default=GenConfig.seed)
    ap.add_argument("--format", choices=["csv", "parquet"], default="csv")
    a = ap.parse_args()

    cfg = replace(GenConfig(), n_clients=a.clients, seed=a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    t = time.time()
    tables = Simulator(cfg).run()
    for name, df in tables.items():
        if a.format == "parquet":
            df.to_parquet(out / f"{name}.parquet", index=False)
        else:
            df.to_csv(out / f"{name}.csv.gz", index=False, compression="gzip")
        print(f"{name:16s} {len(df):>10,d} строк")

    meta = {"config": asdict(cfg), "rows": {k: len(v) for k, v in tables.items()},
            "seconds": round(time.time() - t, 1)}
    (out / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
    print(f"готово за {meta['seconds']} с → {out}")


if __name__ == "__main__":
    main()
