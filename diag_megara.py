"""
diag_megara.py
==============
Diagnostic + tentative de correction automatique pour l'IODevice ALLIANCE AWB.

Modes :
  python diag_megara.py          → diagnostic seul
  python diag_megara.py --fix    → diagnostic + tentative de redémarrage WebSphere
"""

import subprocess, tempfile, os, sys, time

winscp   = r"C:\Program Files (x86)\WinSCP\WinSCP.com"
open_cmd = "open sftp://server:server@244@10.1.140.244:22/ -hostkey=* -timeout=30"

ALLIANCE_DIR   = "/Megara/IODevices/MegaCustody/IN/ALLIANCE"
WAS_PROFILE    = "/opt/IBM/WebSphere/AppServer/profiles/MegaCustody01"
WAS_SERVER     = "MegaCustody01"
WAS_START      = f"{WAS_PROFILE}/bin/startServer.sh {WAS_SERVER}"
WAS_STOP       = f"{WAS_PROFILE}/bin/stopServer.sh {WAS_SERVER}"
WAS_STATUS     = f"{WAS_PROFILE}/bin/serverStatus.sh {WAS_SERVER}"
WAS_LOG        = f"{WAS_PROFILE}/logs/{WAS_SERVER}/SystemOut.log"

FIX_MODE = "--fix" in sys.argv


def run_winscp(script: str, timeout: int = 90) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(script)
        p = f.name
    r = subprocess.run([winscp, f"/script={p}"], capture_output=True, text=True, timeout=timeout)
    os.unlink(p)
    return r.stdout


# ── ÉTAPE 1 : Diagnostic ──────────────────────────────────────────────────────
print("=" * 60)
print("ÉTAPE 1 — DIAGNOSTIC")
print("=" * 60)

diag_script = "\n".join([
    open_cmd,
    # État du dossier ALLIANCE
    f"call echo '--- Contenu ALLIANCE ---'",
    f"call ls -la {ALLIANCE_DIR}/",
    # Statut du serveur WebSphere
    f"call echo '--- Statut WebSphere ---'",
    f"call {WAS_STATUS} 2>&1",
    # Processus Java/WebSphere actifs (limité)
    f"call echo '--- Processus WAS ---'",
    f"call ps -C java -o pid,args --no-headers 2>/dev/null | grep -i MegaCustody | head -5",
    # Dernières lignes de log (tail simple, pas de pipe grep pour éviter timeout)
    f"call echo '--- Fin du log SystemOut ---'",
    f"call tail -20 {WAS_LOG} 2>/dev/null",
    # Fichiers lock dans ALLIANCE uniquement (pas find récursif)
    f"call echo '--- Fichiers lock ALLIANCE ---'",
    f"call ls -la {ALLIANCE_DIR}/ 2>/dev/null",
    "close",
    "exit",
])

output = run_winscp(diag_script, timeout=180)
print(output)

# Analyse rapide
was_running   = "is STARTED" in output or "already running" in output.lower() or "port 8884" in output
was_stopped   = "is STOPPED" in output
session_error = "SESN0008E" in output
lock_files    = ".lock" in output or ".lck" in output
alliance_empty = "MT54X.swf" not in output and "MT548" not in output and "MT54Y" not in output

print("\n" + "=" * 60)
print("ANALYSE")
print("=" * 60)
print(f"  WebSphere démarré  : {'OUI ✓' if was_running else 'NON / INCONNU'}")
print(f"  WebSphere arrêté   : {'OUI ← PROBLÈME' if was_stopped else 'NON'}")
print(f"  ALLIANCE vide      : {'OUI ✓ (fichier absorbé)' if alliance_empty else 'NON — fichier en attente'}")
print(f"  Erreur session LDAP: {'OUI ← PROBLÈME' if session_error else 'NON'}")
print(f"  Fichiers lock      : {'OUI ← PROBLÈME' if lock_files else 'NON'}")


# ── ÉTAPE 2 : Correction automatique ─────────────────────────────────────────
if not FIX_MODE:
    print("\n" + "=" * 60)
    print("Pour tenter une correction automatique :")
    print("  python diag_megara.py --fix")
    print("=" * 60)
    sys.exit(0)

print("\n" + "=" * 60)
print("ÉTAPE 2 — CORRECTION AUTOMATIQUE")
print("=" * 60)

# Si WebSphere tourne déjà et ALLIANCE est vide → rien à faire
if was_running and alliance_empty:
    print("\n✓ WebSphere est démarré et ALLIANCE est vide.")
    print("  L'IODevice fonctionne correctement.")
    print("  Lance l'injection complète :")
    print("    python Process_Swift_AWB.py")
    sys.exit(0)

fix_commands = [open_cmd]

# 2a — Supprimer les fichiers lock s'ils existent
if lock_files:
    print("[FIX] Suppression des fichiers lock dans ALLIANCE ...")
    fix_commands += [
        "option batch continue",
        f"call find {ALLIANCE_DIR} -name '*.lock' -o -name '*.lck' -o -name '*.tmp' | xargs rm -f 2>/dev/null",
        "option batch abort",
    ]

# 2b — Redémarrer WebSphere seulement s'il est ARRÊTÉ
if was_stopped or (not was_running):
    print("[FIX] Démarrage de WebSphere MegaCustody01 ...")
    fix_commands.append(f"call {WAS_START} 2>&1")
    print("[FIX] Attente 30s pour le démarrage complet ...")
    fix_commands.append("call sleep 30")
else:
    print("[INFO] WebSphere déjà en cours — pas de redémarrage nécessaire.")

# 2c — Vérification finale
fix_commands += [
    f"call echo '--- Contenu ALLIANCE ---'",
    f"call ls -la {ALLIANCE_DIR}/",
    "close",
    "exit",
]

fix_output = run_winscp("\n".join(fix_commands), timeout=120)
print(fix_output)

# Résultat final
already_running_after = "already running" in fix_output.lower() or "port 8884" in fix_output
if "ADMU0508I" in fix_output or already_running_after or not fix_output.strip():
    print("\n✓ WebSphere opérationnel.")
    print("  Lance l'injection complète :")
    print("    python Process_Swift_AWB.py")
else:
    print("\n✗ Vérification manuelle nécessaire :")
    print("  http://10.1.140.244:9060/ibm/console")
    print("  Servers → MegaCustody01 → Restart")
