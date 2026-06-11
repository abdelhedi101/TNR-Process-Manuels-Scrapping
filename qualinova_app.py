import io
import hmac
import json
import os
import smtplib
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import uuid
import zipfile
from hashlib import sha256
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import List, Optional

import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Qualinova", page_icon="⚙️", layout="wide")

PROJECTS_DIR = Path("Projects")
ARTIFACTS_ROOT = Path("runs")
ARTIFACTS_ROOT.mkdir(exist_ok=True)
LOG_LOCK = threading.Lock()
SUBSCRIPTION_FILE = Path(".qualinova_subscription.json")
PAYMENT_PROOFS_DIR = Path("payment_proofs")
PAYMENT_PROOFS_DIR.mkdir(exist_ok=True)
PRO_PRICE_TND = 550
CMI_AMOUNT_MILLIMES = PRO_PRICE_TND * 1000
SUBSCRIPTION_CONTACT_EMAIL = "ahmedabdelhedi899@gmail.com"

# Configuration des projets
PROJECT_CONFIGS = {
    "CDG": {
        "modules": {
            "MegaCommon": "https://10.1.140.42/MegaCommon/",
            "MegaCustody": "https://10.1.140.42/MegaCustody/",
            "MegaCor": "https://10.1.140.42/MegaCor/",
            "MegaTrade": "https://10.1.140.42/MegaTrade/",
            "MegaCompliance": "https://10.1.140.42/MegaCompliance/",
            "MegaLend": "https://10.1.140.42/MegaLend/",
            "MegaAccounting": "https://10.1.140.42/MegaAccounting/",
        },
        "credentials": {
            "username": "migration",
            "password": "Vermeg+123",
            "domain": "CDG CAPITAL",
        },
        "auth_type": "keycloak"
    },
    "BMCE": {
        "modules": {
            "MegaCommon": "http://10.1.146.163:9080/MegaCommon/WebApp.html",
            "MegaCor": "http://10.1.146.163:9081/MegaCor/WebApp.html",
            "MegaCustody": "http://10.1.146.163:9082/MegaCustody/WebApp.html",
            "MegaLend": "http://10.1.146.163:9083/MegaLend/WebApp.html",
            "MegaTrade": "http://10.1.146.163:9084/MegaTrade/WebApp.html",
            "MegaAccounting": "http://10.1.146.163:9085/MegaAccounting/WebApp.html",
            "MegaCompliance": "http://10.1.146.163:9086/MegaCompliance/WebApp.html",
            "MegaIssuer": "http://10.1.146.163:9087/MegaIssuer/WebApp.html",
        },
        "credentials": {
            "username": "ADMINBMCE",
            "password": "1234",
            "domain": "BMCE BANK",
        },
        "auth_type": "standard"
    },
    "AWB": {
        "modules": {
            "MegaCommon": "http://10.1.140.244:9080/MegaCommon/login.jsp",
            "MegaCor": "http://10.1.140.244:9081/MegaCor/login.jsp",
            "MegaCustody": "http://10.1.140.244:9082/MegaCustody/login.jsp",
            "MegaTrade": "http://10.1.140.244:9083/MegaTrade/WebApp.jsp",
            "MegaIssuer": "http://10.1.140.244:9084/MegaIssuer/WebApp.jsp",
        },
        "credentials": {
            "username": "migration",
            "password": "Vermeg+123",
            "domain": "awb",
        },
        "auth_type": "standard"
    }
}

GLOBAL_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Manrope:wght@400;500;600&display=swap');
:root {
    --bg: #030712;
    --panel: #0e1727;
    --border: rgba(255, 255, 255, 0.12);
    --text: #e1e8ff;
    --muted: rgba(255, 255, 255, 0.68);
    --accent: #22c55e;
    font-family: 'Space Grotesk', 'Manrope', sans-serif;
}
body {
    background: radial-gradient(circle at top right, rgba(252, 161, 63, 0.16), transparent 40%),
        radial-gradient(circle at bottom left, rgba(99, 102, 241, 0.3), transparent 45%),
        var(--bg);
    color: var(--text);
    font-family: 'Space Grotesk', 'Manrope', sans-serif;
}
.block-container {
    padding: 2.2rem;
    border-radius: 28px;
    background: rgba(14, 23, 39, 0.9);
    box-shadow: 0 30px 80px rgba(7, 10, 25, 0.65);
    border: 1px solid var(--border);
}
.section-title {
    letter-spacing: 0.42rem;
    text-transform: uppercase;
    font-size: 1.1rem;
    color: var(--muted);
}
.player-shell {
    border-radius: 22px;
    background: #05070f;
    border: 1px solid rgba(255, 255, 255, 0.15);
    box-shadow: 0 20px 40px rgba(3, 7, 18, 0.6);
    padding: 0.5rem;
}
.video-frame {
    border-radius: 18px;
    overflow: hidden;
}
.video-frame video {
    width: 100%;
    border-radius: 18px;
}
.start-scroll-btn button {
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    color: #fff;
    border-radius: 16px;
    font-size: 1.1rem;
    font-weight: 600;
    border: none;
    padding: 0.9rem 2.8rem;
    box-shadow: 0 15px 35px rgba(37, 99, 235, 0.3);
}
.terminal-panel {
    border-radius: 18px;
    background: rgba(3, 7, 18, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 1rem;
    margin-top: 1rem;
    font-family: 'Space Grotesk', 'Manrope', monospace;
}
.terminal-panel pre {
    margin: 0;
    font-size: 0.85rem;
    color: #e1e8ff;
    max-height: 280px;
    overflow-y: auto;
}
.terminal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.6rem;
}
.status-pill {
    padding: 0.1rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.3rem;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
}
@media (max-width: 900px) {
    .block-container {
        padding: 1.5rem;
    }
}
</style>
"""

st.markdown(GLOBAL_STYLE, unsafe_allow_html=True)

if "qualinova_run" not in st.session_state:
    st.session_state["qualinova_run"] = {
        "status": "idle",
        "logs": [],
        "zip_bytes": None,
        "zip_name": "",
        "run_id": "",
        "artifact_path": "",
        "failure_count": 0,
        "thread": None,
    }

st.session_state["subscription_plan"] = "pro"


def load_subscription_plan() -> str:
    if not SUBSCRIPTION_FILE.exists():
        return "free"
    try:
        payload = json.loads(SUBSCRIPTION_FILE.read_text(encoding="utf-8"))
        plan = str(payload.get("plan", "free")).strip().lower()
        return "pro" if plan == "pro" else "free"
    except Exception:
        return "free"


def save_subscription_plan(plan: str, payment_ref: str = "", pending_payment_ref: str = "") -> None:
    payload = {
        "plan": "pro" if plan == "pro" else "free",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "payment_ref": payment_ref,
        "pending_payment_ref": pending_payment_ref,
    }
    SUBSCRIPTION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_subscription_state() -> dict:
    if not SUBSCRIPTION_FILE.exists():
        return {}
    try:
        return json.loads(SUBSCRIPTION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sign_cmi_payload(raw_value: str) -> str:
    secret = os.getenv("CMI_SHARED_SECRET", "").strip()
    if not secret:
        return ""
    return hmac.new(secret.encode("utf-8"), raw_value.encode("utf-8"), sha256).hexdigest()


def create_cmi_checkout_url(base_url: str) -> str:
    cmi_checkout_base_url = os.getenv("CMI_CHECKOUT_BASE_URL", "").strip()
    cmi_merchant_id = os.getenv("CMI_MERCHANT_ID", "").strip()
    if not cmi_checkout_base_url or not cmi_merchant_id:
        raise RuntimeError("CMI_CHECKOUT_BASE_URL and CMI_MERCHANT_ID are required")

    payment_ref = f"QLV-{uuid.uuid4().hex[:12].upper()}"
    success_url = f"{base_url}?checkout=success&payment_ref={payment_ref}"
    cancel_url = f"{base_url}?checkout=cancel&payment_ref={payment_ref}"

    signature_seed = f"{payment_ref}|{CMI_AMOUNT_MILLIMES}|TND|{cmi_merchant_id}"
    signature = _sign_cmi_payload(signature_seed)

    query = {
        "merchant_id": cmi_merchant_id,
        "amount": str(CMI_AMOUNT_MILLIMES),
        "currency": "TND",
        "payment_ref": payment_ref,
        "description": "Qualinova Pro Monthly Subscription",
        "return_url": success_url,
        "cancel_url": cancel_url,
    }
    if signature:
        query["signature"] = signature

    state = load_subscription_state()
    save_subscription_plan(state.get("plan", "free"), state.get("payment_ref", ""), payment_ref)
    return f"{cmi_checkout_base_url}?{urllib.parse.urlencode(query)}"


def verify_cmi_payment(payment_ref: str, return_status: str) -> bool:
    verify_url = os.getenv("CMI_VERIFY_URL", "").strip()
    if verify_url:
        api_key = os.getenv("CMI_API_KEY", "").strip()
        params = urllib.parse.urlencode({"payment_ref": payment_ref})
        request = urllib.request.Request(
            f"{verify_url}?{params}",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        status = str(payload.get("status", "")).lower()
        paid = bool(payload.get("paid", False))
        return paid or status in {"paid", "success", "authorized", "completed"}

    return return_status in {"paid", "success", "authorized", "completed"}


def process_checkout_return() -> Optional[str]:
    query_params = st.query_params
    checkout_status = str(query_params.get("checkout", "")).strip().lower()
    payment_ref = str(query_params.get("payment_ref", "")).strip()
    payment_status = str(query_params.get("payment_status", "success")).strip().lower()
    if not checkout_status:
        return None

    if checkout_status == "success" and payment_ref:
        try:
            state = load_subscription_state()
            pending_payment_ref = str(state.get("pending_payment_ref", "")).strip()
            if pending_payment_ref and pending_payment_ref != payment_ref:
                st.query_params.clear()
                return "Reference paiement invalide. Activation Pro refusee."

            if verify_cmi_payment(payment_ref, payment_status):
                st.session_state["subscription_plan"] = "pro"
                save_subscription_plan("pro", payment_ref, "")
                st.query_params.clear()
                return "Paiement confirme. Votre compte est maintenant en mode Pro."
            st.query_params.clear()
            return "Paiement non confirme. Le compte reste en mode Free."
        except Exception as exc:
            st.query_params.clear()
            return f"Verification paiement impossible: {exc}"

    if checkout_status == "cancel":
        state = load_subscription_state()
        save_subscription_plan(state.get("plan", "free"), state.get("payment_ref", ""), "")
        st.query_params.clear()
        return "Paiement annule. Le compte reste en mode Free."
    return None


def save_manual_proof(
    customer_name: str,
    customer_email: str,
    transfer_reference: str,
    uploaded_file,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(uploaded_file.name).suffix or ".bin"
    safe_ref = slugify_label(transfer_reference)[:32]
    filename = f"proof_{timestamp}_{safe_ref}{ext}"
    proof_path = PAYMENT_PROOFS_DIR / filename
    proof_path.write_bytes(uploaded_file.getvalue())

    metadata = {
        "submitted_at": datetime.now().isoformat(timespec="seconds"),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "transfer_reference": transfer_reference,
        "proof_file": str(proof_path),
        "status": "pending_review",
    }
    meta_path = PAYMENT_PROOFS_DIR / f"proof_{timestamp}_{safe_ref}.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return proof_path


def send_manual_proof_email(
    customer_name: str,
    customer_email: str,
    transfer_reference: str,
    proof_path: Path,
) -> tuple[bool, str]:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_username).strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not smtp_host or not smtp_username or not smtp_password or not smtp_from:
        return False, "SMTP non configure. Configurez SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM."

    message = EmailMessage()
    message["Subject"] = "Nouvelle preuve de paiement Pro - Qualinova"
    message["From"] = smtp_from
    message["To"] = SUBSCRIPTION_CONTACT_EMAIL
    message.set_content(
        "Une nouvelle preuve de paiement Pro a ete soumise.\n\n"
        f"Nom: {customer_name}\n"
        f"Email client: {customer_email}\n"
        f"Reference virement: {transfer_reference}\n"
        f"Date: {datetime.now().isoformat(timespec='seconds')}\n"
    )

    with proof_path.open("rb") as attachment_fh:
        attachment_data = attachment_fh.read()
    message.add_attachment(
        attachment_data,
        maintype="application",
        subtype="octet-stream",
        filename=proof_path.name,
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True, "Email de notification envoye."
    except Exception as exc:
        return False, f"Echec envoi email: {exc}"


def slugify_label(value: str) -> str:
    sanitized: List[str] = []
    for char in value.lower():
        if char.isalnum():
            sanitized.append(char)
        elif not sanitized or sanitized[-1] != "_":
            sanitized.append("_")
    return "".join(sanitized).strip("_") or "qualinova"


def list_projects() -> List[str]:
    return list(PROJECT_CONFIGS.keys())


def modules_for_project(project: Optional[str]) -> List[str]:
    if not project or project not in PROJECT_CONFIGS:
        return []
    return list(PROJECT_CONFIGS[project]["modules"].keys())


def append_log(run_state: dict, message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    with LOG_LOCK:
        run_state["logs"].append(entry)
        if len(run_state["logs"]) > 400:
            run_state["logs"] = run_state["logs"][100:]


def build_failure_zip(source: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if source.exists():
            for file_path in sorted(source.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(source))
    buffer.seek(0)
    return buffer.getvalue()


def run_worker(
    state: dict,
    run_id: str,
    project: str,
    module: str,
    menu_lines: List[str],
    subscription_plan: str,
) -> None:
    state["status"] = "running"
    state["logs"] = []
    state["zip_bytes"] = None
    state["zip_name"] = ""
    state["artifact_path"] = ""
    state["failure_count"] = 0
    run_dir = ARTIFACTS_ROOT / run_id
    menu_file = run_dir / "menu_paths.txt"
    screenshot_root = run_dir / "screenshots"
    menu_file.parent.mkdir(parents=True, exist_ok=True)
    screenshot_root.mkdir(parents=True, exist_ok=True)
    menu_file.write_text("\n".join(menu_lines), encoding="utf-8")
    append_log(state, f"Preparing run {run_id} for {project} / {module}")

    # Récupérer la configuration du projet
    project_config = PROJECT_CONFIGS.get(project, {})
    module_url = project_config.get("modules", {}).get(module, "")
    credentials = project_config.get("credentials", {})
    auth_type = project_config.get("auth_type", "standard")

    env = os.environ.copy()
    env["MENU_PATH_FILE"] = str(menu_file)
    env["PROJECT_SLUG"] = slugify_label(project)
    env["MENU_CATEGORY_SLUG"] = slugify_label(module or project)
    env["SCREENSHOT_DIR"] = str(screenshot_root)
    env["MODULE_URL"] = module_url
    env["AUTH_USERNAME"] = credentials.get("username", "")
    env["AUTH_PASSWORD"] = credentials.get("password", "")
    env["AUTH_DOMAIN"] = credentials.get("domain", "")
    env["AUTH_TYPE"] = auth_type
    env["SUBSCRIPTION_PLAN"] = subscription_plan

    append_log(state, f"Configuration: {project} - {module}")
    append_log(state, f"URL: {module_url}")
    append_log(state, f"Auth type: {auth_type}")
    append_log(state, f"Subscription plan: {subscription_plan}")
    append_log(state, f"Effective username: {env['AUTH_USERNAME']}")
    append_log(state, f"Effective domain: {env['AUTH_DOMAIN']}")

    script_by_project = {
        "CDG": "non_regression_cdg.py",
        "AWB": "non_regression_awb3.py",
        "BMCE": "non_regression_bmce.py",
    }
    target_script = script_by_project.get(project, "non_regression_cdg.py")
    append_log(state, f"Automation script: {target_script}")

    cmd = [sys.executable, target_script]
    try:
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        append_log(state, f"Failed to start automation: {exc}")
        state["status"] = "failed"
        state["thread"] = None
        return

    try:
        assert process.stdout
        for raw_line in iter(process.stdout.readline, ""):
            if raw_line:
                append_log(state, raw_line.rstrip())
    finally:
        process.wait()
        exit_code = process.returncode
        append_log(state, f"Process exited with code {exit_code}")
        failure_paths = list(screenshot_root.rglob("*.png"))
        state["failure_count"] = len(failure_paths)
        state["zip_bytes"] = build_failure_zip(screenshot_root)
        state["zip_name"] = f"qualinova_failures_{run_id}.zip"
        if exit_code == 0:
            append_log(state, "Run completed without fatal errors.")
            state["status"] = "finished"
        else:
            append_log(state, "Run finished with issues; review the logs above.")
            state["status"] = "failed"
        state["artifact_path"] = str(run_dir.resolve())
        state["thread"] = None


def trigger_run(project: str, module: str, menu_lines: List[str], subscription_plan: str) -> None:
    run_state = st.session_state["qualinova_run"]
    if run_state["status"] == "running":
        st.warning("Une instance est déjà en cours. Merci de patienter.")
        return

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    thread = threading.Thread(
        target=run_worker,
        args=(run_state, run_id, project, module, menu_lines, subscription_plan),
    )
    thread.daemon = True
    run_state["thread"] = thread
    thread.start()


def render_header() -> None:
    st.markdown(
        """
<div class="header-animate" style="
    display:flex;
    justify-content:center;
    align-items:center;
    background: linear-gradient(90deg, #1f2937, #111827);
    border-radius: 20px;
    padding: 25px;
    margin-bottom: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
">
    <div style="text-align:center;">
        <div style="
            color:#facc15;
            font-size:48px;
            font-weight:700;
            letter-spacing:6px;
        ">
            QUALINOVA
        </div>
        <div style="
            color:#cbd5e1;
            font-size:22px;
            letter-spacing:3px;
            margin-top:8px;
        ">
            AUTOMATED PLAYWRIGHT DRONE
        </div>
        <div class="header-credit" style="
            margin-top:0.75rem;
            font-size:0.85rem;
            letter-spacing:0.4rem;
            color: rgba(203, 213, 225, 0.85);
            text-transform: uppercase;
            display:flex;
            flex-direction:column;
            gap:0.15rem;
        ">
            <span style="letter-spacing:0.25rem;">Maison Qualimetry</span>
            <span style="letter-spacing:0.5rem;">Live scroll vault</span>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    checkout_message = process_checkout_return()

    render_header()
    current_plan = "pro"

    st.markdown(
        """
<div style="
    margin-top: 0.6rem;
    margin-bottom: 1rem;
    padding: 0.9rem 1rem;
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(5, 9, 18, 0.72);
">
    <div style="
        color: #cbd5e1;
        font-size: 0.78rem;
        letter-spacing: 0.35rem;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    ">Version</div>
</div>
""",
        unsafe_allow_html=True,
    )
    projects = list_projects()
    col_form, col_visual = st.columns([1, 1])

    with col_form:
        st.markdown('<div class="block-container">', unsafe_allow_html=True)
        st.markdown("""
<div class="section-title">Projet / Module</div>
""", unsafe_allow_html=True)
        selected_project = st.selectbox(
            "Choisissez le projet",
            projects or ["No project available"],
            index=0,
            key="project_choice",
        )
        modules = modules_for_project(selected_project)
        selected_module = st.selectbox(
            "Module cible",
            modules or ["No module available"],
            index=0,
            key="module_choice",
        )
        
        # Afficher les informations de configuration
        if selected_project in PROJECT_CONFIGS:
            config = PROJECT_CONFIGS[selected_project]
            credentials = config["credentials"]
            st.markdown(f"""
<div style="
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.3);
    border-radius: 12px;
    padding: 0.8rem;
    margin-top: 0.8rem;
    font-size: 0.85rem;
">
    <div style="color: #22c55e; font-weight: 600; margin-bottom: 0.4rem;">📋 Configuration</div>
    <div style="color: var(--text);">
        <strong>Auth:</strong> {config["auth_type"]}<br>
        <strong>Username:</strong> {credentials["username"]}<br>
        <strong>Domain:</strong> {credentials["domain"]}
    </div>
</div>
""", unsafe_allow_html=True)
        
        st.markdown("""
<div class="section-title" style="margin-top:1rem;">Menu paths</div>
""", unsafe_allow_html=True)
        if checkout_message:
            st.info(checkout_message)

        st.markdown(
            f"""
<div style="
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(59, 130, 246, 0.35);
    border-radius: 12px;
    padding: 0.8rem;
    margin-top: 0.8rem;
    font-size: 0.85rem;
">
    <div style="color: #60a5fa; font-weight: 600; margin-bottom: 0.35rem;">Abonnement</div>
    <div style="color: var(--text);"><strong>Plan actif:</strong> {current_plan.upper()}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        menu_input = st.text_area(
            "Pensez à coller chaque menu sur une ligne et à utiliser > pour les niveaux",
            height=180,
            key="menu_input",
            help="Exemple : Report > Ordre de virement",
        )
        st.markdown('<div class="start-scroll-btn">', unsafe_allow_html=True)
        start_pressed = st.button("Start scrolling", key="start_scroll", help="Déclenche le robot Qualinova")
        st.markdown('</div>', unsafe_allow_html=True)
        if start_pressed:
            clean_lines = [line.strip() for line in menu_input.splitlines() if line.strip()]
            if not clean_lines:
                st.warning("Ajoutez au moins un menu à préparer avant de lancer l'exécution.")
            else:
                trigger_run(selected_project, selected_module, clean_lines, "pro")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_visual:
        st.markdown('<div class="player-shell">', unsafe_allow_html=True)
        st.markdown('<div class="video-frame">', unsafe_allow_html=True)
        st.video("https://cdn.streamlit.io/0.87.0/bee.mp4")
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    run_state = st.session_state["qualinova_run"]
    if run_state["status"] == "running":
        st_autorefresh(interval=2000, key="qualinova_autorefresh")
        st.warning("Scroll en cours… regardez le log ci-dessous pour suivre l'instantané.")

    log_text = "\n".join(run_state["logs"][-200:])
    log_html = (
        f"<div class=\"terminal-panel\">"
        f"<div class=\"terminal-header\"><span>Live terminal</span><span class=\"status-pill\">{run_state['status']}</span></div>"
        f"<pre>{escape(log_text)}</pre>"
        f"</div>"
    )
    st.markdown(log_html, unsafe_allow_html=True)

    if run_state["zip_bytes"]:
        st.download_button(
            "Télécharger les captures de fail",
            run_state["zip_bytes"],
            file_name=run_state["zip_name"],
            mime="application/zip",
        )
        if run_state["failure_count"] == 0:
            st.caption("Aucune erreur capturée pendant cette exécution.")
        else:
            st.caption(f"{run_state['failure_count']} captures archivées dans {run_state['zip_name']}.")
    if run_state["artifact_path"]:
        st.caption(f"Run artefacts: {run_state['artifact_path']}")


if __name__ == "__main__":
    main()
