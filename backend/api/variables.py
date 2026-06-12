"""
api/variables.py — Lecture/écriture des fichiers de variables de saisie

Endpoints :
  GET /api/variables/{client}/{process}  → lire les variables du processus
  PUT /api/variables/{client}/{process}  → sauvegarder les modifications
"""
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/variables", tags=["Variables"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VARIABLE_FILES: dict[tuple, str] = {
    ("awb",  "saisie"):          "variable_saisies/Instruction_Client_awb.txt",
    ("awb",  "creation_entite"): "variable_saisies/Creation_role_entite_awb.txt",
    ("awb",  "process_rl"):      "variable_saisies/Process_RL_awb.txt",
    ("awb",  "ost"):             "variable_saisies/ost_awb.txt",
    ("bmce", "saisie"):          "variable_saisies/Instruction_Client_BMCE.txt",
    ("cdg",  "saisie"):          "variable_saisies/Instruction_Client_CDG.txt",
}


class VariableEntry(BaseModel):
    key: str
    value: str
    required: bool = False


class VariablesResponse(BaseModel):
    client: str
    process: str
    file_path: str
    variables: List[VariableEntry]


class VariablesUpdate(BaseModel):
    variables: List[VariableEntry]


def _resolve(client: str, process: str) -> Path:
    rel = VARIABLE_FILES.get((client.lower(), process.lower()))
    if rel is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pas de fichier de variables pour {client}/{process}",
        )
    path = Path(PROJECT_ROOT) / rel
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable : {rel}")
    return path


def _parse(path: Path) -> List[VariableEntry]:
    entries: List[VariableEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip()
            entries.append(VariableEntry(
                key=key,
                value=value.strip(),
                required=key.endswith("*"),
            ))
    return entries


def _write(path: Path, variables: List[VariableEntry]) -> None:
    new_values = {e.key: e.value for e in variables}
    original = path.read_text(encoding="utf-8").splitlines(keepends=True)
    result = []
    seen: set[str] = set()
    for line in original:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            result.append(line)
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in new_values and key not in seen:
                result.append(f"{key} = {new_values[key]}\n")
                seen.add(key)
                continue
        result.append(line)
    path.write_text("".join(result), encoding="utf-8")


@router.get("/{client}/{process}", response_model=VariablesResponse)
def get_variables(client: str, process: str):
    path = _resolve(client, process)
    rel  = VARIABLE_FILES.get((client.lower(), process.lower()), "")
    return VariablesResponse(
        client=client,
        process=process,
        file_path=rel,
        variables=_parse(path),
    )


@router.put("/{client}/{process}")
def update_variables(client: str, process: str, body: VariablesUpdate):
    path = _resolve(client, process)
    _write(path, body.variables)
    return {"message": "Variables sauvegardées", "count": len(body.variables)}
