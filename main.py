from dotenv import load_dotenv

import scripts.execute_requests
import scripts.populate
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

    print("Populating database...")
    scripts.populate.main()
    print("[OK] Database populated.")

    print("Executing requests...")
    scripts.execute_requests.main()
    print("[OK] Requests executed.")

    print("Done.")


if __name__ == "__main__":
    main()
