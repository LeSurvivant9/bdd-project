from dotenv import load_dotenv

from db import OracleManager, PostgresManager


def main() -> None:
    # Load .env at project root
    load_dotenv()

    print("Initializing PostgreSQL schema...")
    pg = PostgresManager.from_env()
    pg.init_schema()
    print("[OK] Schema created/verified for PostgreSQL")

    print("Initializing Oracle schema...")
    ora = OracleManager.from_env()
    ora.init_schema()
    print("[OK] Schema created/verified for Oracle")

    print("Done.")


if __name__ == "__main__":
    main()
