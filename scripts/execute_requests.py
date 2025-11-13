import sys
from pathlib import Path
from typing import Iterable

# Assurer que le projet racine est dans sys.path lorsqu'on exécute ce fichier directement
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import OracleManager, PostgresManager  # noqa: E402


def main():
    pg = PostgresManager.from_env()
    ora = OracleManager.from_env()

    # --- Lecture et exécution des requêtes depuis le dossier requests ---
    requests_dir = Path(__file__).resolve().parent.parent / "requests"
    if not requests_dir.exists():
        print(f"[INFO] Dossier 'requests' introuvable à {requests_dir}. Création...")
        requests_dir.mkdir(parents=True, exist_ok=True)
        print(
            "[INFO] Ajoutez vos fichiers .sql (une requête par fichier) dans ce dossier."
        )

    def iter_sql_files(path: Path) -> Iterable[Path]:
        return sorted([p for p in path.glob("*.sql") if p.is_file()])

    sql_files = list(iter_sql_files(requests_dir))
    if not sql_files:
        print("[INFO] Aucun fichier .sql trouvé dans 'requests'. Rien à exécuter.")
        return

    print(
        "\n===== Exécution des requêtes et explication des plans (PostgreSQL et Oracle) ====="
    )
    for sql_file in sql_files:
        print("\n------------------------------------------------------------------")
        print(f"Requête: {sql_file.name}")
        sql = sql_file.read_text(encoding="utf-8").strip()
        if not sql:
            print("[AVERTISSEMENT] Fichier vide, ignoré.")
            continue

        # PostgreSQL
        print("\n[PostgreSQL]")
        try:
            pg_result = pg.execute_and_explain(sql)
            if pg_result.rows is not None:
                print(f"  Lignes retournées: {len(pg_result.rows)}")
                preview = pg_result.rows[:5]
                if preview:
                    print("  Aperçu (jusqu'à 5 lignes):")
                    for row in preview:
                        print(f"    {row}")
            else:
                print("  Aucune ligne retournée (requête DDL/DML ou sans résultat).")
            print("  Plan d'exécution:")
            print(pg_result.plan or "  (aucun plan)")
        except Exception as e:
            print(f"  [ERREUR] PostgreSQL: {e}")

        # Oracle
        print("\n[Oracle]")
        try:
            ora_result = ora.execute_and_explain(sql)
            if ora_result.rows is not None:
                print(f"  Lignes retournées: {len(ora_result.rows)}")
                preview = ora_result.rows[:5]
                if preview:
                    print("  Aperçu (jusqu'à 5 lignes):")
                    for row in preview:
                        print(f"    {row}")
            else:
                print("  Aucune ligne retournée (requête DDL/DML ou sans résultat).")
            print("  Plan d'exécution:")
            print(ora_result.plan or "  (aucun plan)")
        except Exception as e:
            print(f"  [ERREUR] Oracle: {e}")


if __name__ == "__main__":
    main()
