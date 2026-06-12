"""
api/executions.py — Lancer, suivre et consulter les exécutions

Endpoints disponibles :
  POST   /api/executions              → lancer une nouvelle exécution
  GET    /api/executions              → historique de toutes les exécutions
  GET    /api/executions/{id}         → détail d'une exécution
  DELETE /api/executions/{id}         → arrêter une exécution en cours
  WS     /ws/executions/{id}/logs     → logs en temps réel (WebSocket)
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Execution, ExecutionLog

router = APIRouter(tags=["Executions"])

# Dictionnaire qui garde en mémoire les processus actifs
# Clé = execution_id, Valeur = le process asyncio en cours
active_processes: dict[int, asyncio.subprocess.Process] = {}


# ---------------------------------------------------------------------------
# SCHÉMAS — définissent la forme des données attendues / renvoyées
# ---------------------------------------------------------------------------

class ExecutionCreate(BaseModel):
    """
    Données que le frontend envoie pour lancer une exécution.
    Exemple de JSON envoyé :
      { "client": "awb", "module": "megacustody", "process": "saisie" }
    """
    client:  str
    module:  str
    process: str


class ExecutionResponse(BaseModel):
    """
    Données qu'on renvoie au frontend pour décrire une exécution.
    """
    id:         int
    client:     str
    module:     str
    process:    str
    status:     str
    started_at: datetime
    ended_at:   Optional[datetime]
    error_msg:  Optional[str]

    class Config:
        from_attributes = True  # permet de convertir un objet SQLAlchemy en JSON


# ---------------------------------------------------------------------------
# MAPPING — quel script Python lancer selon le process demandé
# ---------------------------------------------------------------------------

# Chemin du dossier racine du projet (Scrapping/)
# __file__ = backend/api/executions.py → on remonte 3 niveaux
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCRIPT_MAP = {
    # (client, process) → chemin vers le script Python
    ("awb",  "saisie"):     os.path.join(PROJECT_ROOT, "saisie_awb.py"),
    ("bmce", "saisie"):     os.path.join(PROJECT_ROOT, "saisie_bmce.py"),
    ("cdg",  "saisie"):     os.path.join(PROJECT_ROOT, "saisie_CDG.py"),
    ("awb",  "process_rl"): os.path.join(PROJECT_ROOT, "Process_RL_AWB.py"),
    ("cdg",  "process_rl"): os.path.join(PROJECT_ROOT, "Process_RL_CDG.py"),
    ("awb",  "swift"):      os.path.join(PROJECT_ROOT, "Process_Swift_AWB.py"),
    ("awb",  "ost"):        os.path.join(PROJECT_ROOT, "ost_awb.py"),
    ("awb",  "tnr"):        os.path.join(PROJECT_ROOT, "non_regression_awb.py"),
    ("bmce", "tnr"):        os.path.join(PROJECT_ROOT, "non_regression_bmce.py"),
    ("cdg",  "tnr"):        os.path.join(PROJECT_ROOT, "non_regression_cdg.py"),
    ("awb",  "diagnostic"): os.path.join(PROJECT_ROOT, "diag_megara.py"),
}

# ---------------------------------------------------------------------------
# VARIABLES D'ENVIRONNEMENT PAR CLIENT/PROCESS
#
# Process_Swift_AWB.py lit ses paramètres depuis les variables d'env.
# On les définit ici pour chaque combinaison client/process.
# Les valeurs correspondent aux defaults déjà dans les scripts,
# mais les rendre explicites ici permet de les surcharger facilement.
# ---------------------------------------------------------------------------

ENV_CONFIG: dict[tuple, dict] = {
    # ── AWB SWIFT ──────────────────────────────────────────────────────────
    # Variables lues par Process_Swift_AWB.py
    ("awb", "swift"): {
        # Auth MegaCustody UI (Playwright)
        "AUTH_USERNAME":       "migration",
        "AUTH_PASSWORD":       "Vermeg+123",
        "AUTH_DOMAIN":         "awb",
        "MEGACUSTODY_URL":     "http://10.1.140.244:9082/MegaCustody/login.jsp",
        # SFTP AWB (WinSCP)
        "AWB_HOST":            "10.1.140.244",
        "AWB_USER":            "server",
        "AWB_PASSWORD":        "server@244",
        "AWB_PORT":            "22",
        "REMOTE_ALLIANCE_PATH": "/Megara/IODevices/MegaCustody/IN/ALLIANCE",
        # Timing (en secondes)
        "ABSORPTION_TIMEOUT":  "1800",   # 30 min max pour qu'un fichier soit absorbé
        "ABSORPTION_INTERVAL": "15",     # poll toutes les 15 secondes
        "MIC_POLL_TIMEOUT":    "180",    # 3 min max pour trouver l'instruction créée
        "MIC_POLL_INTERVAL":   "10",     # retry toutes les 10 secondes
    },

    # ── AWB SAISIE ──────────────────────────────────────────────────────────
    ("awb", "saisie"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "awb",
        "AUTH_TYPE":       "standard",
        "MODULE_URL":      "http://10.1.140.244:9082/MegaCustody/login.jsp",
    },

    # ── AWB PROCESS RL ──────────────────────────────────────────────────────
    ("awb", "process_rl"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "awb",
        "AUTH_TYPE":       "standard",
        "MODULE_URL":      "http://10.1.140.244:9082/MegaCustody/login.jsp",
        "MEGACOMMON_URL":  "http://10.1.140.244:9080/MegaCommon/login.jsp",
    },

    # ── AWB OST ─────────────────────────────────────────────────────────────
    ("awb", "ost"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "awb",
        "AUTH_TYPE":       "standard",
        "MODULE_URL":      "http://10.1.140.244:9081/MegaCor/login.jsp",
    },

    # ── AWB TNR ─────────────────────────────────────────────────────────────
    ("awb", "tnr"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "awb",
        "AUTH_TYPE":       "standard",
    },

    # ── BMCE SAISIE ─────────────────────────────────────────────────────────
    ("bmce", "saisie"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "BMCE BANK",
        "AUTH_TYPE":       "standard",
        "MODULE_URL":      "http://10.1.146.163:9082/MegaCustody/login.jsp",
    },

    # ── BMCE TNR ─────────────────────────────────────────────────────────────
    ("bmce", "tnr"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "BMCE BANK",
        "AUTH_TYPE":       "standard",
    },

    # ── CDG SAISIE ──────────────────────────────────────────────────────────
    ("cdg", "saisie"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "CDG CAPITAL",
        "AUTH_TYPE":       "keycloak",
        "MODULE_URL":      "https://10.1.140.42/MegaCustody/",
    },

    # ── CDG PROCESS RL ──────────────────────────────────────────────────────
    ("cdg", "process_rl"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "CDG CAPITAL",
        "AUTH_TYPE":       "keycloak",
        "MODULE_URL":      "https://10.1.140.42/MegaCustody/",
        "MEGACOMMON_URL":  "https://10.1.140.42/MegaCommon/",
    },

    # ── CDG TNR ─────────────────────────────────────────────────────────────
    ("cdg", "tnr"): {
        "AUTH_USERNAME":   "migration",
        "AUTH_PASSWORD":   "Vermeg+123",
        "AUTH_DOMAIN":     "CDG CAPITAL",
        "AUTH_TYPE":       "keycloak",
    },
}


# ---------------------------------------------------------------------------
# ENDPOINTS HTTP
# ---------------------------------------------------------------------------

@router.post("/api/executions", response_model=ExecutionResponse, status_code=201)
async def create_execution(body: ExecutionCreate, db: Session = Depends(get_db)):
    """
    Crée une exécution en base de données et démarre le script en arrière-plan.

    Le frontend envoie : { "client": "awb", "module": "megacustody", "process": "saisie" }
    On répond : les détails de l'exécution créée (avec son id)
    """
    # 1. Vérifier qu'un script existe pour cette combinaison client/process
    script_key = (body.client, body.process)
    script_path = SCRIPT_MAP.get(script_key)

    if not script_path:
        raise HTTPException(
            status_code=400,
            detail=f"Aucun script trouve pour client='{body.client}' process='{body.process}'"
        )

    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail=f"Le fichier script est introuvable : {script_path}"
        )

    # 2. Créer la ligne dans la table 'executions'
    execution = Execution(
        client=body.client,
        module=body.module,
        process=body.process,
        status="pending",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    # 3. Lancer le script en arrière-plan
    # async def + asyncio.create_task = la fonction tourne sans bloquer la réponse
    asyncio.create_task(
        _run_script(execution.id, script_path, body.module, body.client, body.process)
    )

    return execution


@router.get("/api/executions", response_model=list[ExecutionResponse])
def list_executions(
    client: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retourne l'historique des exécutions.
    Paramètres optionnels : ?client=awb&status=success&limit=20
    """
    query = db.query(Execution).order_by(Execution.started_at.desc())

    if client:
        query = query.filter(Execution.client == client)
    if status:
        query = query.filter(Execution.status == status)

    return query.limit(limit).all()


@router.get("/api/executions/{execution_id}", response_model=ExecutionResponse)
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    """
    Retourne le détail d'une exécution spécifique.
    """
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Exécution introuvable")
    return execution


@router.get("/api/executions/{execution_id}/logs")
def get_logs(execution_id: int, db: Session = Depends(get_db)):
    """
    Retourne les logs d'une exécution (version HTTP — alternative au WebSocket).
    Utile pour consulter les logs d'une exécution terminée.
    """
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Exécution introuvable")

    logs = (
        db.query(ExecutionLog)
        .filter(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.timestamp.asc())
        .all()
    )

    return [
        {
            "id":        log.id,
            "level":     log.level,
            "message":   log.message,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


@router.delete("/api/executions/{execution_id}")
def stop_execution(execution_id: int, db: Session = Depends(get_db)):
    """
    Arrête une exécution en cours.
    """
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Exécution introuvable")

    if execution.status != "running":
        raise HTTPException(status_code=400, detail=f"L'exécution n'est pas en cours (status: {execution.status})")

    # Tuer le process système si il tourne encore
    process = active_processes.get(execution_id)
    if process:
        process.kill()
        del active_processes[execution_id]

    # Mettre à jour la base de données
    execution.status = "stopped"
    execution.ended_at = datetime.utcnow()
    db.commit()

    return {"message": "Exécution arrêtée"}


# ---------------------------------------------------------------------------
# WEBSOCKET — logs en temps réel
# ---------------------------------------------------------------------------

@router.websocket("/ws/executions/{execution_id}/logs")
async def websocket_logs(websocket: WebSocket, execution_id: int, db: Session = Depends(get_db)):
    """
    WebSocket pour recevoir les logs en temps réel.

    Le frontend se connecte à cette URL et reçoit chaque ligne de log
    au fur et à mesure que le script tourne.

    Format des messages JSON envoyés :
      { "type": "log",  "level": "INFO", "message": "...", "timestamp": "..." }
      { "type": "done", "status": "success" }  ← quand c'est fini
    """
    await websocket.accept()  # accepter la connexion WebSocket

    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        await websocket.send_json({"type": "error", "message": "Exécution introuvable"})
        await websocket.close()
        return

    try:
        # Envoyer les logs déjà existants (pour une exécution déjà commencée)
        existing_logs = (
            db.query(ExecutionLog)
            .filter(ExecutionLog.execution_id == execution_id)
            .order_by(ExecutionLog.timestamp.asc())
            .all()
        )
        for log in existing_logs:
            await websocket.send_json({
                "type":      "log",
                "level":     log.level,
                "message":   log.message,
                "timestamp": log.timestamp.isoformat(),
            })

        # Si l'exécution est déjà terminée, envoyer le message de fin et fermer
        if execution.status in ("success", "error", "stopped"):
            await websocket.send_json({"type": "done", "status": execution.status})
            await websocket.close()
            return

        # Sinon, attendre les nouveaux logs (polling toutes les 0.5 secondes)
        last_log_id = existing_logs[-1].id if existing_logs else 0
        while True:
            db.expire_all()  # forcer SQLAlchemy à relire depuis la DB
            execution = db.query(Execution).filter(Execution.id == execution_id).first()

            # Récupérer les nouveaux logs depuis le dernier envoyé
            new_logs = (
                db.query(ExecutionLog)
                .filter(
                    ExecutionLog.execution_id == execution_id,
                    ExecutionLog.id > last_log_id
                )
                .order_by(ExecutionLog.timestamp.asc())
                .all()
            )

            for log in new_logs:
                await websocket.send_json({
                    "type":      "log",
                    "level":     log.level,
                    "message":   log.message,
                    "timestamp": log.timestamp.isoformat(),
                })
                last_log_id = log.id

            # Si l'exécution est terminée, envoyer "done" et fermer
            if execution.status in ("success", "error", "stopped"):
                await websocket.send_json({"type": "done", "status": execution.status})
                break

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass  # le navigateur a fermé la connexion, c'est normal
    finally:
        await websocket.close()


# ---------------------------------------------------------------------------
# FONCTION INTERNE — exécuter le script Python en arrière-plan
# ---------------------------------------------------------------------------

async def _run_script(execution_id: int, script_path: str, module: str, client: str = "", process: str = ""):
    """
    Lance le script Python en sous-processus et capture ses logs ligne par ligne.
    Cette fonction tourne en arrière-plan — elle ne bloque pas le serveur.
    """
    from database import SessionLocal
    db = SessionLocal()

    try:
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        execution.status = "running"
        db.commit()

        # Dossier de screenshots propre à cette exécution
        screenshot_dir = os.path.join(PROJECT_ROOT, "screenshots", f"run_{execution_id}")
        os.makedirs(screenshot_dir, exist_ok=True)

        # Partir des variables d'env système, puis ajouter les nôtres
        env = os.environ.copy()

        # PYTHONIOENCODING=utf-8 : évite les erreurs sur les caractères
        # spéciaux dans les logs (→, ✓, ⚠, accents, etc.)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"]       = "1"

        # Variables communes à tous les scripts
        env["MODULE_SLUG"]    = module
        env["SCREENSHOT_DIR"] = screenshot_dir

        # Variables spécifiques au client/process (depuis ENV_CONFIG)
        specific_env = ENV_CONFIG.get((client, process), {})
        env.update(specific_env)

        # Si le module est précisé et qu'on a une URL dans l'env config, l'utiliser
        # (certains scripts lisent MODULE_URL pour savoir où se connecter)
        if "MODULE_URL" not in specific_env and module:
            env["MODULE_SLUG"] = module

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            script_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=PROJECT_ROOT,
        )

        # Garder une référence pour pouvoir l'arrêter si besoin
        active_processes[execution_id] = proc

        # Lire les logs ligne par ligne au fur et à mesure
        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue

            # Déterminer le niveau du log
            level = "INFO"
            upper = text.upper()
            if "ERROR" in upper or "ERREUR" in upper:
                level = "ERROR"
            elif "WARNING" in upper or "WARN" in upper:
                level = "WARNING"

            db.add(ExecutionLog(execution_id=execution_id, level=level, message=text))
            db.commit()

        await proc.wait()

        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if proc.returncode == 0:
            execution.status = "success"
        else:
            execution.status = "error"
            execution.error_msg = f"Le script a termine avec le code {proc.returncode}"

        execution.ended_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        # En cas d'erreur inattendue, on enregistre l'erreur
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if execution:
            execution.status = "error"
            execution.error_msg = str(e)
            execution.ended_at = datetime.utcnow()
            db.commit()
    finally:
        if execution_id in active_processes:
            del active_processes[execution_id]
        db.close()
