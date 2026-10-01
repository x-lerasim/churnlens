CREATE TABLE IF NOT EXISTS raw.activity_daily
(
    client_id          UInt32,
    activity_date      Date,
    logins             UInt16,
    active_users       UInt8,
    chessboard_actions UInt32,
    rate_updates       UInt32,
    cm_sync_errors     UInt16
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(activity_date)
ORDER BY (client_id, activity_date);
