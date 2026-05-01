"""
Hello World DAG - smoke test for the local Airflow setup.

Validates that:
  - Airflow scheduler picks up DAGs from /opt/airflow/dags
  - Tasks execute successfully
  - Logs are written to disk
  - Task dependencies work as expected

Replace this DAG with the real ingestion pipeline from Day 3 onward.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


def print_hello() -> str:
    """Simple Python callable to test the PythonOperator."""
    message = "Hello from Airflow — Project 1 setup is working."
    print(message)
    return message


default_args = {
    "owner": "jjs",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="hello_world",
    description="Smoke test DAG for local Airflow setup",
    default_args=default_args,
    start_date=datetime(2026, 4, 29),
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=["smoke-test", "project1"],
) as dag:

    task_bash = BashOperator(
        task_id="say_hello_bash",
        bash_command='echo "Hello from BashOperator at $(date)"',
    )

    task_python = PythonOperator(
        task_id="say_hello_python",
        python_callable=print_hello,
    )

    task_bash >> task_python
