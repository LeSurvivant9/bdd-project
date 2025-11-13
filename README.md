# Comparaison de bases de données (Oracle & PostgreSQL) — Festival

Objectif du projet : implanter un schéma commun dans deux SGBD relationnels (Oracle et PostgreSQL), exécuter des
requêtes et analyser les plans d’exécution. Ce dépôt fournit:

- Oracle, PostgreSQL et Adminer dockerisés (Adminer incluant le support Oracle via OCI8) pour administrer les deux
  bases.
- Un script Python (SQLAlchemy) pour créer le schéma sur les deux bases.

Schéma (gestion simplifiée d’un festival):

- Groupe (IdGroupe, NomGroupe, Style, PaysOrigine, NbMembres)
- Scene (IdScene, NomScene, Emplacement, Capacite)
- Concert (IdConcert, DateConcert, HeureDebut, Duree, #IdScene, #IdGroupe)
- Benevole (IdBenevole, Nom, Prenom, Telephone, Email, Poste)
- Affectation (#IdBenevole, #IdConcert, Role)
- Partenaire (IdPartenaire, NomPartenaire, TypePartenaire)
- Sponsoring (#IdPartenaire, #IdConcert, Montant)

Les modèles SQLAlchemy sont définis dans `db/models.py`. Le script `main.py` se connecte aux deux SGBD et crée toutes
les tables si elles n’existent pas.

---

## Prérequis

- Docker Desktop (macOS/Windows/Linux)
- Python 3.10+
- Pas besoin de télécharger manuellement les ZIP Oracle Instant Client : le Dockerfile d’Adminer peut les télécharger
  automatiquement depuis Oracle (Instant Client 23.9 x64) lors du build. Connexion Internet requise pendant
  `docker compose build adminer`.
    - En environnement hors‑ligne, vous pouvez toujours placer les deux fichiers ZIP à côté de `adminer/Dockerfile`
      et/ou surcharger les URLs de téléchargement.
    - Pour surcharger les URLs au build :
      `docker compose build --build-arg IC_BASIC_URL=<url_basic_lite> --build-arg IC_SDK_URL=<url_sdk> adminer`.

Les dépendances Python sont gérées via `pyproject.toml` (SQLAlchemy, psycopg pour PostgreSQL, oracledb pour Oracle,
python-dotenv).

---

## Configuration (.env)

À la racine du projet, éditez le fichier `.env` (déjà présent) pour définir les identifiants et valeurs par défaut:

```
# Identifiants Oracle utilisés par Adminer et le script Python
ORACLE_USERNAME=PDBADMIN
ORACLE_PASSWORD=password
ORACLE_PDB=FREEPDB1

# Identifiants PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=postgres_db
```

Paramètres hôte/ports optionnels pour le script Python (les valeurs par défaut fonctionnent avec ce compose):

```
# Surcharges optionnelles (valeurs par défaut ci‑dessous)
# ORACLE_HOST=localhost
# ORACLE_PORT=1521
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
```

Notes:

- Les utilisateurs Oracle disponibles par défaut sont `SYS`, `SYSTEM` et `PDBADMIN`. Préférez `PDBADMIN` pour les
  connexions applicatives.
- Le mot de passe Oracle réellement utilisé par le conteneur est celui défini lors de la toute première initialisation
  de son volume de données. Si vous modifiez plus tard `.env`, réinitialisez le mot de passe dans le conteneur (
  `docker exec oracle-db ./setPassword.sh <nouveau>`) ou recréez le volume.

---

## Démarrer la stack

Depuis la racine du dépôt:

```
# Construire l’image Adminer (inclut OCI8 pour Oracle si vous avez fourni les ZIP)
docker compose build adminer

# Démarrer l’ensemble (Oracle, PostgreSQL, Adminer)
docker compose up -d
```

Composants:

- Adminer: http://localhost:8080
- PostgreSQL: localhost:5432 (nom de service `postgres-db` sur le réseau Docker)
- Oracle: localhost:1521 (nom de service `oracle-db` sur le réseau Docker)

---

## Initialiser le schéma avec SQLAlchemy

Utilisez votre Python local pour exécuter le script d’initialisation. Il lira `.env`, se connectera aux deux SGBD et
créera toutes les tables du festival dans chaque base.

```
# Avec uv (recommandé, environnement isolé rapide)
uv run python main.py

# Ou avec pip
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -U pip
pip install -e .
python main.py
```

Sortie attendue:

```
Initializing PostgreSQL schema...
[OK] Schema created/verified for PostgreSQL: postgresql+psycopg://...
Initializing Oracle schema...
[OK] Schema created/verified for Oracle: oracle+oracledb://...
Done.
```

Si vous voyez des erreurs d’authentification, alignez les identifiants comme expliqué ci‑dessus (voir `.env`, et notez
la persistance des mots de passe dans les volumes).

---

## Exécuter vos scripts SQL (dossier `requests/`)

Deux façons d’exécuter automatiquement vos requêtes SQL (une requête par fichier `.sql`) et d’afficher le plan
d’exécution pour PostgreSQL et Oracle:

1) Workflow complet (réinitialisation du schéma + peuplement + exécution des requêtes):

```
uv run main.py
```

Ce script:
- initialise/verify les schémas sur PostgreSQL et Oracle,
- peuple la base avec des données de test,
- puis lit et exécute chaque fichier `*.sql` dans `requests/` en affichant un aperçu des résultats et les plans
  d’exécution des deux SGBD.

2) Itérer sur les requêtes sans réinitialiser les données (ne touche pas au schéma ni aux données):

```
uv run scripts/execute_requests.py
```

Conseils:
- Placez vos requêtes dans le dossier `requests/` à la racine (ex.: `requests/01_count_groupes.sql`).
- Une seule requête par fichier.
- Les résultats et plans d’exécution sont affichés séparément pour PostgreSQL puis Oracle.

---

## Initialisation Oracle après démarrage (recommandé)

Après avoir démarré les conteneurs (`docker compose up -d`), exécutez le script d’initialisation Oracle pour éviter des
erreurs liées aux tablespaces/quotas et privilèges (ex.: ORA-01950, ORA-01031) et pour préparer l’utilisateur
applicatif:

```
# À lancer dans un terminal compatible bash (macOS/Linux, WSL ou Git Bash sur Windows)
bash scripts/init_oracle.sh
```

Ce script:
- détecte automatiquement un PDB valide (par défaut `FREEPDB1`),
- crée l’utilisateur s’il n’existe pas (`ORACLE_USERNAME`, par défaut `PDBADMIN`),
- assigne un tablespace par défaut (`USERS` si présent, sinon crée `APPDATA`) et une quota illimitée,
- accorde les privilèges de base (CREATE SESSION/TABLE/SEQUENCE/VIEW/PROCEDURE),
- et migre d’éventuels objets depuis `SYSTEM` vers le tablespace cible.

Pré‑requis:
- le conteneur `oracle-db` doit être démarré et accessible,
- le fichier `.env` doit être renseigné (au minimum `ORACLE_PASSWORD`).

Astuce:
- Si vous êtes sous Windows PowerShell, exécutez ce script via WSL ou Git Bash. En cas d’erreur « Permission denied »,
  rendez le script exécutable: `chmod +x scripts/init_oracle.sh` puis relancez la commande ci‑dessus.

---

## Utiliser Adminer pour inspecter les tables et exécuter des requêtes

- Ouvrez http://localhost:8080
- Connexion à PostgreSQL:
    - System: PostgreSQL
    - Server: postgres-db
    - Username: POSTGRES_USER
    - Password: POSTGRES_PASSWORD
    - Database: POSTGRES_DB
- Connexion à Oracle:
    - System: Oracle
    - Server: oracle-db (ou un alias TNS, voir plus bas)
    - Username: PDBADMIN (ou votre utilisateur applicatif)
    - Password: ORACLE_PASSWORD
    - Database: ORACLE_PDB (ex.: FREEPDB1)

Si « Oracle » n’apparaît pas dans la liste, reconstruisez l’image Adminer avec OCI8 selon `adminer/Dockerfile` et
assurez‑vous que l’architecture des ZIP Instant Client correspond à la plateforme de votre conteneur.

---

## Où regarder dans le code

- `db/models.py`: tous les modèles SQLAlchemy avec clés étrangères et clés primaires composites pour les tables
  d’association.
- `main.py`: gestion de l’environnement et création du schéma pour les deux SGBD.
- `adminer/Dockerfile`: build personnalisé d’Adminer avec OCI8.
- `docker-compose.yml` et les fichiers compose spécifiques aux services.

---

## Dépannage

- Mot de passe différent après modification de `.env`: réinitialisez‑le dans le conteneur ou recréez les volumes.
- Nom du service/PDB Oracle: vérifiez depuis SQL*Plus dans le conteneur:
  ```
  docker exec -i oracle-db sqlplus -s / as sysdba <<'SQL'
  show con_name;
  show pdbs;
  SQL
  ```
- Depuis le conteneur Adminer, testez l’accessibilité TCP:
  ```
  docker exec -it adminer sh -lc "nc -zv postgres-db 5432 || true"
  docker exec -it adminer sh -lc "nc -zv oracle-db 1521 || true"
  ```

### Erreur ORA-01031 (insufficient privileges) lors de l'initialisation Oracle

Si le script échoue sur Oracle avec ORA-01031 lors d'un `CREATE TABLE`, l'utilisateur n'a probablement pas de quota sur
le tablespace `USERS` et/ou manque de privilèges de création.

Exécutez ces commandes en tant que SYSDBA pour accorder une quota et les privilèges minimaux à `PDBADMIN` (ou à votre
utilisateur applicatif):

```
# Connexion directe au service du PDB (remplacez le mot de passe SYS et le nom de service si besoin)
docker exec -i oracle-db sqlplus -S sys/password@//localhost:1521/ORACLE_DB AS SYSDBA <<'SQL'
ALTER USER PDBADMIN QUOTA UNLIMITED ON USERS;
GRANT CREATE SESSION TO PDBADMIN;
GRANT CREATE TABLE, CREATE SEQUENCE, CREATE VIEW TO PDBADMIN;
EXIT
SQL
```

Notes:

- Si vous vous connectez au service de la CDB (par ex. `FREE`/`XE`) au lieu du PDB, basculez d'abord:
  `ALTER SESSION SET CONTAINER = ORACLE_DB;` puis exécutez les mêmes commandes.
- Adaptez `ORACLE_DB` au nom exact de votre PDB (voir `.env`: `ORACLE_PDB`).
- Pour un schéma dédié, remplacez `PDBADMIN` par votre utilisateur (recommandé en prod).

Vérifications rapides:

```
# Vérifier l'utilisateur et le PDB actifs
docker exec -i oracle-db sqlplus -s PDBADMIN/password@//localhost:1521/ORACLE_DB <<'SQL'
SELECT sys_context('USERENV','SESSION_USER') AS user, sys_context('USERENV','CON_NAME') AS pdb FROM dual;
SQL
```

---

## Connexion Oracle via TNS dans Adminer

Si vous ne parvenez pas à vous connecter via les champs hôte/service d’Adminer, vous pouvez utiliser un alias TNS. Ce
dépôt fournit un fichier TNS monté dans le conteneur Adminer.

- Emplacement du fichier TNS dans le dépôt: `adminer/tns/tnsnames.ora`
- Monté dans Adminer à: `/opt/oracle/instantclient_23_9/network/admin` (c’est `$TNS_ADMIN`)

Entrées par défaut fournies:

```
ORACLE_DB =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = oracle-db)(PORT = 1521))
    (CONNECT_DATA = (SERVICE_NAME = FREEPDB1))
  )

ORCL =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = oracle-db)(PORT = 1521))
    (CONNECT_DATA = (SERVICE_NAME = FREEPDB1))
  )
```

Utilisation dans l’interface Adminer (http://localhost:8080):

- System: `Oracle`
- Server: indiquez l’alias TNS, p. ex. `ORACLE_DB` (ou `ORCL`)
- Username: votre utilisateur Oracle (p. ex. `PDBADMIN` ou votre utilisateur applicatif)
- Password: votre mot de passe Oracle
- Database: laissez vide, ou répétez l’alias si Adminer le demande (certaines versions acceptent l’alias dans Server ou
  Database)

Si le nom de service PDB Oracle ou l’hôte diffèrent:

- Éditez `adminer/tns/tnsnames.ora` et adaptez `HOST` et/ou `SERVICE_NAME`.
- Recréez/redémarrez Adminer pour prendre en compte la modification:
  ```
  docker compose up -d --force-recreate adminer
  ```