from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Interval,
    MetaData,
    Numeric,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Keep names short and deterministic for constraints (Oracle 30 char limit)
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


# Groupe (IdGroupe, NomGroupe, Style, PaysOrigine, NbMembres)
class Groupe(Base):
    __tablename__ = "groupe"

    id_groupe: Mapped[int] = mapped_column("id_groupe", Integer, primary_key=True)
    nom_groupe: Mapped[str] = mapped_column("nom_groupe", String(255), nullable=False)
    style: Mapped[Optional[str]] = mapped_column(String(100))
    pays_origine: Mapped[Optional[str]] = mapped_column("pays_origine", String(100))
    nb_membres: Mapped[Optional[int]] = mapped_column("nb_membres", Integer)

    concerts: Mapped[list[Concert]] = relationship(back_populates="groupe")


# Scene (IdScene, NomScene, Emplacement, Capacite)


class Scene(Base):
    __tablename__ = "scene"

    id_scene: Mapped[int] = mapped_column("id_scene", Integer, primary_key=True)
    nom_scene: Mapped[str] = mapped_column("nom_scene", String(255), nullable=False)
    emplacement: Mapped[Optional[str]] = mapped_column(String(255))
    capacite: Mapped[Optional[int]] = mapped_column(Integer)

    concerts: Mapped[list[Concert]] = relationship(back_populates="scene")


# Concert (IdConcert, DateConcert, HeureDebut, Duree, #IdScene, #IdGroupe)


class Concert(Base):
    __tablename__ = "concert"

    id_concert: Mapped[int] = mapped_column("id_concert", Integer, primary_key=True)
    date_concert: Mapped[Optional[Date]] = mapped_column("date_concert", Date)
    heure_debut: Mapped[Optional[DateTime]] = mapped_column("heure_debut", DateTime)
    # Oracle n'a pas de type Interval identique; SQLAlchemy mappe à INTERVAL / INTERVAL DAY TO SECOND
    duree: Mapped[Optional[Interval]] = mapped_column(Interval, nullable=True)

    id_scene: Mapped[int] = mapped_column(
        "id_scene",
        Integer,
        ForeignKey("scene.id_scene", name="fk_concert_id_scene_scene"),
        nullable=False,
    )
    id_groupe: Mapped[int] = mapped_column(
        "id_groupe",
        Integer,
        ForeignKey("groupe.id_groupe", name="fk_concert_id_groupe_groupe"),
        nullable=False,
    )

    scene: Mapped[Scene] = relationship(back_populates="concerts")
    groupe: Mapped[Groupe] = relationship(back_populates="concerts")
    affectations: Mapped[list[Affectation]] = relationship(back_populates="concert")
    sponsorings: Mapped[list[Sponsoring]] = relationship(back_populates="concert")


# Benevole (IdBenevole, Nom, Prenom, Telephone, Email, Poste)


class Benevole(Base):
    __tablename__ = "benevole"

    id_benevole: Mapped[int] = mapped_column("id_benevole", Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    telephone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    poste: Mapped[Optional[str]] = mapped_column(String(100))

    affectations: Mapped[list[Affectation]] = relationship(back_populates="benevole")


# Affectation (#IdBenevole, #IdConcert, Role)


class Affectation(Base):
    __tablename__ = "affectation"

    id_benevole: Mapped[int] = mapped_column(
        "id_benevole",
        Integer,
        ForeignKey("benevole.id_benevole", name="fk_affect_id_benevole_benevole"),
        primary_key=True,
    )
    id_concert: Mapped[int] = mapped_column(
        "id_concert",
        Integer,
        ForeignKey("concert.id_concert", name="fk_affect_id_concert_concert"),
        primary_key=True,
    )
    role: Mapped[Optional[str]] = mapped_column(String(100))

    benevole: Mapped[Benevole] = relationship(back_populates="affectations")
    concert: Mapped[Concert] = relationship(back_populates="affectations")


# Partenaire (IdPartenaire, NomPartenaire, TypePartenaire)


class Partenaire(Base):
    __tablename__ = "partenaire"

    id_partenaire: Mapped[int] = mapped_column(
        "id_partenaire", Integer, primary_key=True
    )
    nom_partenaire: Mapped[str] = mapped_column(
        "nom_partenaire", String(255), nullable=False
    )
    type_partenaire: Mapped[Optional[str]] = mapped_column(
        "type_partenaire", String(100)
    )

    sponsorings: Mapped[list[Sponsoring]] = relationship(back_populates="partenaire")


# Sponsoring (#IdPartenaire, #IdConcert, Montant)


class Sponsoring(Base):
    __tablename__ = "sponsoring"

    id_partenaire: Mapped[int] = mapped_column(
        "id_partenaire",
        Integer,
        ForeignKey("partenaire.id_partenaire", name="fk_sponsor_id_part_partenaire"),
        primary_key=True,
    )
    id_concert: Mapped[int] = mapped_column(
        "id_concert",
        Integer,
        ForeignKey("concert.id_concert", name="fk_sponsor_id_concert_concert"),
        primary_key=True,
    )
    montant: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2))

    partenaire: Mapped[Partenaire] = relationship(back_populates="sponsorings")
    concert: Mapped[Concert] = relationship(back_populates="sponsorings")
