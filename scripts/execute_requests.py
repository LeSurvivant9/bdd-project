import sys
from pathlib import Path
from typing import Iterable, List

# Assurer que le projet racine est dans sys.path lorsqu'on exécute ce fichier directement
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import OracleManager, PostgresManager


# -------------------------
# Helpers (DRY extraction)
# -------------------------
def get_requests_dir() -> Path:
    """Return the requests directory, create it if missing with info message."""
    requests_dir = Path(__file__).resolve().parent.parent / "requests"
    if not requests_dir.exists():
        print(f"[INFO] Dossier 'requests' introuvable à {requests_dir}. Création...")
        requests_dir.mkdir(parents=True, exist_ok=True)
        print(
            "[INFO] Ajoutez vos fichiers .sql (une requête par fichier) dans ce dossier."
        )
    return requests_dir


def iter_sql_files(path: Path) -> Iterable[Path]:
    return sorted([p for p in path.glob("*.sql") if p.is_file()])


def strip_comments_and_semicolon(line: str) -> str:
    """Remove trailing inline -- comments and a trailing semicolon, then trim."""
    no_inline_comment = line.split("--", 1)[0]
    cleaned = no_inline_comment.strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def _normalize_newlines(s: str) -> str:
    """Normalise CRLF/CR vers LF."""
    return s.replace("\r\n", "\n").replace("\r", "\n")


class _SQLSplitter:
    """Petit parseur état‑machine pour découper un script SQL en statements.

    Règles gérées:
    - Quotes simples: '' pour échapper
    - Quotes doubles: "" pour échapper
    - Commentaires ligne: -- ... jusqu'au \n
    - Commentaires bloc: /* ... */
    - Délimiteur: ; en dehors des quotes/commentaires
    """

    def __init__(self, content: str):
        self.s = _normalize_newlines(content)
        self.n = len(self.s)
        self.i = 0
        self.buf: List[str] = []
        self.stmts: List[str] = []
        self.in_single = False
        self.in_double = False
        self.in_line_comment = False
        self.in_block_comment = False

    def _peek(self) -> str:
        return self.s[self.i + 1] if self.i + 1 < self.n else ""

    def _append(self, ch: str) -> None:
        self.buf.append(ch)

    def _finalize_stmt(self) -> None:
        stmt = "".join(self.buf).strip()
        if stmt.endswith(";"):
            stmt = stmt[:-1].rstrip()
        if stmt:
            self.stmts.append(stmt)
        self.buf = []

    def _consume_line_comment(self) -> None:
        # Inclure le texte du commentaire (comme l'implémentation d'origine)
        while self.i < self.n:
            ch = self.s[self.i]
            self._append(ch)
            self.i += 1
            if ch == "\n":
                break

    def _consume_block_comment(self) -> None:
        # Inclure le texte du commentaire jusqu'à */
        while self.i < self.n:
            ch = self.s[self.i]
            nxt = self._peek()
            self._append(ch)
            self.i += 1
            if ch == "*" and nxt == "/":
                self._append(nxt)
                self.i += 1
                break

    def _consume_single_quoted(self) -> None:
        # On est positionné sur le premier ' déjà ajouté au buffer
        while self.i < self.n:
            ch = self.s[self.i]
            nxt = self._peek()
            self._append(ch)
            self.i += 1
            if ch == "'":
                if nxt == "'":  # Quote échappée
                    self._append(nxt)
                    self.i += 1
                else:
                    break

    def _consume_double_quoted(self) -> None:
        while self.i < self.n:
            ch = self.s[self.i]
            nxt = self._peek()
            self._append(ch)
            self.i += 1
            if ch == '"':
                if nxt == '"':  # Quote échappée
                    self._append(nxt)
                    self.i += 1
                else:
                    break

    def run(self) -> List[str]:
        while self.i < self.n:
            ch = self.s[self.i]
            nxt = self._peek()

            # États spéciaux
            if ch == "-" and nxt == "-":
                # début commentaire ligne
                self._append(ch)
                self._append(nxt)
                self.i += 2
                self._consume_line_comment()
                continue
            if ch == "/" and nxt == "*":
                # début commentaire bloc
                self._append(ch)
                self._append(nxt)
                self.i += 2
                self._consume_block_comment()
                continue
            if ch == "'":
                self._append(ch)
                self.i += 1
                self._consume_single_quoted()
                continue
            if ch == '"':
                self._append(ch)
                self.i += 1
                self._consume_double_quoted()
                continue
            if ch == ";":
                # délimiteur de statement
                self._finalize_stmt()
                self.i += 1
                continue

            # caractère normal
            self._append(ch)
            self.i += 1

        # Reste du buffer -> dernier statement (sans ;) si non vide
        tail = "".join(self.buf).strip()
        if tail:
            if tail.endswith(";"):
                tail = tail[:-1].rstrip()
            if tail:
                self.stmts.append(tail)
        return self.stmts


def split_sql_statements(content: str) -> List[str]:
    """Découpe un script SQL en statements en déléguant à un petit parseur.

    Comportement inchangé: les `;` à l'extérieur des quotes/commentaires séparent
    les requêtes. Les requêtes retournées sont trimées et sans `;` terminal, et
    les vides sont ignorées.
    """
    return _SQLSplitter(content).run()


def normalize_for_explain(sql_stmt: str) -> str:
    """If line starts with EXPLAIN (PG) or EXPLAIN PLAN FOR (Oracle), strip that prefix.

    We return the raw statement to execute; managers will compute plans.
    """
    up = sql_stmt.lstrip().upper()
    s = sql_stmt.lstrip()
    if up.startswith("EXPLAIN PLAN FOR "):
        after = s[len("EXPLAIN PLAN FOR ") :].lstrip()
        return after
    if up.startswith("EXPLAIN "):
        rest = s[len("EXPLAIN ") :].lstrip()
        for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
            idx = rest.upper().find(kw)
            if idx >= 0:
                return rest[idx:]
        return rest
    return sql_stmt


def print_query_preview(rows: List[tuple] | None) -> None:
    if rows is not None:
        print(f"  Lignes retournées: {len(rows)}")
        preview = rows[:5]
        if preview:
            print("  Aperçu (jusqu'à 5 lignes):")
            for row in preview:
                print(f"    {row}")
    else:
        print("  Aucune ligne retournée (requête DDL/DML ou sans résultat).")


def execute_and_print_db(label: str, manager, sql: str) -> None:
    print(f"\n[{label}]")
    try:
        result = manager.execute_and_explain(sql)
        print_query_preview(result.rows)
        print("  Plan d'exécution:")
        print(result.plan or "  (aucun plan)")
    except Exception as e:  # noqa: BLE001 - we display error per DB and continue
        print(f"  [ERREUR] {label}: {e}")


def execute_on_both(pg: PostgresManager, ora: OracleManager, sql: str) -> None:
    execute_and_print_db("PostgreSQL", pg, sql)
    execute_and_print_db("Oracle", ora, sql)


def parse_requests_dot_sql(content: str) -> List[str]:
    """Parse requests.sql content into a list of SQL statements.

    The file may contain multi-line statements separated by semicolons. Comments and
    quoted strings are respected. Each returned statement is normalized to remove
    any leading EXPLAIN prefix so that managers compute plans themselves.
    """
    statements = split_sql_statements(content)
    normalized: List[str] = []
    for stmt in statements:
        s = normalize_for_explain(stmt)
        if s.strip():
            normalized.append(s.strip())
    return normalized


def process_requests_dot_sql(
    pg: PostgresManager, ora: OracleManager, content: str
) -> None:
    statements = parse_requests_dot_sql(content)
    if not statements:
        print(
            "[INFO] Aucune requête exploitable trouvée (commentaires/vides uniquement)."
        )
        return
    for idx, sql in enumerate(statements, start=1):
        preview = sql.replace("\n", " ")[:80]
        header = f"[Requête {idx}] {preview}" + ("..." if len(sql) > 80 else "")
        print(f"\n>>> {header}")
        execute_on_both(pg, ora, sql)


def process_single_sql_file(
    pg: PostgresManager, ora: OracleManager, content: str
) -> None:
    sql_whole = content.strip()
    sql_whole = strip_comments_and_semicolon(sql_whole)
    sql_whole = normalize_for_explain(sql_whole)
    if not sql_whole:
        print("[AVERTISSEMENT] Aucune requête exploitable dans ce fichier.")
        return
    execute_on_both(pg, ora, sql_whole)


def process_sql_file(pg: PostgresManager, ora: OracleManager, sql_file: Path) -> None:
    print("\n------------------------------------------------------------------")
    print(f"Requête: {sql_file.name}")
    content = sql_file.read_text(encoding="utf-8")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    if not content.strip():
        print("[AVERTISSEMENT] Fichier vide, ignoré.")
        return
    if sql_file.name.lower() == "requests.sql":
        process_requests_dot_sql(pg, ora, content)
    else:
        process_single_sql_file(pg, ora, content)


def main() -> None:
    pg = PostgresManager.from_env()
    ora = OracleManager.from_env()

    requests_dir = get_requests_dir()
    sql_files = list(iter_sql_files(requests_dir))
    if not sql_files:
        print("[INFO] Aucun fichier .sql trouvé dans 'requests'. Rien à exécuter.")
        return

    print(
        "\n===== Exécution des requêtes et explication des plans (PostgreSQL et Oracle) ====="
    )
    for sql_file in sql_files:
        process_sql_file(pg, ora, sql_file)


if __name__ == "__main__":
    main()
