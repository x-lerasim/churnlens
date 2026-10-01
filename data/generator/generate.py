import argparse
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from data.generator import config as C

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

D = "datetime64[D]"
P_START = np.datetime64(C.PERIOD_START, "D")
P_END = np.datetime64(C.PERIOD_END, "D")
H_START = np.datetime64(C.HISTORY_START, "D")
N_DAYS = int((P_END - P_START).astype(int)) + 1
DATES = P_START + np.arange(N_DAYS)
MONTH_STARTS = np.arange(P_START.astype("datetime64[M]"), (P_END + 1).astype("datetime64[M]")).astype(D)
N_MONTHS = len(MONTH_STARTS)

SCHEMAS = {
    "clients": pa.schema([
        ("client_id", pa.uint32()), ("property_name", pa.string()), ("property_type", pa.string()),
        ("region", pa.string()), ("rooms_count", pa.uint16()), ("signup_date", pa.date32()),
        ("acquisition_channel", pa.string()), ("has_account_manager", pa.uint8()),
    ]),
    "subscriptions": pa.schema([
        ("subscription_id", pa.uint32()), ("client_id", pa.uint32()), ("tariff", pa.string()),
        ("billing_period", pa.string()), ("price_per_room", pa.decimal128(10, 2)), ("start_date", pa.date32()),
        ("end_date", pa.date32()), ("status", pa.string()), ("cancel_reason", pa.string()),
    ]),
    "modules": pa.schema([
        ("client_id", pa.uint32()), ("module_code", pa.string()), ("enabled_date", pa.date32()),
        ("disabled_date", pa.date32()),
    ]),
    "activity_daily": pa.schema([
        ("client_id", pa.uint32()), ("activity_date", pa.date32()), ("logins", pa.uint16()),
        ("active_users", pa.uint8()), ("chessboard_actions", pa.uint32()), ("rate_updates", pa.uint32()),
        ("cm_sync_errors", pa.uint16()),
    ]),
    "bookings": pa.schema([
        ("client_id", pa.uint32()), ("booking_date", pa.date32()), ("source", pa.string()),
        ("bookings_cnt", pa.uint16()), ("room_nights", pa.uint32()), ("revenue", pa.decimal128(14, 2)),
        ("cancellations", pa.uint16()),
    ]),
    "support_tickets": pa.schema([
        ("ticket_id", pa.uint32()), ("client_id", pa.uint32()), ("created_at", pa.timestamp("s")),
        ("closed_at", pa.timestamp("s")), ("category", pa.string()), ("priority", pa.string()),
        ("channel", pa.string()), ("csat", pa.uint8()),
    ]),
    "payments": pa.schema([
        ("invoice_id", pa.uint32()), ("client_id", pa.uint32()), ("invoice_date", pa.date32()),
        ("due_date", pa.date32()), ("amount", pa.decimal128(12, 2)), ("paid_date", pa.date32()),
        ("paid_amount", pa.decimal128(12, 2)), ("payment_method", pa.string()),
    ]),
}


def pick(rng, mapping, size=None, key="w"):
    keys = list(mapping)
    w = np.array([mapping[k][key] if isinstance(mapping[k], dict) else mapping[k] for k in keys], dtype=float)
    return rng.choice(keys, size=size, p=w / w.sum())


def season_curves():
    mid = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349], dtype=float)
    doy = (DATES - DATES.astype("datetime64[Y]")).astype(int).astype(float)
    return {k: np.interp(doy, mid, np.array(v), period=365) for k, v in C.SEASON_MONTHLY.items()}


SEASON = season_curves()
WEEKDAY = np.array(C.WEEKDAY_FACTOR)[(DATES.astype(int) + 3) % 7]


def build_clients(rng):
    n = C.N_CLIENTS
    types = pick(rng, C.PROPERTY_TYPES, n, key="share")
    region_names = list(C.REGIONS)
    regions = np.empty(n, dtype=object)
    for t in C.PROPERTY_TYPES:
        idx = np.where(types == t)[0]
        w = []
        for r in region_names:
            kind = C.REGIONS[r]["kind"]
            mult = 1.0
            if C.PROPERTY_TYPES[t]["nature"]:
                mult = 2.5 if kind in ("nature", "sea") else 0.3
            elif t in ("hotel", "mini_hotel", "hostel") and kind == "city":
                mult = 1.3
            w.append(C.REGIONS[r]["w"] * mult)
        w = np.array(w)
        regions[idx] = rng.choice(region_names, size=len(idx), p=w / w.sum())

    rooms = np.zeros(n, dtype=int)
    for t, p in C.PROPERTY_TYPES.items():
        idx = types == t
        med, sigma, lo, hi = p["rooms"]
        rooms[idx] = np.clip(np.round(rng.lognormal(np.log(med), sigma, idx.sum())), lo, hi)

    is_new = rng.random(n) < C.SHARE_NEW_IN_PERIOD
    max_tenure = int((P_START - H_START).astype(int))
    tenure = np.clip(rng.exponential(C.EXISTING_TENURE_MEAN_DAYS, n), 1, max_tenure).astype(int)
    signup = P_START - tenure
    new_off = rng.integers(0, N_DAYS - 30, n)
    signup = np.where(is_new, P_START + new_off, signup).astype(D)

    acq = pick(rng, C.ACQUISITION, n)
    am_prob = np.where(rooms >= 40, 0.8, np.where(rooms >= 15, 0.25, 0.05))
    has_am = (rng.random(n) < am_prob).astype(int)

    labels = np.array([C.PROPERTY_TYPES[t]["label"] for t in types], dtype=object)
    words = rng.choice(C.NAME_WORDS, n)
    names = np.array([f"{l} «{w}»" for l, w in zip(labels, words)], dtype=object)

    season_kind = np.where(
        np.array([C.PROPERTY_TYPES[t]["nature"] for t in types]), "nature",
        np.where(np.array([C.REGIONS[r]["kind"] for r in regions]) == "sea", "sea", "city"),
    )

    return {
        "client_id": np.arange(C.FIRST_CLIENT_ID, C.FIRST_CLIENT_ID + n),
        "property_name": names, "property_type": types, "region": regions, "rooms_count": rooms,
        "signup_date": signup, "acquisition_channel": acq, "has_account_manager": has_am,
        "season_kind": season_kind,
    }


def initial_modules(rng, cl):
    n = C.N_CLIENTS
    rooms = cl["rooms_count"]
    owned = {}
    for code, m in C.MODULES.items():
        p = np.full(n, m["p"])
        if code == "rms":
            p = np.where(rooms >= 30, p * 2.5, p * 0.5)
        if code == "price_monitoring":
            p = np.where(rooms >= 20, p * 1.5, p)
        if code == "channel_manager":
            p = np.where(cl["property_type"] == "apartments", 0.95, p)
        has = rng.random(n) < np.clip(p, 0, 1)
        if "requires" in m:
            has &= owned[m["requires"]]
        owned[code] = has
    return owned


def assign_tariffs(rng, cl, owned):
    n = C.N_CLIENTS
    rooms = cl["rooms_count"]
    probs = np.where(rooms[:, None] < 10, [0.55, 0.35, 0.10], np.where(rooms[:, None] <= 40, [0.25, 0.50, 0.25], [0.10, 0.40, 0.50]))
    probs = np.where(owned["rms"][:, None], [0.0, 0.3, 0.7], probs)
    u = rng.random(n)[:, None]
    tariff_idx = (u > np.cumsum(probs, axis=1)).sum(axis=1)
    billing = pick(rng, C.BILLING, n)
    return tariff_idx, billing


def static_risk(rng, cl, owned, tariff_idx, billing):
    n_mod = sum(owned[k].astype(int) for k in owned)
    rooms = cl["rooms_count"]
    r = np.array([C.PROPERTY_TYPES[t]["risk"] for t in cl["property_type"]])
    r += np.array([C.ACQUISITION[a]["risk"] for a in cl["acquisition_channel"]])
    r += C.ACCOUNT_MANAGER_RISK * cl["has_account_manager"]
    r += np.where(rooms < 5, 0.3, np.where(rooms > 50, -0.3, 0.0))
    r += C.MODULE_RISK_PER_EXTRA * (n_mod - 2)
    r += np.array([C.TARIFFS[C.TARIFF_ORDER[i]]["risk"] for i in tariff_idx])
    r += np.array([C.BILLING[b]["risk"] for b in billing])
    r += rng.normal(0, C.LATENT_RISK_SIGMA, len(r))
    return r


def simulate_churn(rng, cl, r_static):
    n = C.N_CLIENTS
    signup = cl["signup_date"]
    month_end = np.append(MONTH_STARTS[1:], P_END + 1)
    exposed = (signup[:, None] < MONTH_STARTS[None, :])
    tenure_m = (MONTH_STARTS[None, :] - signup[:, None]).astype(int) / 30.44
    tr = np.zeros_like(tenure_m)
    for limit, val in reversed(C.TENURE_RISK):
        tr = np.where(tenure_m < limit, val, tr)
    months = MONTH_STARTS.astype("datetime64[M]").astype(int) % 12 + 1
    autumn = np.isin(months, [10, 11])[None, :] & (cl["season_kind"] != "city")[:, None]
    logit = r_static[:, None] + tr + C.SEASONAL_AUTUMN_RISK * autumn
    raw = np.exp(logit)
    u = rng.random((n, N_MONTHS))
    target_m = 1 - (1 - C.TARGET_ANNUAL_CHURN) ** (1 / 12)
    base = target_m / raw[exposed].mean()
    for _ in range(8):
        hit = exposed & (u < np.clip(base * raw, 0, 0.3))
        any_hit = hit.any(axis=1)
        first = np.where(any_hit, hit.argmax(axis=1), N_MONTHS)
        exp_months = (exposed & (np.arange(N_MONTHS)[None, :] <= first[:, None])).sum()
        realized = any_hit.sum() / exp_months
        base *= target_m / realized
    hit = exposed & (u < np.clip(base * raw, 0, 0.3))
    churned = hit.any(axis=1)
    first = hit.argmax(axis=1)
    m_start = MONTH_STARTS[first]
    m_len = (month_end[first] - m_start).astype(int)
    churn_date = m_start + (rng.random(n) * m_len).astype(int)
    churn_date = np.maximum(churn_date, signup + 20)
    churn_date = np.where(churned & (churn_date <= P_END), churn_date, np.datetime64("NaT"))
    return churn_date.astype(D)


def build_profiles(rng, cl, churn_date):
    n = C.N_CLIENTS
    churned = ~np.isnat(churn_date)
    kind = np.where(churned, pick(rng, C.CHURN_KINDS, n), "")
    window = np.zeros(n, dtype=int)
    depth = np.ones(n)
    reason = np.empty(n, dtype=object)
    for k, p in C.CHURN_KINDS.items():
        idx = kind == k
        window[idx] = rng.integers(p["window"][0], p["window"][1] + 1, idx.sum())
        depth[idx] = rng.uniform(*p["depth"], idx.sum())
        reason[idx] = pick(rng, {r: w for r, w in C.CANCEL_REASONS[k].items()}, idx.sum(), key=None)
    gradual = kind == "gradual"
    dip = ~churned & (rng.random(n) < C.DIP_PROB)
    start_off = np.maximum((cl["signup_date"] - P_START).astype(int), 0)
    dip_len = rng.integers(C.DIP_DAYS[0], C.DIP_DAYS[1] + 1, n)
    dip_start = start_off + (rng.random(n) * np.maximum(N_DAYS - start_off - dip_len, 1)).astype(int)
    users = np.maximum(1, np.round(cl["rooms_count"] ** 0.45 * rng.lognormal(0, 0.3, n))).astype(int)
    return {
        "churned": churned, "kind": kind, "window": window, "depth": depth, "reason": reason,
        "late_pay": gradual & (rng.random(n) < C.GRADUAL_LATE_PAY_PROB),
        "module_drop": gradual & (rng.random(n) < C.GRADUAL_MODULE_DROP_PROB),
        "downgrade": gradual & (rng.random(n) < C.GRADUAL_DOWNGRADE_PROB),
        "spike": np.where(gradual, rng.uniform(*C.GRADUAL_TICKET_SPIKE, n), 1.0),
        "cancel_ticket": np.where(gradual, rng.random(n) < C.CANCELLATION_TICKET_PROB, rng.random(n) < 0.3) & churned,
        "dip": dip, "dip_start": dip_start, "dip_len": dip_len,
        "dip_depth": rng.uniform(*C.DIP_DEPTH, n), "dip_spike": rng.uniform(*C.DIP_TICKET_SPIKE, n),
        "dip_late": dip & (rng.random(n) < 0.5),
        "habitual_late": rng.random(n) < C.HABITUAL_LATE_PAYER_PROB,
        "upgrade": ~churned & (rng.random(n) < C.UPGRADE_PROB),
        "random_drop": ~churned & (rng.random(n) < C.RANDOM_MODULE_DROP_PROB),
        "upsell": rng.random(n) < C.MODULE_UPSELL_PROB,
        "level": rng.lognormal(0, 0.5, n), "users": users, "drift": rng.normal(0, 0.15, n),
        "occ_noise": rng.lognormal(0, 0.25, n), "prone": rng.gamma(2.0, 0.5, n), "err_prone": rng.gamma(1.5, 0.6, n),
        "pay_method": pick(rng, C.PAYMENT_METHODS, n, key=None),
        "shares": rng.dirichlet([s["alpha"] for s in C.BOOKING_SOURCES.values()], n),
    }


class Sink:
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.buf = {t: [] for t in SCHEMAS}
        self.writers = {}
        self.counts = {t: 0 for t in SCHEMAS}

    def add(self, table, **cols):
        self.buf[table].append(cols)

    def flush(self):
        for table, parts in self.buf.items():
            if not parts:
                continue
            schema = SCHEMAS[table]
            arrays = []
            for field in schema:
                vals = [p[field.name] for p in parts]
                arrays.append(to_arrow(vals, field.type))
            tbl = pa.Table.from_arrays(arrays, schema=schema)
            if table not in self.writers:
                self.writers[table] = pq.ParquetWriter(self.out_dir / f"{table}.parquet", schema)
            self.writers[table].write_table(tbl)
            self.counts[table] += tbl.num_rows
            self.buf[table] = []

    def close(self):
        self.flush()
        for w in self.writers.values():
            w.close()


def to_arrow(vals, typ):
    flat = []
    for v in vals:
        if isinstance(v, np.ndarray):
            flat.append(v)
        elif isinstance(v, list):
            flat.append(np.array(v, dtype=object))
        else:
            flat.append(np.array([v], dtype=object if isinstance(v, str) or v is None else None))
    arr = np.concatenate(flat) if flat else np.array([])
    if pa.types.is_decimal(typ):
        return pa.array(np.round(arr.astype(float), 2)).cast(typ, safe=False)
    if pa.types.is_date32(typ):
        return pa.array(arr.astype(D), from_pandas=True, type=pa.date32())
    if pa.types.is_timestamp(typ):
        return pa.array(arr.astype("datetime64[s]"), from_pandas=True, type=typ)
    if pa.types.is_string(typ):
        if arr.dtype.kind == "U":
            return pa.array(arr.tolist(), type=typ)
        return pa.array([None if v is None or v == "" else str(v) for v in arr], type=typ)
    if arr.dtype == object:
        return pa.array([None if v is None else int(v) for v in arr], type=typ)
    return pa.array(arr, type=typ)


def subscription_rows(rng, i, cl, pr, tariff_idx, billing, churn_date, sink, ids):
    cid = cl["client_id"][i]
    signup = cl["signup_date"][i]
    t0 = tariff_idx[i]
    changes = []
    if pr["upgrade"][i] and t0 < 2:
        lo = max(signup, P_START) + 30
        if lo < P_END:
            changes.append((lo + int(rng.integers(0, max(int((P_END - lo).astype(int)), 1))), t0 + 1))
    if pr["downgrade"][i] and t0 > 0:
        d = churn_date[i] - pr["window"][i]
        if d > signup + 30:
            changes.append((d, t0 - 1))
    periods = [(signup, t0)] + sorted(changes)
    for k, (start, t) in enumerate(periods):
        last = k == len(periods) - 1
        if last:
            end = churn_date[i] if pr["churned"][i] else np.datetime64("NaT")
            status = "cancelled" if pr["churned"][i] else "active"
            reason = pr["reason"][i] if pr["churned"][i] else None
        else:
            end, status, reason = periods[k + 1][0], "changed", None
        ids["sub"] += 1
        sink.add("subscriptions", subscription_id=ids["sub"], client_id=cid, tariff=C.TARIFF_ORDER[t],
                 billing_period=billing[i], price_per_room=C.TARIFFS[C.TARIFF_ORDER[t]]["price"],
                 start_date=start, end_date=end, status=status, cancel_reason=reason)
    return periods


def module_rows(rng, i, cl, pr, owned, churn_date, sink):
    cid = cl["client_id"][i]
    signup = cl["signup_date"][i]
    churned = pr["churned"][i]
    life_end = churn_date[i] if churned else P_END
    mods = {}
    for code in C.MODULES:
        if owned[code][i]:
            mods[code] = [signup + (0 if code == "pms" else int(rng.integers(0, 21))), np.datetime64("NaT")]
    span_lo = max(signup, P_START) + 30
    if pr["upsell"][i] and span_lo < life_end - 30:
        free = [c for c in C.MODULES if c not in mods and C.MODULES[c].get("requires", "pms") in mods]
        if free:
            c = rng.choice(free)
            mods[c] = [span_lo + int(rng.integers(0, int((life_end - 30 - span_lo).astype(int)))), np.datetime64("NaT")]
    optional = [c for c in mods if c != "pms"]
    if optional and (pr["module_drop"][i] or pr["random_drop"][i]):
        k = min(len(optional), int(rng.integers(1, 3)) if pr["module_drop"][i] else 1)
        for c in rng.choice(optional, k, replace=False):
            if pr["module_drop"][i]:
                d = churn_date[i] - int(rng.integers(5, max(pr["window"][i], 6)))
            else:
                d = span_lo + int(rng.integers(0, max(int((P_END - span_lo).astype(int)), 1)))
            if d > mods[c][0] + 7:
                mods[c][1] = d
    if churned:
        for c in mods:
            if np.isnat(mods[c][1]) or mods[c][1] > churn_date[i]:
                mods[c][1] = churn_date[i]
    for c, (en, dis) in mods.items():
        sink.add("modules", client_id=cid, module_code=c, enabled_date=en, disabled_date=dis)
    return mods


def module_active(mods, code, days):
    if code not in mods:
        return np.zeros(len(days), dtype=bool)
    en, dis = mods[code]
    act = days >= en
    if not np.isnat(dis):
        act &= days < dis
    return act


def daily_factors(i, cl, pr, churn_date, days, off):
    p = pr
    kind = cl["season_kind"][i]
    season = SEASON[kind][off]
    act_season = 1 + C.ACTIVITY_SEASON_DAMP * (season - 1)
    since = (days - cl["signup_date"][i]).astype(int)
    onboard = np.clip(0.5 + 0.5 * since / 30, 0.5, 1.0)
    trend = 1 + p["drift"][i] * off / N_DAYS
    progress = np.zeros(len(days))
    if p["churned"][i] and p["window"][i] > 0:
        to_churn = (churn_date[i] - days).astype(int)
        progress = np.clip(1 - to_churn / p["window"][i], 0, 1)
    decay = 1 - (1 - p["depth"][i]) * progress ** 1.3
    dip = np.ones(len(days))
    in_dip = np.zeros(len(days), dtype=bool)
    if p["dip"][i]:
        t = (off - p["dip_start"][i]) / p["dip_len"][i]
        in_dip = (t >= 0) & (t <= 1)
        dip = np.where(in_dip, 1 - (1 - p["dip_depth"][i]) * np.sin(np.pi * np.clip(t, 0, 1)), 1.0)
    return season, act_season, onboard, trend, progress, decay, dip, in_dip, since


def gen_client(rng, i, cl, pr, owned, tariff_idx, billing, churn_date, sink, ids):
    cid = cl["client_id"][i]
    t = cl["property_type"][i]
    tp = C.PROPERTY_TYPES[t]
    rooms = cl["rooms_count"][i]
    periods = subscription_rows(rng, i, cl, pr, tariff_idx, billing, churn_date, sink, ids)
    mods = module_rows(rng, i, cl, pr, owned, churn_date, sink)

    first = max(cl["signup_date"][i], P_START)
    last = churn_date[i] - 1 if pr["churned"][i] else P_END
    if first > last:
        return
    off = np.arange(int((first - P_START).astype(int)), int((last - P_START).astype(int)) + 1)
    days = DATES[off]
    n = len(days)
    season, act_season, onboard, trend, progress, decay, dip, in_dip, since = daily_factors(i, cl, pr, churn_date, days, off)
    week_noise = rng.lognormal(0, 0.15, N_DAYS // 7 + 1)[off // 7]
    cm = module_active(mods, "channel_manager", days)
    be = module_active(mods, "booking_engine", days)
    rms = module_active(mods, "rms", days)

    book_decay = 1 - (1 - decay) * 0.7
    book_dip = 1 - (1 - dip) * 0.5
    total_b = rooms * tp["occ"] * season / tp["los"] * pr["occ_noise"][i] * book_decay * book_dip * np.clip(onboard * 1.2, 0, 1)
    avail = np.ones((n, len(C.BOOKING_SOURCES)))
    srcs = list(C.BOOKING_SOURCES)
    for j, s in enumerate(srcs):
        if s == "direct_widget":
            avail[:, j] = be
        elif s.startswith("ota"):
            avail[:, j] = np.where(cm, 1.0, 0.25)
    lam = total_b[:, None] * pr["shares"][i][None, :] * avail
    cnt = rng.poisson(lam)
    rn = cnt + rng.poisson(cnt * (tp["los"] - 1))
    price = tp["adr"] * C.REGIONS[cl["region"][i]]["price"] * (1 + 0.35 * (season - 1))
    revenue = rn * price[:, None] * rng.lognormal(0, 0.08, cnt.shape)
    canc_p = np.array([C.BOOKING_SOURCES[s]["cancel"] for s in srcs])
    canc = rng.binomial(cnt, canc_p[None, :])
    nz = cnt > 0
    di, sj = np.nonzero(nz)
    sink.add("bookings", client_id=np.full(len(di), cid), booking_date=days[di], source=np.array(srcs, dtype=object)[sj],
             bookings_cnt=np.minimum(cnt[nz], 65535), room_nights=rn[nz], revenue=revenue[nz], cancellations=canc[nz])
    bookings_day = cnt.sum(axis=1)

    act_f = act_season * WEEKDAY[off] * decay * dip * onboard * trend * week_noise
    users = pr["users"][i]
    logins = rng.poisson(users * 2.2 * pr["level"][i] * act_f * rng.lognormal(0, 0.3, n))
    chess = rng.poisson(logins * 4 + bookings_day * 2 * decay)
    rate_mu = pr["level"][i] * np.sqrt(rooms) * np.where(cm, 2.0, 0.3) * np.where(rms, 3.0, 1.0) * act_f
    rates = rng.poisson(rate_mu)
    err_extra = 0.6 * progress if pr["reason"][i] in ("switched_competitor", "functionality") else 0.0
    errs = rng.poisson(cm * (0.15 * pr["err_prone"][i] + err_extra))
    p_user = np.clip(0.55 * np.minimum(act_f, 1.5) + 0.1, 0.05, 0.95)
    au = np.where(logins > 0, np.clip(rng.binomial(users, p_user), 1, np.minimum(logins, 255)), 0)
    keep = (logins > 0) | (chess > 0) | (rates > 0)
    sink.add("activity_daily", client_id=np.full(keep.sum(), cid), activity_date=days[keep],
             logins=np.minimum(logins[keep], 65535), active_users=au[keep], chessboard_actions=chess[keep],
             rate_updates=rates[keep], cm_sync_errors=np.minimum(errs[keep], 65535))

    risk_mask = (progress > 0) | in_dip
    gen_tickets(rng, i, cl, pr, mods, churn_date, days, off, since, act_season, progress, in_dip, risk_mask, cm, sink, ids)
    gen_payments(rng, i, cl, pr, billing, periods, churn_date, sink, ids)


def gen_tickets(rng, i, cl, pr, mods, churn_date, days, off, since, act_season, progress, in_dip, risk_mask, cm, sink, ids):
    cid = cl["client_id"][i]
    n_mod = len(mods)
    base = (0.5 + 0.12 * n_mod) * cl["rooms_count"][i] ** 0.25 / 30 * pr["prone"][i]
    mult = np.sqrt(act_season) * np.where(since < 60, 3.0, 1.0)
    mult = mult * (1 + (pr["spike"][i] - 1) * progress)
    mult = mult * np.where(in_dip, pr["dip_spike"][i], 1.0)
    cnt = rng.poisson(base * mult)
    idx = np.repeat(np.arange(len(days)), cnt)
    phases = np.where(since[idx] < 60, "onboarding", np.where(risk_mask[idx], "risk", "normal"))
    cats = np.empty(len(idx), dtype=object)
    prio = np.empty(len(idx), dtype=object)
    for ph in ("normal", "onboarding", "risk"):
        m = phases == ph
        if m.any():
            cats[m] = pick(rng, C.TICKET_CATEGORIES[ph], m.sum(), key=None)
            pk = "risk" if ph == "risk" else "normal"
            prio[m] = rng.choice(["low", "normal", "high"], m.sum(), p=C.TICKET_PRIORITY[pk])
    cats = np.where((cats == "cm_sync") & ~cm[idx], "other", cats)
    tdays = days[idx]
    if pr["cancel_ticket"][i]:
        d = churn_date[i] - int(rng.integers(3, 22))
        if d >= days[0]:
            tdays = np.append(tdays, d)
            cats = np.append(cats, "cancellation")
            prio = np.append(prio, "high")
            phases = np.append(phases, "risk")
    k = len(tdays)
    if k == 0:
        return
    hours = rng.choice(np.arange(24), k, p=hour_weights())
    created = tdays.astype("datetime64[s]") + (hours * 3600 + rng.integers(0, 3600, k)).astype("timedelta64[s]")
    res_h = rng.lognormal(np.log(5), 1.1, k) * np.where(prio == "high", 0.5, 1.0)
    closed = created + (res_h * 3600).astype("timedelta64[s]")
    horizon = (P_END + 1).astype("datetime64[s]")
    open_mask = (closed >= horizon) | (rng.random(k) < 0.02)
    closed = np.where(open_mask, np.datetime64("NaT"), closed)
    rated = ~open_mask & (rng.random(k) < 0.55)
    csat = np.full(k, None, dtype=object)
    for ph, key in (("risk", "risk"), ("normal", "normal"), ("onboarding", "normal")):
        m = rated & (phases == ph)
        if m.any():
            csat[m] = rng.choice([1, 2, 3, 4, 5], m.sum(), p=C.CSAT[key])
    chan = pick(rng, C.TICKET_CHANNELS, k, key=None)
    tid = np.arange(ids["ticket"] + 1, ids["ticket"] + k + 1)
    ids["ticket"] += k
    sink.add("support_tickets", ticket_id=tid, client_id=np.full(k, cid), created_at=created, closed_at=closed,
             category=cats, priority=prio, channel=chan, csat=csat)


_HW = None


def hour_weights():
    global _HW
    if _HW is None:
        w = np.array([0.2, 0.1, 0.1, 0.1, 0.1, 0.2, 0.5, 1.0, 2.5, 4, 5, 5, 4.5, 4.5, 5, 5, 4.5, 4, 3, 2, 1.5, 1, 0.6, 0.4])
        _HW = w / w.sum()
    return _HW


def invoice_dates(i, cl, billing, churn_date, pr):
    signup = cl["signup_date"][i]
    m = C.BILLING[billing[i]]["months"]
    s_month = signup.astype("datetime64[M]")
    months = np.arange(s_month + 1, (P_END + 1).astype("datetime64[M]") + 1)
    months = months[((months - s_month).astype(int) % m) == 0]
    dates = list(months.astype(D))
    if signup >= P_START:
        dates = [signup] + dates
    dates = np.array(dates, dtype=D)
    limit = churn_date[i] if pr["churned"][i] else P_END + 1
    return dates[(dates >= P_START) & (dates <= P_END) & (dates < limit)]


def gen_payments(rng, i, cl, pr, billing, periods, churn_date, sink, ids):
    dates = invoice_dates(i, cl, billing, churn_date, pr)
    k = len(dates)
    if k == 0:
        return
    b = C.BILLING[billing[i]]
    starts = np.array([p[0] for p in periods], dtype=D)
    tariffs = np.array([p[1] for p in periods])
    t_at = tariffs[np.searchsorted(starts, dates, side="right") - 1]
    price = np.array([C.TARIFFS[C.TARIFF_ORDER[t]]["price"] for t in t_at])
    amount = np.maximum(cl["rooms_count"][i] * price, C.MIN_MONTHLY_BILL) * b["months"] * (1 - b["discount"])
    due = dates + C.DUE_DAYS
    paid = dates + np.clip(np.round(rng.normal(4, 3, k)), 0, C.DUE_DAYS).astype(int)
    slight = rng.random(k) < 0.07
    paid = np.where(slight, due + rng.integers(1, 8, k), paid)
    if pr["habitual_late"][i]:
        paid = due + 1 + rng.exponential(12, k).astype(int)
    paid_amount = amount.copy()
    if pr["late_pay"][i]:
        w = (churn_date[i] - dates).astype(int) <= pr["window"][i]
        paid = np.where(w, due + 2 + rng.exponential(18, k).astype(int), paid)
        partial = w & (rng.random(k) < 0.10)
        paid_amount = np.where(partial, np.round(amount * 0.5, 2), paid_amount)
    if pr["dip_late"][i]:
        dip_s = P_START + pr["dip_start"][i]
        w = (dates >= dip_s) & (dates <= dip_s + pr["dip_len"][i])
        paid = np.where(w, due + 1 + rng.exponential(10, k).astype(int), paid)
    unpaid = paid > P_END
    if pr["churned"][i] and pr["reason"][i] == "non_payment":
        unpaid |= dates >= churn_date[i] - 45
    if pr["churned"][i]:
        unpaid |= paid > churn_date[i] + 60
    paid = np.where(unpaid, np.datetime64("NaT"), paid).astype(D)
    paid_amount = np.where(unpaid, 0.0, paid_amount)
    method = np.where(unpaid, None, pr["pay_method"][i]).astype(object)
    iid = np.arange(ids["invoice"] + 1, ids["invoice"] + k + 1)
    ids["invoice"] += k
    sink.add("payments", invoice_id=iid, client_id=np.full(k, cl["client_id"][i]), invoice_date=dates, due_date=due,
             amount=amount, paid_date=paid, paid_amount=paid_amount, payment_method=method)


def summary(cl, churn_date, counts):
    churned = ~np.isnat(churn_date)
    signup = cl["signup_date"]
    exposure = 0
    for k, ms in enumerate(MONTH_STARTS):
        exposure += ((signup < ms) & (np.isnat(churn_date) | (churn_date >= ms))).sum()
    monthly = churned.sum() / exposure
    print("rows:")
    for t, c in counts.items():
        print(f"  {t:<16} {c:>12,}")
    print(f"churned clients: {churned.sum()} of {len(churned)}")
    print(f"annualized churn: {1 - (1 - monthly) ** 12:.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUTPUT_DIR))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(C.SEED)
    cl = build_clients(rng)
    owned = initial_modules(rng, cl)
    tariff_idx, billing = assign_tariffs(rng, cl, owned)
    r = static_risk(rng, cl, owned, tariff_idx, billing)
    churn_date = simulate_churn(rng, cl, r)
    pr = build_profiles(rng, cl, churn_date)

    sink = Sink(out)
    sink.add("clients", **{f.name: cl[f.name] for f in SCHEMAS["clients"]})
    ids = {"sub": 0, "ticket": 0, "invoice": 0}
    for i in range(C.N_CLIENTS):
        gen_client(rng, i, cl, pr, owned, tariff_idx, billing, churn_date, sink, ids)
        if (i + 1) % C.CHUNK_CLIENTS == 0:
            sink.flush()
            print(f"  {i + 1}/{C.N_CLIENTS} clients")
    sink.close()
    summary(cl, churn_date, sink.counts)


if __name__ == "__main__":
    main()
