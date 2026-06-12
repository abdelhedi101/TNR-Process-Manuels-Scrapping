"""
database.py — Configuration de la base de données SQLite

SQLAlchemy est l'outil qui fait le lien entre Python et la base de données.
On n'écrit pas de SQL à la main — SQLAlchemy le génère pour nous.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# L'URL de notre base de données.
# "sqlite:///megara.db" signifie : fichier SQLite nommé megara.db
# dans le dossier backend/
DATABASE_URL = "sqlite:///./megara.db"

# Le "moteur" : c'est la connexion entre Python et le fichier SQLite
# check_same_thread=False est nécessaire pour que FastAPI puisse l'utiliser
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# SessionLocal : c'est ce qu'on ouvre pour lire/écrire dans la base de données
# (comme ouvrir un fichier avant de le lire)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base : toutes nos "tables" vont hériter de cette classe
class Base(DeclarativeBase):
    pass


def get_db():
    """
    Fonction utilitaire utilisée par FastAPI pour donner accès à la DB.
    Elle ouvre une session, la donne, puis la ferme automatiquement.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
