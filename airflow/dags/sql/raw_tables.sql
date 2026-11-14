-- Схемы raw-таблиц. {suffix} = '' для боевых, '_new' для промежуточных при перезаливке.

CREATE TABLE IF NOT EXISTS raw.clients{suffix} (
    client_id       UInt32,
    signup_date     Date,
    hotel_type      LowCardinality(String),
    region          LowCardinality(String),
    rooms_count     UInt16,
    tariff_initial  LowCardinality(String)
) ENGINE = MergeTree ORDER BY client_id;

CREATE TABLE IF NOT EXISTS raw.churn_events{suffix} (
    client_id     UInt32,
    churn_date    Date,
    churn_reason  LowCardinality(String)
) ENGINE = MergeTree ORDER BY client_id;

CREATE TABLE IF NOT EXISTS raw.activity_daily{suffix} (
    client_id         UInt32,
    event_date        Date,
    active_users      UInt16,
    logins            UInt32,
    bookings_created  UInt32
) ENGINE = MergeTree PARTITION BY toYear(event_date) ORDER BY (client_id, event_date);

CREATE TABLE IF NOT EXISTS raw.invoices{suffix} (
    invoice_id       UInt32,
    client_id        UInt32,
    period_start     Date,
    tariff           LowCardinality(String),
    amount_rub       UInt32,
    due_date         Date,
    paid_date        Nullable(Date),
    failed_attempts  UInt8
) ENGINE = MergeTree ORDER BY (client_id, period_start);

CREATE TABLE IF NOT EXISTS raw.support_tickets{suffix} (
    ticket_id    UInt32,
    client_id    UInt32,
    created_at   DateTime,
    category     LowCardinality(String),
    priority     LowCardinality(String),
    resolved_at  Nullable(DateTime),
    csat         Nullable(UInt8)
) ENGINE = MergeTree ORDER BY (client_id, created_at);

CREATE TABLE IF NOT EXISTS raw.product_monthly{suffix} (
    client_id            UInt32,
    month_start          Date,
    tariff               LowCardinality(String),
    modules_enabled      UInt8,
    integrations_active  UInt8
) ENGINE = MergeTree ORDER BY (client_id, month_start);
