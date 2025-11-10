import datetime
import random
import sys

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy.orm import sessionmaker

from db import OracleManager, PostgresManager
from db.models import (
    Affectation,
    Benevole,
    Concert,
    Groupe,
    Partenaire,
    Scene,
    Sponsoring,
)

TOTAL_GROUPES = 500
TOTAL_SCENES = 50
TOTAL_BENEVOLES = 2000
TOTAL_PARTENAIRES = 100
TOTAL_CONCERTS = 5000
TOTAL_AFFECTATIONS = 15000
TOTAL_SPONSORINGS = 1000

fake = Faker("fr_FR")


STYLES_MUSIQUE = [
    "Rock",
    "Pop",
    "Electro",
    "Jazz",
    "Métal",
    "Classique",
    "Hip-Hop",
    "Reggae",
]
ROLES_BENEVOLE = ["Bar", "Accueil", "Sécurité", "Technique", "Catering", "VIP"]
TYPES_PARTENAIRE = ["Média", "Financier", "Boisson", "Matériel"]
POSTES_BENEVOLE = ["Manager", "Membre équipe", "Stagiaire", "Superviseur"]


def clear_data(session_maker):
    """Vide toutes les données des tables dans le bon ordre (respect des FK)."""
    print("Effacement des anciennes données...")
    with session_maker() as session:
        # Ordre inverse de la création
        session.query(Affectation).delete()
        session.query(Sponsoring).delete()
        session.query(Concert).delete()
        session.query(Groupe).delete()
        session.query(Scene).delete()
        session.query(Benevole).delete()
        session.query(Partenaire).delete()
        session.commit()
    print("Données effacées.")


def populate_data(session_maker, engine_name: str):
    print(f"Début du peuplement pour {engine_name}...")
    with session_maker() as session:
        print(f"  Génération de {TOTAL_GROUPES} groupes...")
        groupes = []
        for _ in range(TOTAL_GROUPES):
            groupes.append(
                Groupe(
                    nom_groupe=fake.company() + " " + fake.word().capitalize(),
                    style=random.choice(STYLES_MUSIQUE),
                    pays_origine=fake.country(),
                    nb_membres=random.randint(1, 10),
                )
            )

        print(f"  Génération de {TOTAL_SCENES} scènes...")
        scenes = []
        for i in range(TOTAL_SCENES):
            scenes.append(
                Scene(
                    nom_scene=f"Scène {fake.word().capitalize()} {i}",
                    emplacement=f"Zone {random.choice(['Nord', 'Sud', 'Est', 'Ouest'])}",
                    capacite=random.choice([1000, 5000, 10000, 25000, 50000]),
                )
            )

        print(f"  Génération de {TOTAL_BENEVOLES} bénévoles...")
        benevoles = []
        for _ in range(TOTAL_BENEVOLES):
            benevoles.append(
                Benevole(
                    nom=fake.last_name(),
                    prenom=fake.first_name(),
                    telephone=fake.phone_number(),
                    email=fake.email(),
                    poste=random.choice(POSTES_BENEVOLE),
                )
            )

        print(f"  Génération de {TOTAL_PARTENAIRES} partenaires...")
        partenaires = []
        for _ in range(TOTAL_PARTENAIRES):
            partenaires.append(
                Partenaire(
                    nom_partenaire=fake.company(),
                    type_partenaire=random.choice(TYPES_PARTENAIRE),
                )
            )

        # Commit pour obtenir les IDs
        print("  Commit des entités de base...")
        session.add_all(groupes)
        session.add_all(scenes)
        session.add_all(benevoles)
        session.add_all(partenaires)
        session.commit()
        print("  [OK] Entités de base créées.")

        # --- 2. Créer les concerts (dépendent des groupes et scènes) ---
        print(f"  Génération de {TOTAL_CONCERTS} concerts...")
        concerts = []
        for _ in range(TOTAL_CONCERTS):
            start_time = fake.date_time_between(
                start_date=datetime.datetime(2025, 7, 1),
                end_date=datetime.datetime(2025, 7, 5),
            )
            concerts.append(
                Concert(
                    date_concert=start_time.date(),
                    heure_debut=start_time,
                    duree=datetime.timedelta(minutes=random.choice([45, 60, 90, 120])),
                    id_scene=random.choice(scenes).id_scene,
                    id_groupe=random.choice(groupes).id_groupe,
                )
            )
        session.add_all(concerts)
        session.commit()
        print("  [OK] Concerts créés.")

        # --- 3. Créer les affectations et sponsorings (dépendent des concerts) ---
        print(f"  Génération de {TOTAL_AFFECTATIONS} affectations...")
        affectations_set = set()
        while len(affectations_set) < TOTAL_AFFECTATIONS:
            # Assurer des paires (benevole, concert) uniques
            affectations_set.add(
                (
                    random.choice(benevoles).id_benevole,
                    random.choice(concerts).id_concert,
                )
            )

        affectations = [
            Affectation(
                id_benevole=b_id, id_concert=c_id, role=random.choice(ROLES_BENEVOLE)
            )
            for b_id, c_id in affectations_set
        ]
        session.add_all(affectations)

        print(f"  Génération de {TOTAL_SPONSORINGS} sponsorings...")
        sponsorings_set = set()
        while len(sponsorings_set) < TOTAL_SPONSORINGS:
            # Assurer des paires (partenaire, concert) uniques
            sponsorings_set.add(
                (
                    random.choice(partenaires).id_partenaire,
                    random.choice(concerts).id_concert,
                )
            )

        sponsorings = [
            Sponsoring(
                id_partenaire=p_id,
                id_concert=c_id,
                montant=random.choice([500, 1000, 5000, 10000]),
            )
            for p_id, c_id in sponsorings_set
        ]
        session.add_all(sponsorings)

        session.commit()
        print("  [OK] Relations créées.")
        print(f"[TERMINE] Peuplement réussi pour {engine_name}.")


def main():
    load_dotenv()

    # --- PostgreSQL ---
    try:
        pg_manager = PostgresManager.from_env()
        pg_session_maker = sessionmaker(bind=pg_manager.engine)
        # On vide avant de remplir
        clear_data(pg_session_maker)
        populate_data(pg_session_maker, "PostgreSQL")
    except Exception as e:
        print(f"Erreur lors du peuplement de PostgreSQL: {e}", file=sys.stderr)

    # --- Oracle ---
    try:
        ora_manager = OracleManager.from_env()
        ora_session_maker = sessionmaker(bind=ora_manager.engine)
        # On vide avant de remplir
        clear_data(ora_session_maker)
        populate_data(ora_session_maker, "Oracle")
    except Exception as e:
        print(f"Erreur lors du peuplement d'Oracle: {e}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    main()
