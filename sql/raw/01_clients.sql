CREATE TABLE IF NOT EXISTS raw.clients
(
    client_id           UInt32,
    property_name       String,
    property_type       LowCardinality(String),
    region              LowCardinality(String),
    rooms_count         UInt16,
    signup_date         Date,
    acquisition_channel LowCardinality(String),
    has_account_manager UInt8
)
ENGINE = MergeTree
ORDER BY client_id;
