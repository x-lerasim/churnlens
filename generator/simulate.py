"""Симуляция клиентов отельной SaaS-платформы.

Механика:
  * у клиента есть латентное «здоровье» h (AR(1) вокруг базового уровня + редкие шоки);
  * месячная вероятность ухода зависит от h, онбординга, январской индексации и межсезонья;
  * за 3 месяца до ухода у 80 % уходящих падает активность (множитель d), у 20 % — нет («тихий» уход);
  * все наблюдаемые таблицы (активность, оплаты, обращения, продукт) порождаются из h и d.
Модель видит только наблюдаемые таблицы; h и d наружу не выгружаются.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import GenConfig

ROOMS_LN = {"hotel": (3.5, 0.6), "mini_hotel": (2.4, 0.4), "hostel": (2.3, 0.4),
            "apartments": (2.0, 0.5), "resort": (4.3, 0.5)}
AVG_STAY = {"hotel": 2.5, "mini_hotel": 2.5, "hostel": 2.0, "apartments": 3.0, "resort": 6.0}
OCC = {"hotel": (0.62, 0.12), "mini_hotel": (0.55, 0.15), "hostel": (0.58, 0.12),
       "apartments": (0.50, 0.18), "resort": (0.50, 0.32)}          # (база, амплитуда)
PRICE = {"start": (3000, 40), "standard": (5000, 70), "pro": (9000, 110)}  # (фикс, за номер), руб./мес.
MODULES_BASE = {"start": 3, "standard": 5, "pro": 7}
INTEGR_BASE = {"start": 1, "standard": 2, "pro": 4}
TICKET_CATS = np.array(["bug", "billing", "howto", "integration", "feature_request"])
TICKET_PRI = np.array(["critical", "high", "normal", "low"])
PRI_RES_K = np.array([0.3, 0.6, 1.0, 1.6])


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _choice(rng, d: dict):
    keys = list(d)
    p = np.array([d[k] for k in keys], dtype=float)
    return keys[rng.choice(len(keys), p=p / p.sum())]


class Simulator:
    def __init__(self, cfg: GenConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.month_starts = pd.date_range(cfg.start, periods=cfg.n_months, freq="MS")
        self.start = np.datetime64(cfg.start, "D")
        self.end = np.datetime64((self.month_starts[-1] + pd.offsets.MonthEnd(0)).date(), "D")
        self.ms = self.month_starts.values.astype("datetime64[D]")
        self.me = np.append(self.ms[1:], self.end + 1)          # первый день следующего месяца
        self.cal_month = self.month_starts.month.values

        self.clients, self.churn, self.activity = [], [], []
        self.invoices, self.tickets, self.product = [], [], []
        self._ticket_id = 1
        self._invoice_id = 1

    # ---------- профиль ----------
    def _profile(self, cid: int) -> dict:
        c, r = self.cfg, self.rng
        htype = _choice(r, c.hotel_types)
        region = "black_sea" if htype == "resort" and r.random() < 0.6 else _choice(r, c.regions)
        mu, s = ROOMS_LN[htype]
        rooms = int(max(3, round(r.lognormal(mu, s))))
        staff = int(max(1, round(rooms * 0.12 + 1 + r.normal(0, 1))))
        score = np.log(rooms) + r.normal(0, 0.7)
        tariff = 0 if score < 2.6 else (1 if score < 3.6 else 2)
        if r.random() < c.share_existing:
            signup = self.start - int(r.integers(30, c.max_prior_tenure_m * 30))
        else:
            total = int((self.end - self.start).astype(int))
            signup = self.start + int(r.integers(0, total - 60))
        base_h = r.normal(0, 0.8) + 0.3 * (tariff == 2) - 0.2 * (htype in ("hostel", "apartments"))
        return dict(client_id=cid, signup_date=signup, hotel_type=htype, region=region,
                    rooms_count=rooms, tariff_initial=c.tariffs[tariff],
                    _staff=staff, _tariff=tariff, _b=base_h)

    # ---------- траектория здоровья и уход ----------
    def _trajectory(self, p: dict):
        c, r = self.cfg, self.rng
        T = c.n_months
        t0 = 0 if p["signup_date"] < self.start else int(np.searchsorted(self.ms, p["signup_date"], "right") - 1)
        h = np.full(T, np.nan)
        cur = p["_b"] + r.normal(0, 0.5)
        churn_t, churn_date = None, None
        seasonal = p["hotel_type"] == "resort" or p["region"] == "black_sea"
        for t in range(t0, T):
            shock = c.shock_size if r.random() < c.shock_prob else 0.0
            cur = p["_b"] + c.h_phi * (cur - p["_b"]) + r.normal(0, c.h_sigma) + shock
            h[t] = cur
            if self.ms[t] <= p["signup_date"]:
                continue                                             # в месяц подключения не уходят
            tenure_m = (self.ms[t] - p["signup_date"]).astype(int) / 30.4
            logit = c.churn_alpha - c.churn_beta * cur
            logit += c.onboarding_bump * (tenure_m < c.onboarding_months)
            logit += c.january_price_bump * (self.cal_month[t] in (1, 2) and tenure_m >= 12)
            logit += c.offseason_bump * (seasonal and self.cal_month[t] in (10, 11))
            if r.random() < _sigmoid(logit):
                days_in = int((self.me[t] - self.ms[t]).astype(int))
                churn_date = self.ms[t] + int(r.integers(0, days_in))
                churn_date = max(churn_date, p["signup_date"] + 1)
                churn_t = t
                break

        d = np.ones(T)
        silent = churn_t is not None and r.random() < c.silent_churn_share
        if churn_t is not None:
            if silent:
                d[churn_t] = 0.9
            else:
                for k, v in enumerate(c.precursor):
                    if churn_t - k >= t0:
                        d[churn_t - k] = v
        return t0, h, d, churn_t, churn_date, silent

    # ---------- ежедневная активность ----------
    def _activity(self, p, h, d, last_day):
        r = self.rng
        first = max(p["signup_date"], self.start)
        if last_day < first:
            return
        days = np.arange(first, last_day + 1)
        mi = (days.astype("datetime64[M]") - self.ms[0].astype("datetime64[M]")).astype(int)
        hd, dd = h[mi], d[mi]
        dow = (days.astype(int) + 3) % 7                             # 0 = понедельник
        wf = np.where(dow >= 5, 0.6, 1.0)
        cm = (days.astype("datetime64[M]").astype(int) % 12) + 1
        base, amp = OCC[p["hotel_type"]]
        amp += 0.1 * (p["region"] == "black_sea")
        occ = np.clip(base + amp * np.cos(2 * np.pi * (cm - 7) / 12), 0.05, 0.97)

        p_act = np.clip(0.55 + 0.12 * hd, 0.1, 0.95) * dd * wf
        active = r.binomial(p["_staff"], np.clip(p_act, 0, 1))
        logins = r.poisson(active * 1.6)
        usage = np.clip(0.85 + 0.08 * hd, 0.2, 1.0) * dd
        bookings = r.poisson(p["rooms_count"] * occ / AVG_STAY[p["hotel_type"]] * usage)
        keep = (logins > 0) | (bookings > 0)
        if keep.any():
            self.activity.append(pd.DataFrame({
                "client_id": p["client_id"], "event_date": days[keep],
                "active_users": active[keep], "logins": logins[keep], "bookings_created": bookings[keep]}))

    # ---------- счета, обращения, продукт (по месяцам) ----------
    def _monthly(self, p, t0, h, d, churn_t, churn_date, silent):
        c, r = self.cfg, self.rng
        T = c.n_months
        t_last = churn_t if churn_t is not None else T - 1
        plan = p["_tariff"]
        tickets_last3 = 0
        downgraded = False
        for t in range(t0, t_last + 1):
            ht, x = h[t], (1 - d[t]) + max(0.0, -h[t]) * 0.3
            ms, me = self.ms[t], self.me[t]
            alive_from = max(ms, p["signup_date"])
            alive_to = churn_date if churn_t == t else me              # не включительно

            # смена тарифа
            if r.random() < _sigmoid(-5.0 - 1.0 * ht + 1.5 * (1 - d[t])) and plan > 0:
                plan -= 1
                downgraded = True
            elif r.random() < _sigmoid(-5.5 + 0.8 * ht) and plan < 2:
                plan += 1
            tname = c.tariffs[plan]

            # счёт: выставляется 1-го числа, начиная с первого полного месяца
            if ms > p["signup_date"]:
                fix, per = PRICE[tname]
                amount = round((fix + per * p["rooms_count"]) / 10) * 10
                due = ms + 10
                late = r.random() < _sigmoid(-1.8 - 1.1 * ht + 2.0 * (1 - d[t]))
                if late:
                    paid = due + 1 + int(r.geometric(1 / (8 * (1 + 2 * (1 - d[t])))))
                else:
                    paid = ms + int(r.integers(0, 11))
                if churn_t == t and not silent and r.random() < 0.6:
                    paid = None
                if paid is not None and paid > self.end:
                    paid = None
                self.invoices.append((self._invoice_id, p["client_id"], ms, tname, amount, due, paid,
                                      int(r.poisson(0.05 + 1.0 * late))))
                self._invoice_id += 1

            # продукт: состояние за месяц
            mods = int(np.clip(MODULES_BASE[tname] + round(0.8 * ht + r.normal(0, 0.5)) - round((1 - d[t]) * 4), 1, 8))
            integ = int(np.clip(INTEGR_BASE[tname] + round(0.6 * ht + r.normal(0, 0.7)) - round((1 - d[t]) * 3), 0, 6))
            self.product.append((p["client_id"], ms, tname, mods, integ))

            # обращения в поддержку
            span = int((alive_to - alive_from).astype(int))
            if span <= 0:
                continue
            tenure_m = (ms - p["signup_date"]).astype(int) / 30.4
            lam = (0.3 + p["_staff"] * 0.05) * np.exp(-0.45 * ht) * (1 + 1.5 * (tenure_m < 3)) * (1 + 2.5 * (1 - d[t]))
            lam *= span / 30.4
            n = r.poisson(lam)
            if t >= t_last - 2:
                tickets_last3 += n
            if n == 0:
                continue
            w = np.array([0.25 * (1 + 1.5 * x), 0.15 * (1 + 2 * x), 0.35, 0.15 * (1 + x), 0.10])
            cats = TICKET_CATS[r.choice(5, n, p=w / w.sum())]
            pw = np.array([0.03 * (1 + 3 * x), 0.15 * (1 + x), 0.5, 0.32])
            pri_i = r.choice(4, n, p=pw / pw.sum())
            created = (alive_from + r.integers(0, span, n)).astype("datetime64[s]") \
                + r.integers(8 * 3600, 22 * 3600, n).astype("timedelta64[s]")
            res_h = r.lognormal(np.log(10), 1.0, n) * PRI_RES_K[pri_i] * (1 + max(0.0, -ht) * 0.3)
            resolved = created + (res_h * 3600).astype("timedelta64[s]")
            csat = np.clip(np.round(4.3 + 0.35 * ht - 0.004 * res_h - 1.2 * x + r.normal(0, 0.6, n)), 1, 5)
            csat_mask = r.random(n) < 0.4
            end_ts = (self.end + 1).astype("datetime64[s]")
            for i in range(n):
                self.tickets.append((
                    self._ticket_id, p["client_id"], created[i], cats[i], TICKET_PRI[pri_i[i]],
                    resolved[i] if resolved[i] < end_ts else None,
                    None if csat_mask[i] else int(csat[i])))
                self._ticket_id += 1

        if churn_t is not None:
            w = dict(c.churn_reasons)
            if silent:
                w["closed_business"] *= 3
            if tickets_last3 >= 3:
                w["support"] *= 3
            if downgraded:
                w["price"] *= 2
            self.churn.append((p["client_id"], churn_date, _choice(r, w)))

    # ---------- запуск ----------
    def run(self) -> dict[str, pd.DataFrame]:
        for i in range(self.cfg.n_clients):
            p = self._profile(100001 + i)
            t0, h, d, churn_t, churn_date, silent = self._trajectory(p)
            last_day = churn_date - 1 if churn_date is not None else self.end
            self._activity(p, h, d, last_day)
            self._monthly(p, t0, h, d, churn_t, churn_date, silent)
            self.clients.append({k: v for k, v in p.items() if not k.startswith("_")})

        to_date = lambda s: pd.to_datetime(s).dt.date
        clients = pd.DataFrame(self.clients)
        clients["signup_date"] = to_date(clients["signup_date"])
        churn = pd.DataFrame(self.churn, columns=["client_id", "churn_date", "churn_reason"])
        churn["churn_date"] = to_date(churn["churn_date"])
        activity = pd.concat(self.activity, ignore_index=True)
        activity["event_date"] = to_date(activity["event_date"])
        inv = pd.DataFrame(self.invoices, columns=["invoice_id", "client_id", "period_start", "tariff",
                                                   "amount_rub", "due_date", "paid_date", "failed_attempts"])
        for col in ("period_start", "due_date", "paid_date"):
            inv[col] = to_date(inv[col])
        tick = pd.DataFrame(self.tickets, columns=["ticket_id", "client_id", "created_at", "category",
                                                   "priority", "resolved_at", "csat"])
        tick["created_at"] = pd.to_datetime(tick["created_at"])
        tick["resolved_at"] = pd.to_datetime(tick["resolved_at"])
        tick["csat"] = tick["csat"].astype("Int8")
        prod = pd.DataFrame(self.product, columns=["client_id", "month_start", "tariff",
                                                   "modules_enabled", "integrations_active"])
        prod["month_start"] = to_date(prod["month_start"])
        return {"clients": clients, "churn_events": churn, "activity_daily": activity,
                "invoices": inv, "support_tickets": tick, "product_monthly": prod}
