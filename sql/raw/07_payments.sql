CREATE TABLE IF NOT EXISTS raw.payments
(
    invoice_id     UInt32,
    client_id      UInt32,
    invoice_date   Date,
    due_date       Date,
    amount         Decimal(12, 2),
    paid_date      Nullable(Date),
    paid_amount    Decimal(12, 2),
    payment_method LowCardinality(Nullable(String))
)
ENGINE = MergeTree
ORDER BY (client_id, invoice_date);
