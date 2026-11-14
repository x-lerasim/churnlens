FROM python:3.12.8-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DBT_PROFILES_DIR=/dbt
RUN pip install --no-cache-dir "dbt-core==1.9.4" "dbt-clickhouse==1.9.1"
WORKDIR /dbt
ENTRYPOINT ["dbt"]
CMD ["debug"]
