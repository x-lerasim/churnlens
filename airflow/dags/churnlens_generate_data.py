"""generate (контейнер генератора) → load_raw (ClickHouse raw) → validate → dbt_build (контейнер dbt)."""
import json
import os
from pathlib import Path

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import Param, dag, task
from docker.types import Mount

TABLES = ["clients", "churn_events", "activity_daily", "invoices", "support_tickets", "product_monthly"]
SQL = Path(__file__).parent / "sql" / "raw_tables.sql"
META = Path("/opt/airflow/data/raw/_meta.json")
HOST = os.environ["HOST_PROJECT_DIR"]          # пути для монтирования — на хосте
DOCKER = dict(docker_url="unix://var/run/docker.sock", auto_remove="success",
              mount_tmp_dir=False, force_pull=False)


def ch():
    import clickhouse_connect
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"], port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"], password=os.environ["CLICKHOUSE_PASSWORD"],
        send_receive_timeout=600)


def ddl(client, suffix):
    for stmt in SQL.read_text().replace("{suffix}", suffix).split(";"):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            client.command(body)


@dag(
    dag_id="churnlens_generate_data",
    schedule=None,
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Moscow"),
    catchup=False,
    tags=["churnlens"],
    params={"n_clients": Param(5000, type="integer", minimum=100),
            "seed": Param(42, type="integer")},
)
def churnlens_generate_data():
    generate = DockerOperator(
        task_id="generate",
        image="churnlens/generator:1.0",
        command=["--out", "/data/out", "--clients", "{{ params.n_clients }}", "--seed", "{{ params.seed }}"],
        network_mode="none",
        user=f"{os.environ['AIRFLOW_UID']}:0",
        mounts=[Mount(source=f"{HOST}/data/raw", target="/data/out", type="bind")],
        **DOCKER,
    )

    @task
    def load_raw():
        c = ch()
        ddl(c, "")
        for t in TABLES:
            c.command(f"DROP TABLE IF EXISTS raw.{t}_new")
        ddl(c, "_new")
        for t in TABLES:
            c.command(f"INSERT INTO raw.{t}_new SELECT * FROM file('raw/{t}.csv.gz', 'CSVWithNames')")
            c.command(f"EXCHANGE TABLES raw.{t} AND raw.{t}_new")
            c.command(f"DROP TABLE raw.{t}_new")
        return {t: int(c.command(f"SELECT count() FROM raw.{t}")) for t in TABLES}

    @task
    def validate(counts: dict):
        expected = json.loads(META.read_text())["rows"]
        bad = {t: (counts[t], expected[t]) for t in TABLES if counts[t] != expected[t]}
        if bad:
            raise ValueError(f"raw ≠ генератор: {bad}")

    dbt_build = DockerOperator(
        task_id="dbt_build",
        image="churnlens/dbt:1.0",
        command=["build"],
        network_mode="churnlens",
        environment={k: os.environ[k] for k in
                     ("CLICKHOUSE_HOST", "CLICKHOUSE_PORT", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")},
        mounts=[Mount(source=f"{HOST}/dbt", target="/dbt", type="bind")],
        **DOCKER,
    )

    loaded = load_raw()
    generate >> loaded
    validate(loaded) >> dbt_build


churnlens_generate_data()
