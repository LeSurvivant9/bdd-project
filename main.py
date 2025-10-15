import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from db import Base


def build_postgres_url() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    db = os.getenv("POSTGRES_DB", "postgres")
    return URL.create(
        drivername="postgresql+psycopg",
        username=user,
        password=password,
        host=host,
        port=port,
        database=db,
    ).render_as_string(hide_password=False)


def build_oracle_url() -> str:
    user = os.getenv("ORACLE_USERNAME", "PDBADMIN")
    password = os.getenv("ORACLE_PASSWORD", "password")
    host = os.getenv("ORACLE_HOST", "localhost")
    port = int(os.getenv("ORACLE_PORT", "1521"))
    service_name = os.getenv("ORACLE_PDB", "FREEPDB1")
    # SQLAlchemy URL with service name
    return URL.create(
        drivername="oracle+oracledb",
        username=user,
        password=password,
        host=host,
        port=port,
        query={"service_name": service_name},
    ).render_as_string(hide_password=False)


def init_db(url: str, label: str) -> None:
    engine = create_engine(url, pool_pre_ping=True)
    # Create all tables if not exist
    Base.metadata.create_all(engine)
    print(f"[OK] Schema created/verified for {label}: {url}")


def main() -> None:
    # Load .env at project root
    load_dotenv()

    pg_url = build_postgres_url()
    ora_url = build_oracle_url()

    print("Initializing PostgreSQL schema...")
    init_db(pg_url, "PostgreSQL")

    print("Initializing Oracle schema...")
    init_db(ora_url, "Oracle")

    print("Done.")


if __name__ == "__main__":
    main()
