"""Destructive PostgreSQL migration smoke test for an explicitly disposable database.

The target database must be empty and its name must contain ``stage1_smoke``. The
script migrates it, drives the authenticated HTTP workflow, verifies PostgreSQL-only
integrity behaviour, downgrades to base, upgrades again, and confirms a clean reseed.
It never creates or drops the database itself.
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from urllib.parse import urlparse

import httpx
import psycopg
from psycopg import errors

from app.seed import LEASEDESK_TRUTH

BASE_URL = "http://127.0.0.1:8876"
EXPECTED_INDEXES = {
    "ix_truth_product_status",
    "uq_truth_one_draft_per_product",
    "uq_truth_product_version",
}
EXPECTED_CONSTRAINTS = {
    "ck_truth_approval_timestamp",
    "ck_truth_status",
}
EXPECTED_STAGE2_TABLES = {
    "signals",
    "creative_runs",
    "creative_run_signals",
    "concepts",
    "challenges",
    "experiments",
    "learnings",
}
EXPECTED_STAGE3_TABLES = {"ai_executions"}


def database_url() -> str:
    url = os.environ["DATABASE_URL"]
    database_name = urlparse(url.replace("postgresql+psycopg://", "postgresql://")).path
    if "stage1_smoke" not in database_name:
        raise RuntimeError("Refusing to run: database name must contain 'stage1_smoke'")
    return url.replace("postgresql+psycopg://", "postgresql://")


def run_alembic(*arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        check=True,
        env=os.environ.copy(),
    )


@contextmanager
def running_application():
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8876",
        ],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError(f"Application exited during startup with {process.returncode}")
            try:
                if httpx.get(f"{BASE_URL}/login", timeout=0.5).status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Application did not become ready")
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def csrf_from(html: str) -> str:
    match = re.search(r'name="csrf" value="([a-f0-9]+)"', html)
    if not match:
        raise AssertionError("CSRF token was not rendered")
    return match.group(1)


def drive_truth_workflow() -> str:
    with httpx.Client(base_url=BASE_URL, follow_redirects=False) as client:
        login = client.post("/login", data={"password": os.environ["OPERATOR_PASSWORD"]})
        assert login.status_code == 303
        truth = client.get("/truth")
        assert truth.status_code == 200
        assert "Small-commercial-property landlords" in truth.text
        assert "quantified time savings" in truth.text
        csrf = csrf_from(truth.text)

        created = client.post("/truth/drafts", data={"csrf": csrf})
        assert created.status_code == 303
        draft_id = created.headers["location"].split("/")[3]

        form = {"csrf": csrf, "change_note": "PostgreSQL smoke-test revision."}
        for key, item in LEASEDESK_TRUTH.model_dump(mode="json").items():
            form[f"{key}__value"] = item["value"]
            form[f"{key}__confidence"] = item["confidence"]
            form[f"{key}__basis"] = item["basis"]
        form["buyer__value"] = "The accountable landlord or owner-operator."
        saved = client.post(f"/truth/drafts/{draft_id}", data=form)
        assert saved.status_code == 303

        approved = client.post(f"/truth/drafts/{draft_id}/approve", data={"csrf": csrf})
        assert approved.status_code == 303
        approved_page = client.get(approved.headers["location"])
        assert approved_page.status_code == 200
        assert "approved and immutable" in approved_page.text
        return draft_id


def expect_database_error(connection, error_type, statement: str, parameters=()) -> None:
    try:
        with connection.transaction():
            connection.execute(statement, parameters)
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__} for: {statement}")


def verify_postgresql_integrity(approved_id: str) -> dict:
    with psycopg.connect(database_url(), autocommit=True) as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                "AND tablename='truth_versions'"
            )
        }
        assert indexes >= EXPECTED_INDEXES

        constraints = {
            row[0]
            for row in connection.execute(
                "SELECT conname FROM pg_constraint " "WHERE conrelid='truth_versions'::regclass"
            )
        }
        assert constraints >= EXPECTED_CONSTRAINTS

        product_id, content = connection.execute(
            "SELECT product_id, content FROM truth_versions WHERE id=%s", (approved_id,)
        ).fetchone()

        expect_database_error(
            connection,
            errors.CheckViolation,
            "INSERT INTO truth_versions "
            "(id, product_id, version, status, content, created_at, updated_at) "
            "VALUES (%s, %s, 90, 'invalid', %s::json, now(), now())",
            (str(uuid.uuid4()), product_id, json.dumps(content)),
        )
        expect_database_error(
            connection,
            errors.CheckViolation,
            "INSERT INTO truth_versions "
            "(id, product_id, version, status, content, created_at, updated_at, approved_at) "
            "VALUES (%s, %s, 91, 'draft', %s::json, now(), now(), now())",
            (str(uuid.uuid4()), product_id, json.dumps(content)),
        )

        first_draft_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO truth_versions "
            "(id, product_id, version, status, content, created_at, updated_at) "
            "VALUES (%s, %s, 92, 'draft', %s::json, now(), now())",
            (first_draft_id, product_id, json.dumps(content)),
        )
        expect_database_error(
            connection,
            errors.UniqueViolation,
            "INSERT INTO truth_versions "
            "(id, product_id, version, status, content, created_at, updated_at) "
            "VALUES (%s, %s, 93, 'draft', %s::json, now(), now())",
            (str(uuid.uuid4()), product_id, json.dumps(content)),
        )
        connection.execute("DELETE FROM truth_versions WHERE id=%s", (first_draft_id,))

        expect_database_error(
            connection,
            errors.RaiseException,
            "UPDATE truth_versions SET change_note='forbidden' WHERE id=%s",
            (approved_id,),
        )
        expect_database_error(
            connection,
            errors.RaiseException,
            "DELETE FROM truth_versions WHERE id=%s",
            (approved_id,),
        )

        audit = connection.execute(
            "SELECT tv.xmin::text, ae.xmin::text, count(*) OVER () "
            "FROM truth_versions tv JOIN audit_events ae ON ae.truth_version_id=tv.id "
            "WHERE tv.id=%s AND ae.event_type='truth.approved'",
            (approved_id,),
        ).fetchone()
        assert audit is not None
        assert audit[0] == audit[1], "Truth approval and audit event used different transactions"
        assert audit[2] == 1

        trigger_enabled = connection.execute(
            "SELECT tgenabled FROM pg_trigger "
            "WHERE tgrelid='truth_versions'::regclass AND tgname='truth_versions_immutable'"
        ).fetchone()
        assert trigger_enabled == ("O",)

    return {
        "partial_index_verified": True,
        "check_constraints_verified": True,
        "approved_update_rejected": True,
        "approved_delete_rejected": True,
        "approval_audit_same_transaction": True,
        "immutability_trigger_enabled": True,
    }


def verify_ai_execution_integrity() -> dict:
    with psycopg.connect(database_url(), autocommit=True) as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                "AND tablename='ai_executions'"
            )
        }
        assert {"uq_ai_execution_idempotency", "ix_ai_execution_origin"} <= indexes
        constraints = {
            row[0]
            for row in connection.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid='ai_executions'::regclass"
            )
        }
        assert "ck_ai_execution_status" in constraints
        execution_id = str(uuid.uuid4())
        values = (
            execution_id,
            "generate_collisions",
            "pending",
            "openai",
            "test-model",
            "v1",
            "v1",
            "creative_run",
            str(uuid.uuid4()),
            "smoke-idempotency-key",
        )
        connection.execute(
            "INSERT INTO ai_executions "
            "(id, task_type, status, provider, model, prompt_version, schema_version, "
            "origin_type, origin_id, idempotency_key, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
            values,
        )
        expect_database_error(
            connection,
            errors.UniqueViolation,
            "INSERT INTO ai_executions "
            "(id, task_type, status, provider, model, prompt_version, schema_version, "
            "origin_type, origin_id, idempotency_key, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
            (str(uuid.uuid4()), *values[1:]),
        )
        expect_database_error(
            connection,
            errors.CheckViolation,
            "UPDATE ai_executions SET status='invalid' WHERE id=%s",
            (execution_id,),
        )
    return {
        "ai_execution_schema_verified": True,
        "ai_execution_indexes_verified": True,
        "ai_execution_constraints_verified": True,
        "ai_execution_idempotency_verified": True,
    }


def verify_clean_state(expected_tables: bool) -> None:
    with psycopg.connect(database_url()) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        }
        assert ("products" in tables) is expected_tables
        if expected_tables:
            assert tables >= EXPECTED_STAGE2_TABLES
            assert tables >= EXPECTED_STAGE3_TABLES


def main() -> None:
    verify_clean_state(expected_tables=False)
    run_alembic("upgrade", "head")
    with running_application():
        approved_id = drive_truth_workflow()
    result = verify_postgresql_integrity(approved_id)
    result.update(verify_ai_execution_integrity())

    run_alembic("downgrade", "base")
    verify_clean_state(expected_tables=False)
    run_alembic("upgrade", "head")
    verify_clean_state(expected_tables=True)
    with running_application(), httpx.Client(base_url=BASE_URL, follow_redirects=True) as client:
        login = client.post("/login", data={"password": os.environ["OPERATOR_PASSWORD"]})
        assert login.status_code == 200
        assert "Truth v1 approved" in login.text

    result.update(
        {
            "clean_initial_upgrade": True,
            "clean_downgrade": True,
            "clean_reupgrade": True,
            "reseed_after_reupgrade": True,
            "authenticated_http_workflow": True,
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
