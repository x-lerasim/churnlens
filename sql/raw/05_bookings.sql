CREATE TABLE IF NOT EXISTS raw.bookings
(
    client_id     UInt32,
    booking_date  Date,
    source        LowCardinality(String),
    bookings_cnt  UInt16,
    room_nights   UInt32,
    revenue       Decimal(14, 2),
    cancellations UInt16
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(booking_date)
ORDER BY (client_id, booking_date, source);
