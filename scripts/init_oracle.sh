#!/usr/bin/env bash
set -euo pipefail

# Purpose: Initialize Oracle so the application user can create objects without hitting ORA-01950
# - Detects a valid PDB automatically if ORACLE_PDB is wrong or missing
# - Ensures the application user exists (creates it if missing)
# - Sets the user's default tablespace to USERS (if it exists) and grants unlimited quota
# - If USERS doesn't exist in the PDB, creates a dedicated APPDATA tablespace and assigns it
#
# Usage:
#   bash scripts/init_oracle.sh
#
# Requirements:
# - Docker container named "oracle-db" running the Oracle Free image (as in this repo's docker-compose.yml)
# - .env file at project root with at least ORACLE_PASSWORD; ORACLE_PASSWORD optional
# - You run this on the host that can execute `docker exec` into the oracle-db container

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# shellcheck disable=SC1090
if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  source "$ENV_FILE"
  set +o allexport
fi

ORACLE_CONTAINER_NAME=${ORACLE_CONTAINER_NAME:-oracle-db}
ORACLE_PDB=${ORACLE_PDB:-FREEPDB1}
ORACLE_USERNAME=${ORACLE_USERNAME:-PDBADMIN}
# Optional dedicated password for the application user; fallback to admin password if not provided
ORACLE_PASSWORD=${ORACLE_PASSWORD:-${ORACLE_PASSWORD:-password}}

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker is required but not found in PATH." >&2
  exit 1
fi

# Wait for the oracle-db port to be open inside the container
echo "[INFO] Waiting for Oracle container ($ORACLE_CONTAINER_NAME) to be ready..."
for i in {1..60}; do
  if docker exec "$ORACLE_CONTAINER_NAME" bash -lc "echo > /dev/tcp/127.0.0.1/1521" >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [[ $i -eq 60 ]]; then
    echo "[ERROR] Oracle did not become ready in time." >&2
    exit 1
  fi
done

# Helper to run SQL as SYSDBA inside the DB container
run_sql() {
  local sql="$1"
  docker exec -i "$ORACLE_CONTAINER_NAME" bash -lc "sqlplus -s / as sysdba <<'SQL'
SET ECHO OFF HEADING OFF FEEDBACK ON PAGES 0 LINES 200 VERIFY OFF SERVEROUTPUT ON
$sql
EXIT
SQL
"
}

# Helper to fetch a single-line value from SQLPlus
run_sql_scalar() {
  local sql="$1"
  docker exec -i "$ORACLE_CONTAINER_NAME" bash -lc "sqlplus -s / as sysdba <<'SQL' | tr -d '\r' | sed -e '/^\s*$/d' | tail -n 1
SET ECHO OFF HEADING OFF FEEDBACK OFF PAGES 0 LINES 400 VERIFY OFF
${sql}
EXIT
SQL
"
}

# Determine a valid target PDB: prefer ORACLE_PDB, otherwise first READ WRITE PDB (not PDB$SEED)
PDB_TO_USE=$(run_sql_scalar "WITH pref AS (
  SELECT name, 1 ord FROM v\$pdbs WHERE name = UPPER('${ORACLE_PDB}')
), fallback AS (
  SELECT name, 2 ord FROM v\$pdbs WHERE open_mode = 'READ WRITE' AND name <> 'PDB\$SEED'
)
SELECT name FROM (
  SELECT name, ord FROM pref
  UNION ALL
  SELECT name, ord FROM fallback
) WHERE ROWNUM = 1 ORDER BY ord;")

if [[ -z "${PDB_TO_USE}" ]]; then
  echo "[ERROR] Could not determine a usable PDB. Ensure the database has an open PDB." >&2
  exit 1
fi

echo "[INFO] Using PDB: ${PDB_TO_USE} (requested: ${ORACLE_PDB})"

# Ensure Oracle Managed Files is enabled so we can create tablespaces without hardcoding file paths
# This must be executed at CDB level before switching to the PDB
ENABLE_OMF_SQL="ALTER SYSTEM SET db_create_file_dest='/opt/oracle/oradata' SCOPE=BOTH SID='*';"
run_sql "$ENABLE_OMF_SQL"

# Always set container first
SET_PDB_SQL="ALTER SESSION SET CONTAINER = ${PDB_TO_USE};"

# Ensure application user exists in the target PDB
ENSURE_USER_SQL="$SET_PDB_SQL
DECLARE
  v_cnt NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM dba_users WHERE username = UPPER('${ORACLE_USERNAME}');
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'CREATE USER ${ORACLE_USERNAME} IDENTIFIED BY "${ORACLE_PASSWORD}"';
  END IF;
END;
/"
run_sql "$ENSURE_USER_SQL"

# Configure default tablespace and quota: prefer USERS if it exists, else create/use APPDATA
CONFIGURE_TS_SQL="$SET_PDB_SQL
DECLARE
  v_users NUMBER;
  v_cnt   NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_users FROM dba_tablespaces WHERE tablespace_name = 'USERS';
  IF v_users > 0 THEN
    EXECUTE IMMEDIATE 'ALTER USER ${ORACLE_USERNAME} DEFAULT TABLESPACE USERS';
    EXECUTE IMMEDIATE 'ALTER USER ${ORACLE_USERNAME} QUOTA UNLIMITED ON USERS';
  ELSE
    SELECT COUNT(*) INTO v_cnt FROM dba_tablespaces WHERE tablespace_name = 'APPDATA';
    IF v_cnt = 0 THEN
      EXECUTE IMMEDIATE 'CREATE TABLESPACE APPDATA DATAFILE SIZE 500M AUTOEXTEND ON NEXT 50M MAXSIZE UNLIMITED';
    END IF;
    EXECUTE IMMEDIATE 'ALTER USER ${ORACLE_USERNAME} DEFAULT TABLESPACE APPDATA';
    EXECUTE IMMEDIATE 'ALTER USER ${ORACLE_USERNAME} QUOTA UNLIMITED ON APPDATA';
  END IF;
END;
/"

run_sql "$CONFIGURE_TS_SQL"

# Ensure the user has basic object creation privileges in the PDB
GRANTS_SQL="$SET_PDB_SQL
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW, CREATE TRIGGER, CREATE PROCEDURE TO ${ORACLE_USERNAME};
/"
run_sql "$GRANTS_SQL"

# Migrate any existing objects for this user from SYSTEM to the target tablespace (USERS or APPDATA)
MIGRATE_SQL="$SET_PDB_SQL
DECLARE
  v_target_ts VARCHAR2(30);
  v_cnt       NUMBER;
BEGIN
  -- Determine target tablespace
  SELECT COUNT(*) INTO v_cnt FROM dba_tablespaces WHERE tablespace_name = 'USERS';
  IF v_cnt > 0 THEN
    v_target_ts := 'USERS';
  ELSE
    v_target_ts := 'APPDATA';
    SELECT COUNT(*) INTO v_cnt FROM dba_tablespaces WHERE tablespace_name = 'APPDATA';
    IF v_cnt = 0 THEN
      EXECUTE IMMEDIATE 'CREATE TABLESPACE APPDATA DATAFILE SIZE 500M AUTOEXTEND ON NEXT 50M MAXSIZE UNLIMITED';
    END IF;
  END IF;

  -- Move heap/partition tables out of SYSTEM if any
  FOR t IN (
    SELECT table_name FROM dba_tables
    WHERE owner = UPPER('${ORACLE_USERNAME}') AND tablespace_name = 'SYSTEM'
  ) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'ALTER TABLE ${ORACLE_USERNAME}.' || t.table_name || ' MOVE TABLESPACE ' || v_target_ts;
    EXCEPTION WHEN OTHERS THEN NULL; END;
  END LOOP;

  -- Move LOB segments
  FOR l IN (
    SELECT table_name, column_name FROM dba_lobs
    WHERE owner = UPPER('${ORACLE_USERNAME}') AND tablespace_name = 'SYSTEM'
  ) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'ALTER TABLE ${ORACLE_USERNAME}.' || l.table_name || ' MOVE LOB(' || l.column_name || ') STORE AS (TABLESPACE ' || v_target_ts || ')';
    EXCEPTION WHEN OTHERS THEN NULL; END;
  END LOOP;

  -- Rebuild indexes into target tablespace
  FOR i IN (
    SELECT index_name FROM dba_indexes
    WHERE owner = UPPER('${ORACLE_USERNAME}') AND tablespace_name = 'SYSTEM'
  ) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'ALTER INDEX ${ORACLE_USERNAME}.' || i.index_name || ' REBUILD TABLESPACE ' || v_target_ts;
    EXCEPTION WHEN OTHERS THEN NULL; END;
  END LOOP;
END;
/"
run_sql "$MIGRATE_SQL"

echo "[OK] Oracle initialization completed for user ${ORACLE_USERNAME} in PDB ${PDB_TO_USE}."
