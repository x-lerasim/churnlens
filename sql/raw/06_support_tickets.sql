CREATE TABLE IF NOT EXISTS raw.support_tickets
(
    ticket_id  UInt32,
    client_id  UInt32,
    created_at DateTime,
    closed_at  Nullable(DateTime),
    category   LowCardinality(String),
    priority   LowCardinality(String),
    channel    LowCardinality(String),
    csat       Nullable(UInt8)
)
ENGINE = MergeTree
ORDER BY (client_id, created_at);
