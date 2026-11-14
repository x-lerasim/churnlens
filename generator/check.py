"""Проверка сгенерированных данных: доля ушедших, порог 200 ушедших, обучаемость сигнала.

python -m generator.check --data data/raw
Признаки здесь упрощённые (часть из 20) — только чтобы убедиться, что сигнал есть, но задача не тривиальна.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score


def load(d: Path):
    rd = lambda n, **k: pd.read_csv(d / f"{n}.csv.gz", **k)
    return dict(
        clients=rd("clients", parse_dates=["signup_date"]),
        churn=rd("churn_events", parse_dates=["churn_date"]),
        act=rd("activity_daily", parse_dates=["event_date"]),
        inv=rd("invoices", parse_dates=["period_start", "due_date", "paid_date"]),
        tick=rd("support_tickets", parse_dates=["created_at", "resolved_at"]),
        prod=rd("product_monthly", parse_dates=["month_start"]),
    )


def snapshot(t, S: pd.Timestamp, horizon_m=2):
    cl = t["clients"].merge(t["churn"], on="client_id", how="left")
    base = cl[(cl.signup_date < S) & (cl.churn_date.isna() | (cl.churn_date >= S))].copy()
    base["target"] = (base.churn_date < S + pd.DateOffset(months=horizon_m)).astype(int)
    base["tenure_m"] = (S - base.signup_date).dt.days / 30.4

    a = t["act"][(t["act"].event_date < S) & (t["act"].event_date >= S - pd.Timedelta(days=90))]
    a30 = a[a.event_date >= S - pd.Timedelta(days=30)]
    g30 = a30.groupby("client_id").agg(logins_30d=("logins", "sum"), bookings_30d=("bookings_created", "sum"),
                                       active_days_30d=("logins", lambda s: (s > 0).sum()))
    g90 = a.groupby("client_id").agg(logins_90d=("logins", "sum"), last=("event_date", "max"))
    ly = t["act"][(t["act"].event_date >= S - pd.DateOffset(years=1) - pd.Timedelta(days=30))
                  & (t["act"].event_date < S - pd.DateOffset(years=1))]
    gly = ly.groupby("client_id").agg(bookings_ly=("bookings_created", "sum"))

    i = t["inv"][(t["inv"].due_date < S) & (t["inv"].due_date >= S - pd.Timedelta(days=90))].copy()
    paid_eff = i.paid_date.where(i.paid_date < S, S).fillna(S)
    i["overdue"] = (paid_eff - i.due_date).dt.days.clip(lower=0)
    gi = i.groupby("client_id").agg(overdue_max_90d=("overdue", "max"), failed_90d=("failed_attempts", "sum"))

    k = t["tick"][(t["tick"].created_at < S) & (t["tick"].created_at >= S - pd.Timedelta(days=90))]
    gk = k.groupby("client_id").agg(tickets_90d=("ticket_id", "count"),
                                    critical_90d=("priority", lambda s: s.isin(["critical", "high"]).sum()),
                                    csat_90d=("csat", "mean"))
    pm = t["prod"][t["prod"].month_start == S - pd.DateOffset(months=1)].set_index("client_id")[
        ["modules_enabled", "integrations_active"]]

    df = base.set_index("client_id").join([g30, g90, gly, gi, gk, pm])
    df["days_since_last"] = (S - df.pop("last")).dt.days.fillna(90)
    df["logins_trend"] = df.logins_30d / (df.logins_90d / 3 + 1)
    df["season_yoy"] = df.bookings_30d / (df.bookings_ly + 1)
    df = df.fillna({c: 0 for c in ["logins_30d", "bookings_30d", "active_days_30d", "logins_90d",
                                   "overdue_max_90d", "failed_90d", "tickets_90d", "critical_90d"]})
    df["snapshot"] = S
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw")
    t = load(Path(ap.parse_args().data))

    start = t["act"].event_date.min().to_period("M").to_timestamp()
    end = t["act"].event_date.max()
    snaps = pd.date_range(start + pd.DateOffset(months=12),
                          end + pd.Timedelta(days=1) - pd.DateOffset(months=2), freq="MS")
    df = pd.concat([snapshot(t, S) for S in snaps])

    per = df.groupby("snapshot").agg(alive=("target", "size"), pos=("target", "sum"))
    per["rate_%"] = (per.pos / per.alive * 100).round(2)
    print(per.to_string())
    print(f"\nВсего ушедших: {len(t['churn'])}, причины:\n{t['churn'].churn_reason.value_counts().to_string()}")

    last2y = snaps[-24:]
    uniq = df[df.snapshot.isin(last2y) & (df.target == 1)].index.nunique()
    print(f"\nУникальных ушедших в последних 24 срезах: {uniq} (порог 200: {'OK' if uniq >= 200 else 'МАЛО'})")

    feats = ["tenure_m", "rooms_count", "logins_30d", "bookings_30d", "active_days_30d", "days_since_last",
             "logins_trend", "season_yoy", "overdue_max_90d", "failed_90d", "tickets_90d", "critical_90d",
             "csat_90d", "modules_enabled", "integrations_active"]
    X = df[feats].astype(float)
    for c in ["hotel_type", "region"]:
        X[c] = df[c].astype("category").cat.codes
    split = snaps[-6]                                    # последние 6 срезов — тест (out-of-time)
    tr, te = df.snapshot < split - pd.DateOffset(months=2), df.snapshot >= split
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=0)
    m.fit(X[tr], df.target[tr])
    p = m.predict_proba(X[te])[:, 1]
    y = df.target[te]
    print(f"\nOut-of-time: ROC-AUC={roc_auc_score(y, p):.3f}  PR-AUC={average_precision_score(y, p):.3f}  "
          f"доля класса={y.mean():.3f}")
    rule = (X.loc[te, "logins_trend"] < 0.7) | (X.loc[te, "overdue_max_90d"] > 10)
    print(f"Правило (спад входов или просрочка>10 дн): ROC-AUC={roc_auc_score(y, rule):.3f}")


if __name__ == "__main__":
    main()
