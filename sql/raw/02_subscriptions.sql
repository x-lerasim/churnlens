CREATE TABLE IF NOT EXISTS raw.subscriptions
(
    subscription_id UInt32,
    client_id       UInt32,
    tariff          LowCardinality(String),
    billing_period  LowCardinality(String),
    price_per_room  Decimal(10, 2),
    start_date      Date,
    end_date        Nullable(Date),
    status          LowCardinality(String),
    cancel_reason   LowCardinality(Nullable(String))
)
ENGINE = MergeTree
ORDER BY (client_id, start_date);
