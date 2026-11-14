FROM apache/airflow:3.1.8-python3.12
# docker-провайдер уже есть в официальном образе; добавляем клиент ClickHouse
RUN pip install --no-cache-dir "apache-airflow==3.1.8" "clickhouse-connect==0.8.18"
