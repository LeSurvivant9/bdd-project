from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, Result

from .models import Base

# Ensure project root .env is loaded once when this module is imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class QueryResult:
    rows: list[tuple] | None
    plan: str | None


class BaseDBManager:
    def __init__(self, engine: Engine):
        self.engine = engine

    # ---- Schema helpers ----
    def init_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    def drop_table(self, table_name: str, cascade: bool = True) -> None:
        # Dialect-specific fast-path; fallback to SQLAlchemy reflection if needed
        dialect = self.engine.dialect.name
        with self.engine.begin() as conn:
            if dialect == "postgresql":
                clause = " CASCADE" if cascade else ""
                conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table_name}{clause}")
            elif dialect == "oracle":
                clause = " CASCADE CONSTRAINTS" if cascade else ""
                # IF EXISTS not supported on Oracle; attempt and ignore if not exists
                try:
                    conn.exec_driver_sql(f"DROP TABLE {table_name}{clause}")
                except Exception as exc:  # noqa: BLE001 - we intentionally swallow not exists
                    # Ignore error if table doesn't exist
                    err = str(exc).upper()
                    if "ORA-00942" not in err:  # table or view does not exist
                        raise
            else:
                # Generic SQL (may fail depending on dialect)
                try:
                    conn.exec_driver_sql(f"DROP TABLE {table_name}")
                except Exception:
                    pass

    # ---- Query helpers ----
    def execute(self, sql: str, params: Optional[dict[str, Any]] = None) -> Result:
        with self.engine.begin() as conn:
            return conn.execute(text(sql), params or {})

    def explain(self, sql: str, params: Optional[dict[str, Any]] = None) -> str:
        raise NotImplementedError

    def execute_and_explain(
        self, sql: str, params: Optional[dict[str, Any]] = None
    ) -> QueryResult:
        raise NotImplementedError


class PostgresManager(BaseDBManager):
    @staticmethod
    def from_env() -> "PostgresManager":
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "password")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        db = os.getenv("POSTGRES_DB", "postgres_db")
        url = URL.create(
            drivername="postgresql+psycopg",
            username=user,
            password=password,
            host=host,
            port=port,
            database=db,
        ).render_as_string(hide_password=False)
        engine = create_engine(url, pool_pre_ping=True)
        return PostgresManager(engine)

    def explain(self, sql: str, params: Optional[dict[str, Any]] = None) -> str:
        explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}"
        with self.engine.begin() as conn:
            result = conn.exec_driver_sql(explain_sql, params or {})
            plan_lines = [row[0] for row in result]
        return "\n".join(plan_lines)

    def execute_and_explain(
        self, sql: str, params: Optional[dict[str, Any]] = None
    ) -> QueryResult:
        # Run the query and get its plan with ANALYZE (executes the query)
        rows: list[tuple] | None = None
        with self.engine.begin() as conn:
            try:
                res = conn.execute(text(sql), params or {})
                if res.returns_rows:
                    rows = [tuple(r) for r in res.fetchall()]
            finally:
                # Always gather the plan afterwards on the same connection
                plan_rows = conn.exec_driver_sql(
                    f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}", params or {}
                ).fetchall()
        plan = "\n".join(r[0] for r in plan_rows)
        return QueryResult(rows=rows, plan=plan)


class OracleManager(BaseDBManager):
    @staticmethod
    def from_env() -> "OracleManager":
        user = os.getenv("ORACLE_USERNAME", "PDBADMIN")
        password = os.getenv("ORACLE_PASSWORD", "password")
        host = os.getenv("ORACLE_HOST", "localhost")
        port = int(os.getenv("ORACLE_PORT", "1521"))
        service_name = os.getenv("ORACLE_PDB", "FREEPDB1")
        url = URL.create(
            drivername="oracle+oracledb",
            username=user,
            password=password,
            host=host,
            port=port,
            query={"service_name": service_name},
        ).render_as_string(hide_password=False)
        engine = create_engine(url, pool_pre_ping=True)
        return OracleManager(engine)

    def explain(self, sql: str, params: Optional[dict[str, Any]] = None) -> str:
        # Generate a plan without executing, then display it
        with self.engine.begin() as conn:
            conn.exec_driver_sql("EXPLAIN PLAN FOR " + sql, params or {})
            plan_rows = conn.exec_driver_sql(
                "SELECT PLAN_TABLE_OUTPUT FROM TABLE(DBMS_XPLAN.DISPLAY())"
            ).fetchall()
        return "\n".join(r[0] for r in plan_rows)

    def execute_and_explain(
        self, sql: str, params: Optional[dict[str, Any]] = None
    ) -> QueryResult:
        """
        Execute the SQL and attempt to fetch the execution plan with runtime stats.

        Preferred path:
          - ALTER SESSION statistics_level=ALL
          - DBMS_XPLAN.DISPLAY_CURSOR with 'ALLSTATS LAST' (reads V$ views)

        Fallback (no special privileges needed):
          - Use EXPLAIN PLAN + DBMS_XPLAN.DISPLAY() if access to V$ views is denied

        This ensures we always return a plan, even for low-privilege users.
        """
        rows: list[tuple] | None = None
        with self.engine.begin() as conn:
            # Always try to run the statement to also return rows when applicable
            res = conn.execute(text(sql), params or {})
            if res.returns_rows:
                rows = [tuple(r) for r in res.fetchall()]

            # Try high-fidelity plan first (may fail without privileges on V$ views)
            try:
                conn.exec_driver_sql("ALTER SESSION SET statistics_level = ALL")
                plan_rows = conn.exec_driver_sql(
                    "SELECT PLAN_TABLE_OUTPUT FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL, NULL, 'ALLSTATS LAST'))"
                ).fetchall()
                plan = "\n".join(r[0] for r in plan_rows)
                return QueryResult(rows=rows, plan=plan)
            except Exception as exc:  # noqa: BLE001 — fall back if insufficient privileges
                # Known privilege issues: ORA-01031 (insufficient privileges), ORA-00942 (table or view does not exist)
                msg = str(exc).upper()
                if "ORA-01031" not in msg and "ORA-00942" not in msg:
                    # Not a privilege problem → re-raise
                    raise

                # Fallback: classic EXPLAIN PLAN (no runtime stats), available to regular users
                conn.exec_driver_sql("EXPLAIN PLAN FOR " + sql, params or {})
                plan_rows = conn.exec_driver_sql(
                    "SELECT PLAN_TABLE_OUTPUT FROM TABLE(DBMS_XPLAN.DISPLAY())"
                ).fetchall()
                plan = "\n".join(r[0] for r in plan_rows)
                return QueryResult(rows=rows, plan=plan)


__all__ = [
    "BaseDBManager",
    "PostgresManager",
    "OracleManager",
    "QueryResult",
]
