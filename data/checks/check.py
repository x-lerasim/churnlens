import pandas as pd

from data.ch import get_client
from data.generator.config import PERIOD_START

TABLES = ["clients", "subscriptions", "modules", "activity_daily", "bookings", "support_tickets", "payments"]

BASE = f"""
WITH
    months AS (
        SELECT addMonths(toDate('{PERIOD_START}'), number) AS m
        FROM numbers(24)
    ),
    base AS (
        SELECT c.client_id, c.property_type, c.signup_date, s.end_date AS churn_date
        FROM raw.clients AS c
        LEFT JOIN (SELECT client_id, end_date FROM raw.subscriptions WHERE status = 'cancelled') AS s
            ON s.client_id = c.client_id
    ),
    grid AS (
        SELECT
            m, property_type,
            signup_date < m AND (churn_date IS NULL OR churn_date >= m) AS active_start,
            churn_date IS NOT NULL AND toStartOfMonth(churn_date) = m AS churned
        FROM months CROSS JOIN base
    )
"""

MONTHLY = BASE + """
SELECT
    m AS month,
    countIf(active_start) AS active_at_start,
    countIf(churned) AS churned_cnt,
    round(churned_cnt / active_at_start * 100, 2) AS churn_pct
FROM grid
GROUP BY m
ORDER BY m
SETTINGS join_use_nulls = 1
"""

BY_TYPE = BASE + """
SELECT
    property_type,
    countIf(churned) AS churned_cnt,
    round(countIf(active_start) / 24) AS avg_active,
    round((1 - pow(1 - countIf(churned) / countIf(active_start), 12)) * 100, 1) AS annual_churn_pct
FROM grid
GROUP BY property_type
ORDER BY annual_churn_pct DESC
SETTINGS join_use_nulls = 1
"""

REASONS = """
SELECT cancel_reason, count() AS cnt, round(cnt / sum(cnt) OVER () * 100, 1) AS pct
FROM raw.subscriptions
WHERE status = 'cancelled'
GROUP BY cancel_reason
ORDER BY cnt DESC
"""


def show(title, df):
    print(f"\n{title}")
    print(df.to_string(index=False))


def main():
    pd.set_option("display.width", 200)
    client = get_client()
    counts = pd.DataFrame(
        [(t, client.command(f"SELECT count() FROM raw.{t}")) for t in TABLES],
        columns=["table", "rows"],
    )
    show("Строк по таблицам", counts)
    monthly = client.query_df(MONTHLY)
    show("Отток по месяцам", monthly)
    total = monthly["churned_cnt"].sum() / monthly["active_at_start"].sum()
    print(f"\nГодовой отток (среднемесячный в пересчёте на год): {(1 - (1 - total) ** 12) * 100:.1f}%")
    show("Отток по типам объектов", client.query_df(BY_TYPE))
    show("Причины отказа", client.query_df(REASONS))


if __name__ == "__main__":
    main()
