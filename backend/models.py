"""
models.py — Définition des tables de la base de données

Chaque classe = une table dans megara.db
Chaque attribut = une colonne dans cette table
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class Execution(Base):
    """
    Table 'executions' — une ligne par exécution lancée.

    Exemple d'une ligne :
      id=1, client="awb", module="megacustody", process="saisie",
      status="running", started_at=2026-06-11 10:00:00
    """
    __tablename__ = "executions"

    # Colonnes de la table
    id         = Column(Integer, primary_key=True, index=True)  # numéro unique auto-incrémenté
    client     = Column(String, nullable=False)   # "awb", "bmce", "cdg"
    module     = Column(String, nullable=False)   # "megacustody", "megacor", etc.
    process    = Column(String, nullable=False)   # "saisie", "process_rl", "swift", "ost", "tnr"
    status     = Column(String, default="pending") # "pending", "running", "success", "error"
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at   = Column(DateTime, nullable=True)  # vide tant que pas terminé
    error_msg  = Column(Text, nullable=True)       # message d'erreur si échec

    # Relation : une exécution a plusieurs logs
    # (comme un dossier qui contient des fichiers)
    logs = relationship("ExecutionLog", back_populates="execution")


class ExecutionLog(Base):
    """
    Table 'execution_logs' — une ligne par message de log.

    Exemple d'une ligne :
      id=42, execution_id=1, level="INFO",
      message="Navigation vers MegaCustody...", timestamp=2026-06-11 10:00:05
    """
    __tablename__ = "execution_logs"

    id           = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)  # lien vers la table executions
    level        = Column(String, default="INFO")   # "INFO", "WARNING", "ERROR"
    message      = Column(Text, nullable=False)      # le texte du log
    timestamp    = Column(DateTime, default=datetime.utcnow)

    # Relation inverse : ce log appartient à une exécution
    execution = relationship("Execution", back_populates="logs")
