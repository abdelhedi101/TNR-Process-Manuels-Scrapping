"""
main.py — Point d'entrée du serveur FastAPI

Pour démarrer le serveur, ouvre un terminal dans le dossier backend/ et tape :
    python -m uvicorn main:app --reload --port 8000

  --reload  : le serveur redémarre automatiquement quand tu modifies un fichier
  --port    : on écoute sur le port 8000

Une fois démarré, tu peux :
  - Voir la documentation interactive : http://localhost:8000/docs
  - Tester les endpoints : http://localhost:8000/api/clients
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from api.clients import router as clients_router
from api.executions import router as executions_router

# ---------------------------------------------------------------------------
# CRÉER L'APPLICATION FASTAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Megara TNR Platform",
    description="Plateforme web pour automatiser les processus TNR Megara (AWB, BMCE, CDG)",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS — Cross-Origin Resource Sharing
#
# Le navigateur bloque par défaut les appels d'une URL vers une autre.
# (Ex: le frontend sur localhost:5173 ne peut pas appeler localhost:8000)
# Ce middleware lève cette restriction pour notre frontend.
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # URLs du frontend
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DÉMARRAGE — créer les tables en base de données si elles n'existent pas
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup():
    """
    Ce code s'exécute une seule fois au démarrage du serveur.
    Il crée les tables dans megara.db si elles n'existent pas encore.
    """
    Base.metadata.create_all(bind=engine)
    print("[OK] Base de donnees initialisee")
    print("[OK] Serveur Megara TNR Platform demarre")
    print("[OK] Documentation disponible sur : http://localhost:8000/docs")


# ---------------------------------------------------------------------------
# BRANCHER LES ROUTERS — connecter les endpoints au serveur
# ---------------------------------------------------------------------------

# Les endpoints définis dans api/clients.py
app.include_router(clients_router)

# Les endpoints définis dans api/executions.py
app.include_router(executions_router)


# ---------------------------------------------------------------------------
# ENDPOINT DE SANTÉ — pour vérifier que le serveur tourne
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Megara TNR Platform — API opérationnelle", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}
