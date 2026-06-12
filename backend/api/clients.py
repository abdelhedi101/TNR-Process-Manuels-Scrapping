"""
api/clients.py — Endpoints pour les clients et leurs modules

Endpoints disponibles :
  GET /api/clients                         → liste tous les clients (AWB, BMCE, CDG)
  GET /api/clients/{client_slug}/modules   → liste les modules d'un client
  GET /api/clients/{client_slug}/processes → liste les processus disponibles
"""

from fastapi import APIRouter

# APIRouter : un "sous-menu" de routes qu'on branche dans main.py
router = APIRouter(prefix="/api/clients", tags=["Clients"])


# ---------------------------------------------------------------------------
# DONNÉES EN DUR — la configuration de nos 3 clients
# Plus tard, ces données viendront de la base de données.
# Pour l'instant on les écrit directement ici pour commencer simplement.
# ---------------------------------------------------------------------------

CLIENTS = {
    "awb": {
        "slug": "awb",
        "name": "AWB",
        "full_name": "Attijariwafa Bank",
        "auth_type": "standard",
        "base_ip": "10.1.140.244",
        "modules": [
            {"slug": "megacommon",  "name": "MegaCommon",  "port": 9080, "url": "http://10.1.140.244:9080/MegaCommon/login.jsp"},
            {"slug": "megacor",     "name": "MegaCor",     "port": 9081, "url": "http://10.1.140.244:9081/MegaCor/login.jsp"},
            {"slug": "megacustody", "name": "MegaCustody", "port": 9082, "url": "http://10.1.140.244:9082/MegaCustody/login.jsp"},
            {"slug": "megatrade",   "name": "MegaTrade",   "port": 9083, "url": "http://10.1.140.244:9083/MegaTrade/WebApp.jsp"},
            {"slug": "megaissuer",  "name": "MegaIssuer",  "port": 9084, "url": "http://10.1.140.244:9084/MegaIssuer/WebApp.jsp"},
        ],
    },
    "bmce": {
        "slug": "bmce",
        "name": "BMCE",
        "full_name": "BMCE Bank",
        "auth_type": "standard",
        "base_ip": "10.1.146.163",
        "modules": [
            {"slug": "megacommon",     "name": "MegaCommon",     "port": 9080, "url": "http://10.1.146.163:9080/MegaCommon/login.jsp"},
            {"slug": "megacor",        "name": "MegaCor",        "port": 9081, "url": "http://10.1.146.163:9081/MegaCor/login.jsp"},
            {"slug": "megacustody",    "name": "MegaCustody",    "port": 9082, "url": "http://10.1.146.163:9082/MegaCustody/login.jsp"},
            {"slug": "megalend",       "name": "MegaLend",       "port": 9083, "url": "http://10.1.146.163:9083/MegaLend/WebApp.jsp"},
            {"slug": "megatrade",      "name": "MegaTrade",      "port": 9084, "url": "http://10.1.146.163:9084/MegaTrade/WebApp.jsp"},
            {"slug": "megaaccounting", "name": "MegaAccounting", "port": 9085, "url": "http://10.1.146.163:9085/MegaAccounting/WebApp.jsp"},
            {"slug": "megacompliance", "name": "MegaCompliance", "port": 9086, "url": "http://10.1.146.163:9086/MegaCompliance/WebApp.jsp"},
        ],
    },
    "cdg": {
        "slug": "cdg",
        "name": "CDG",
        "full_name": "CDG Capital",
        "auth_type": "keycloak",
        "base_ip": "10.1.140.42",
        "modules": [
            {"slug": "megacommon",     "name": "MegaCommon",     "port": 443, "url": "https://10.1.140.42/MegaCommon/login.jsp"},
            {"slug": "megacor",        "name": "MegaCor",        "port": 443, "url": "https://10.1.140.42/MegaCor/login.jsp"},
            {"slug": "megacustody",    "name": "MegaCustody",    "port": 443, "url": "https://10.1.140.42/MegaCustody/"},
            {"slug": "megatrade",      "name": "MegaTrade",      "port": 443, "url": "https://10.1.140.42/MegaTrade/WebApp.jsp"},
            {"slug": "megacompliance", "name": "MegaCompliance", "port": 443, "url": "https://10.1.140.42/MegaCompliance/WebApp.jsp"},
            {"slug": "megaaccounting", "name": "MegaAccounting", "port": 443, "url": "https://10.1.140.42/MegaAccounting/WebApp.jsp"},
        ],
    },
}

# Catalogue complet de tous les processus possibles
ALL_PROCESSES = {
    "saisie":     {"slug": "saisie",     "name": "Saisie d'instructions",       "description": "Remplissage automatique des formulaires clients"},
    "process_rl": {"slug": "process_rl", "name": "Reglement / Livraison",       "description": "Appariement et denouement des instructions"},
    "swift":      {"slug": "swift",      "name": "Injection SWIFT",             "description": "Upload MT54X, MT548, MT54Y via SFTP"},
    "ost":        {"slug": "ost",        "name": "Operations sur Titres (OST)", "description": "Dividendes et paiements d'interets"},
    "tnr":        {"slug": "tnr",        "name": "Non-Regression (TNR)",        "description": "Tests complets de navigation + screenshots"},
    "diagnostic": {"slug": "diagnostic", "name": "Diagnostic infra",            "description": "Verification WebSphere et IODevice ALLIANCE"},
}

# Processus disponibles PAR CLIENT — uniquement ceux qui ont un script correspondant
CLIENT_PROCESSES = {
    "awb":  ["saisie", "process_rl", "swift", "ost", "tnr", "diagnostic"],
    "bmce": ["saisie", "tnr"],
    "cdg":  ["saisie", "process_rl", "tnr"],
}


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/")
def list_clients():
    """
    Retourne la liste de tous les clients.
    Le frontend appellera cette URL pour afficher AWB / BMCE / CDG.
    """
    # On retourne une liste simplifiée (sans les modules dedans)
    return [
        {
            "slug":      c["slug"],
            "name":      c["name"],
            "full_name": c["full_name"],
            "auth_type": c["auth_type"],
        }
        for c in CLIENTS.values()
    ]


@router.get("/{client_slug}/modules")
def list_modules(client_slug: str):
    """
    Retourne les modules d'un client spécifique.
    Exemple : GET /api/clients/awb/modules → liste les 5 modules AWB
    """
    # On vérifie que le client existe
    if client_slug not in CLIENTS:
        # 404 = "non trouvé"
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Client '{client_slug}' inconnu")

    return CLIENTS[client_slug]["modules"]


@router.get("/{client_slug}/processes")
def list_processes(client_slug: str):
    """
    Retourne UNIQUEMENT les processus disponibles pour ce client.
    AWB  → saisie, process_rl, swift, ost, tnr, diagnostic
    BMCE → saisie, tnr
    CDG  → saisie, process_rl, tnr
    """
    if client_slug not in CLIENTS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Client '{client_slug}' inconnu")

    slugs_disponibles = CLIENT_PROCESSES.get(client_slug, [])
    return [ALL_PROCESSES[slug] for slug in slugs_disponibles if slug in ALL_PROCESSES]
