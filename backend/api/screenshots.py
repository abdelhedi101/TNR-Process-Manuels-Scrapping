"""
api/screenshots.py — Accès aux captures d'écran prises pendant un TNR

Endpoints :
  GET  /api/executions/{id}/screenshots           → liste les fichiers
  GET  /api/executions/{id}/screenshots/download  → télécharger tout en ZIP
  GET  /api/executions/{id}/screenshots/{path}    → servir une image
"""

import io
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

router = APIRouter(tags=["Screenshots"])

PROJECT_ROOT    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCREENSHOTS_BASE = Path(PROJECT_ROOT) / "screenshots"


def _exec_dir(execution_id: int) -> Path:
    return SCREENSHOTS_BASE / f"run_{execution_id}"


@router.get("/api/executions/{execution_id}/screenshots")
def list_screenshots(execution_id: int):
    """
    Retourne la liste des captures pour une exécution.
    Cherche récursivement tous les .png dans screenshots/run_{id}/
    """
    exec_dir = _exec_dir(execution_id)
    if not exec_dir.exists():
        return {"count": 0, "files": []}

    files = []
    for p in sorted(exec_dir.rglob("*.png"), key=lambda x: x.name):
        rel = p.relative_to(exec_dir)
        files.append({
            "name":  p.name,
            "path":  rel.as_posix(),   # ex: "AWB/megacommon/position/screen_123.png"
            "size":  p.stat().st_size,
        })

    return {"count": len(files), "files": files}


@router.get("/api/executions/{execution_id}/screenshots/download")
def download_screenshots(execution_id: int):
    """
    Crée un ZIP de toutes les captures et le renvoie en téléchargement.
    """
    exec_dir = _exec_dir(execution_id)

    if not exec_dir.exists():
        raise HTTPException(status_code=404, detail="Aucune capture trouvée pour cette exécution")

    files = list(exec_dir.rglob("*.png"))
    if not files:
        raise HTTPException(status_code=404, detail="Aucune capture PNG trouvée")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(files):
            # Chemin dans le ZIP = chemin relatif au dossier de l'exécution
            rel = fp.relative_to(exec_dir)
            zf.write(fp, rel.as_posix())
    buf.seek(0)

    filename = f"captures_exec_{execution_id}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/api/executions/{execution_id}/screenshots/{file_path:path}")
def get_screenshot(execution_id: int, file_path: str):
    """
    Sert une capture individuelle (pour l'affichage dans le navigateur).
    Protection contre les path traversal (ex: ../../etc/passwd).
    """
    exec_dir = _exec_dir(execution_id).resolve()
    target   = (exec_dir / file_path).resolve()

    # Sécurité : interdire toute sortie du dossier autorisé
    if not str(target).startswith(str(exec_dir)):
        raise HTTPException(status_code=403, detail="Accès interdit")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Capture introuvable")

    return FileResponse(str(target), media_type="image/png")
