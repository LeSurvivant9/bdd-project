from db import OracleManager, PostgresManager

if __name__ == "__main__":
    pg = PostgresManager.from_env()
    print("Dropping all PostgreSQL tables...")
    pg.drop_all()

    ora = OracleManager.from_env()
    print("Dropping all Oracle tables...")
    ora.drop_all()

    print("Done.")
