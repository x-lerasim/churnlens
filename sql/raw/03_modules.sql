CREATE TABLE IF NOT EXISTS raw.modules
(
    client_id     UInt32,
    module_code   LowCardinality(String),
    enabled_date  Date,
    disabled_date Nullable(Date)
)
ENGINE = MergeTree
ORDER BY (client_id, module_code, enabled_date);
