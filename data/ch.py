import os

import clickhouse_connect


def get_client(database="default"):
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "churnlens"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "churnlens"),
        database=database,
    )
