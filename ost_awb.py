"""
ost_awb.py - Automatisation du process OST sur MegaCor (AWB).

Workflow couvert :
  1. Login MegaCor (migration / Vermeg+123 / domaine ALL)
  2. Navigation : Operations sur titres > Annonces > Creation > OST Marche Local
  3. Selection du "Type OST" depuis variable_saisies/ost_awb_<TypeOST>.txt
  4. Remplissage du formulaire dedie en respectant l'ORDRE et l'INDEX des
     cles dupliquees du fichier txt (ex: 2x "Titre Execute*").
  5. Save + capture timestamp dd/mm/yyyy hh:mm:ss:fff
  6. Operations sur titres > Annonces > Validation
     -> filtre Date de creation '>=' timestamp, "Valider l'annonce"
  7. Operations sur titres > Annonces > Activation
     -> meme filtre, "Activer l'annonce"
"""

from __future__ import annotations

import logging
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from playwright.sync_api import (
    Error as PlaywrightError,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = Path(__file__).resolve().parent

LOGIN_ENTRY = os.getenv(
    "MEGACOR_URL",
    "http://10.1.140.244:9081/MegaCor/login.jsp",
)
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "migration")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Vermeg+123")
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "ALL")

VARIABLES_DIR = Path(
    os.getenv("OST_AWB_VARIABLES_DIR", str(WORKSPACE_ROOT / "variable_saisies"))
)
TYPE_OST_FILE = Path(
    os.getenv("OST_AWB_TYPE_FILE", str(VARIABLES_DIR / "ost_awb.txt"))
)

SCREENSHOTS_ROOT = Path(
    os.getenv(
        "OST_AWB_SCREENSHOTS_DIR",
        str(WORKSPACE_ROOT / "screenshots" / "AWB"),
    )
)

TOP_LEVEL_MENU = "Opérations sur titres"
TOP_LEVEL_EXECUTIONS = "Exécutions"
TOP_LEVEL_PAYMENTS = "Paiements"
TREE_PATH_CREATION = ["Annonces", "Création", "OST Marché Local"]
TREE_PATH_VALIDATION = ["Annonces", "Validation"]
TREE_PATH_ACTIVATION = ["Annonces", "Activation"]
TREE_PATH_CONSULTATION = ["Annonces", "Consultation des annonces"]
TREE_PATH_EXEC_CLIENT_OFFICE = ["Client", "Calcul", "OST d'Office"]
TREE_PATH_EXEC_MARKET_OFFICE = ["Marché", "Calcul", "OST d'Office"]
TREE_PATH_PAY_MARKET_ADHOC = ["Paiements Marché", "Créer", "Générer Ad-hoc"]
TREE_PATH_PAY_CLIENT_ACTUAL = ["Paiements Client", "Création", "Paiement Actuel"]

# Domaine pour la 2e session (post-activation)
AUTH_DOMAIN_POST = os.getenv("AUTH_DOMAIN_POST", "awb")

DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
LOGIN_TIMEOUT_MS = 30_000
APP_READY_TIMEOUT_MS = 45_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ---------------------------------------------------------------------------
# Specs des formulaires (ordre = ordre de saisie + des cles dans le txt)
# ---------------------------------------------------------------------------
# kind in {"text", "combo", "search", "date"}
#   text   : input simple, tape la valeur
#   combo  : dropdown ExtJS (trigger + liste x-combo-list-item)
#   search : champ avec lookup F2 (saisie + Enter pour valider la recherche)
#   date   : input date au format dd/mm/yyyy

FORM_FIELDS_PAIEMENT_INTERETS: List[dict] = [
    {"label": "Source d'Information",         "container": "Field_ComponentdataSource",                                                                       "kind": "combo"},
    {"label": "OST Référence Marché",         "container": "Field_ComponentmarketReference",                                                                  "kind": "text"},
    {"label": "Agent Payeur",                 "container": "Field_ComponentpayingAgent",                                                                      "kind": "combo"},
    {"label": "Titre Exécuté",                "container": "Field_ComponentrightDistributionEvent.entitledSecurity",                                          "kind": "search"},
    {"label": "Date de détachement Maroclear","container": "Field_ComponentrightDistributionEvent.exDate",                                                    "kind": "date"},
    {"label": "Date d'enregistrement",        "container": "Field_ComponentrightDistributionEvent.recordDate",                                                "kind": "date"},
    {"label": "Titre",                        "container": "Field_ComponentrightDistributionEvent.optionSecu.iNTRRightMvtSecIn.securityByMarket",             "kind": "search"},
    {"label": "Date d'expiration",            "container": "Field_ComponentrightDistributionEvent.optionSecu.expiryDate",                                     "kind": "date"},
    {"label": "Date de paiement du droit",    "container": "Field_ComponentrightDistributionEvent.optionSecu.iNTRRightMvtSecIn.paymentDate",                  "kind": "date"},
    {"label": "Titre Exécuté",                "container": "Field_ComponentinterestPaymentEvent.entitledSecurity",                                            "kind": "search"},
    {"label": "Date de détachement",          "container": "Field_ComponentinterestPaymentEvent.exDate",                                                      "kind": "date"},
    {"label": "Date d'enregistrement",        "container": "Field_ComponentinterestPaymentEvent.recordDate",                                                  "kind": "date"},
    {"label": "Date de paiement de l'exercice","container": "Field_ComponentinterestPaymentEvent.paymentDate",                                                "kind": "date"},
    {"label": "Prix",                         "container": "Field_ComponentinterestPaymentEvent.optionCash.interestPaymentMvtCash.price",                     "kind": "text"},
    {"label": "Devise",                       "container": "Field_ComponentinterestPaymentEvent.optionCash.interestPaymentMvtCash.currency",                  "kind": "search"},
    {"label": "Date de paiement espèce",      "container": "Field_ComponentinterestPaymentEvent.optionCash.interestPaymentMvtCash.paymentDate",               "kind": "date"},
    {"label": "Titre",                        "container": "Field_ComponentinterestPaymentEvent.optionCash.secOut.securityByMarket",                          "kind": "search"},
    {"label": "Date de paiement",             "container": "Field_ComponentinterestPaymentEvent.optionCash.secOut.paymentDate",                               "kind": "date"},
]

FORM_FIELDS_PAIEMENT_DIVIDENDES_ESPECE: List[dict] = [
    {"label": "Source d'Information",          "container": "Field_ComponentdataSource",                                                              "kind": "combo"},
    {"label": "OST Référence Marché",          "container": "Field_ComponentmarketReference",                                                         "kind": "text"},
    {"label": "Agent Payeur",                  "container": "Field_ComponentpayingAgent",                                                             "kind": "combo"},
    {"label": "Titre Exécuté",                 "container": "Field_ComponentcashDivRightDist.entitledSecurity",                                       "kind": "search"},
    {"label": "Date de détachement bourse",    "container": "Field_ComponentcashDivRightDist.exDate",                                                 "kind": "date"},
    {"label": "Titre",                         "container": "Field_ComponentcashDivRightDist.optionSecu.cashDivRightMvtSec.securityByMarket",         "kind": "search"},
    {"label": "Date d'expiration",             "container": "Field_ComponentcashDivRightDist.optionSecu.expiryDate",                                  "kind": "date"},
    {"label": "Titre Exécuté",                 "container": "Field_ComponentcashDividendEvent.entitledSecurity",                                      "kind": "search"},
    {"label": "Type de Dividende",             "container": "Field_ComponentcashDividendEvent.dividendType",                                          "kind": "combo"},
    {"label": "Prix",                          "container": "Field_ComponentcashDividendEvent.optionCash.cashMovement.price",                         "kind": "text"},
    {"label": "Devise",                        "container": "Field_ComponentcashDividendEvent.optionCash.cashMovement.currency",                      "kind": "search"},
    {"label": "Titre",                         "container": "Field_ComponentcashDividendEvent.optionCash.secOut.securityByMarket",                    "kind": "search"},
]

FORM_FIELDS_BY_TYPE = {
    "paiement d'interets": FORM_FIELDS_PAIEMENT_INTERETS,
    "paiement d'intérêts": FORM_FIELDS_PAIEMENT_INTERETS,  # tolere accents
    "paiement de dividendes en espece": FORM_FIELDS_PAIEMENT_DIVIDENDES_ESPECE,
    "paiement de dividendes en espèce": FORM_FIELDS_PAIEMENT_DIVIDENDES_ESPECE,
    "paiement de dividendes en especes": FORM_FIELDS_PAIEMENT_DIVIDENDES_ESPECE,
    "paiement de dividendes en espèces": FORM_FIELDS_PAIEMENT_DIVIDENDES_ESPECE,
}


# ---------------------------------------------------------------------------
# Spec du flux post-activation par type d'OST
# ---------------------------------------------------------------------------
# Pour chaque type d'OST, liste des "evenements" a traiter en sequence.
# Chaque evenement decrit comment identifier la bonne ligne dans :
#   - les ecrans Executions (Client + Marche)  : matching sur la colonne
#     'ecaLabel' (ex. "RHDI/RightDistribution", "INTR/Interest Payment", ...)
#   - l'ecran Paiements Client                  : matching sur la colonne
#     'eCAName' (ex. "RightDistributionEvent", "InterestPaymentEvent", ...)
# Pour chaque evenement, le cycle complet est joue :
#   ExecClient -> ExecMarche -> Generer Ad-hoc Marche -> Pay Client.

POST_FLOW_PAIEMENT_INTERETS = [
    {
        "key": "right_dist",
        "eca_label": re.compile(r"rhdi|right\s*distribution", re.IGNORECASE),
        "eca_name": re.compile(r"rightdistribution\s*event", re.IGNORECASE),
    },
    {
        "key": "interest_payment",
        "eca_label": re.compile(r"intr|interest\s*payment", re.IGNORECASE),
        "eca_name": re.compile(r"interestpayment\s*event", re.IGNORECASE),
    },
]

POST_FLOW_PAIEMENT_DIVIDENDES_ESPECE = [
    {
        "key": "cash_div_right_dist",
        "eca_label": re.compile(
            r"dvrd|cash\s*div\s*right|right\s*dist", re.IGNORECASE
        ),
        "eca_name": re.compile(r"cashdivright\w*event", re.IGNORECASE),
    },
    {
        "key": "cash_dividend",
        "eca_label": re.compile(
            r"dvca|cash\s*dividend|paiement.*dividende", re.IGNORECASE
        ),
        "eca_name": re.compile(r"cashdividend\s*event", re.IGNORECASE),
    },
]

POST_FLOW_BY_TYPE = {
    "paiement d'interets": POST_FLOW_PAIEMENT_INTERETS,
    "paiement d'intérêts": POST_FLOW_PAIEMENT_INTERETS,
    "paiement de dividendes en espece": POST_FLOW_PAIEMENT_DIVIDENDES_ESPECE,
    "paiement de dividendes en espèce": POST_FLOW_PAIEMENT_DIVIDENDES_ESPECE,
    "paiement de dividendes en especes": POST_FLOW_PAIEMENT_DIVIDENDES_ESPECE,
    "paiement de dividendes en espèces": POST_FLOW_PAIEMENT_DIVIDENDES_ESPECE,
}


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(ch)
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(text).strip().lower())


def _normalize_label(label: str) -> str:
    """Normalise un libelle de champ : sans etoile finale, sans accents, lower."""
    return _normalize((label or "").strip().rstrip("*").strip())


def load_variables_ordered(path: Path) -> List[Tuple[str, str]]:
    """
    Lit un fichier 'cle = valeur' UTF-8 et renvoie une LISTE ordonnee de
    tuples (cle_normalisee, valeur_brute). Conserve l'ordre du fichier et
    autorise les cles dupliquees (la N-eme occurrence sera consommee a
    la N-eme demande).
    """
    if not path.exists():
        logging.warning("Fichier de variables introuvable : %s", path)
        return []

    entries: List[Tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            # Cle declaree sans '=' (ex: "Date d'enregistrement*") => valeur vide
            key_norm = _normalize_label(line)
            if key_norm:
                entries.append((key_norm, ""))
            continue
        key, value = line.split("=", 1)
        key_norm = _normalize_label(key)
        if not key_norm:
            continue
        entries.append((key_norm, value.strip()))
    return entries


def consume_value(entries: List[Tuple[str, str]], label: str) -> Optional[str]:
    """
    Retire et renvoie la PREMIERE valeur dont la cle correspond a `label`.
    Renvoie None si aucune occurrence trouvee. Gere les doublons en
    respectant l'ordre du fichier txt.
    """
    target = _normalize_label(label)
    for idx, (key, _value) in enumerate(entries):
        if key == target:
            return entries.pop(idx)[1]
    return None


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def _find_first_visible(page: Page, selectors: Iterable[str]) -> Optional[Locator]:
    for selector in selectors:
        loc = page.locator(selector).first
        if loc.count() and loc.is_visible():
            return loc
    return None


def _fill_domain(page: Page, domain: str) -> None:
    if not domain:
        return

    field = _find_first_visible(
        page,
        [
            "input[name='j_asp']",
            "#domain",
            "select[name='domain']",
            "input[name='domain']",
            "input[id*='domain']",
        ],
    )
    if field is None:
        logging.debug("Champ domaine non trouve, on poursuit sans le definir.")
        return

    try:
        tag = (field.evaluate("el => el.tagName") or "").lower()
    except Exception:
        tag = ""

    try:
        if tag == "select":
            try:
                field.select_option(label=domain)
                return
            except Exception:
                field.select_option(value=domain)
                return
        field.fill("")
        field.type(domain, delay=15)
    except Exception as exc:
        logging.warning("Impossible de definir le domaine '%s' : %s", domain, exc)


def login(page: Page, *, domain: Optional[str] = None) -> bool:
    domain_value = domain if domain is not None else AUTH_DOMAIN
    logging.info("Ouverture de %s", LOGIN_ENTRY)
    try:
        page.goto(LOGIN_ENTRY, wait_until="domcontentloaded", timeout=LOGIN_TIMEOUT_MS)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.error("Echec navigation vers %s : %s", LOGIN_ENTRY, exc)
        return False

    try:
        page.wait_for_selector(
            "#username, input[name='username'], input[name='j_username']",
            timeout=15_000,
        )
    except PlaywrightTimeoutError:
        logging.error("Formulaire de login non affiche.")
        return False

    username = _find_first_visible(
        page, ["#username", "input[name='username']", "input[name='j_username']"]
    )
    password = _find_first_visible(
        page, ["#password", "input[name='password']", "input[name='j_password']"]
    )
    if username is None or password is None:
        logging.error("Champs username/password introuvables.")
        return False

    username.fill(AUTH_USERNAME)
    password.fill(AUTH_PASSWORD)
    _fill_domain(page, domain_value)

    submit = _find_first_visible(
        page,
        [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Login')",
            "button:has-text('Se connecter')",
        ],
    )
    if submit is None:
        logging.info("Pas de bouton submit visible, validation par Enter.")
        password.press("Enter")
    else:
        submit.click()

    app_ready = (
        "div[role='treeitem'], "
        "button:has-text('Opérations sur titres'), "
        "button:has-text('Position'), "
        "a.x-tab-strip-text"
    )
    try:
        page.wait_for_selector(app_ready, timeout=APP_READY_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        if page.locator("#username, input[name='username']").count():
            logging.error("Login refuse : le formulaire est toujours visible.")
            return False
        logging.warning("Application non detectee dans le delai, on poursuit.")

    logging.info(
        "Login MegaCor effectue (user=%s, domain=%s)", AUTH_USERNAME, domain_value
    )
    return True


def logout(page: Page) -> bool:
    """Tente de se deconnecter de MegaCor (clic sur lien/bouton 'Logout')."""
    candidates = [
        "a:has-text('Logout')",
        "a:has-text('Logoff')",
        "a:has-text('Déconnexion')",
        "button:has-text('Logout')",
        "button:has-text('Déconnexion')",
        "#logout",
        "a[href*='logout']",
    ]
    clicked = False
    for sel in candidates:
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        logging.info("Aucun bouton logout trouve, navigation directe vers /logout.")
        try:
            base = LOGIN_ENTRY.rsplit("/", 1)[0]
            page.goto(f"{base}/logout.jsp", wait_until="domcontentloaded", timeout=10_000)
        except Exception as exc:
            logging.warning("Logout echoue : %s", exc)
            return False
    page.wait_for_timeout(800)
    return True


# ---------------------------------------------------------------------------
# Navigation menu
# ---------------------------------------------------------------------------

def close_active_tab(page: Page) -> None:
    """Ferme l'onglet ExtJS actif via mousedown DOM direct.

    ExtJS ne reagit pas toujours au .click() JS sur la croix : il ecoute
    'mousedown'. On dispatch donc l'evenement complet (mousedown + mouseup +
    click) sur la croix, en ciblant en priorite le tab actif, sinon le
    DERNIER tab visible (qui est generalement celui qu'on vient d'ouvrir).
    """
    try:
        result = page.evaluate(
            """
            () => {
              const fire = (el) => {
                const opts = { bubbles: true, cancelable: true, view: window, button: 0 };
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                el.dispatchEvent(new MouseEvent('mouseup', opts));
                el.dispatchEvent(new MouseEvent('click', opts));
              };
              // 1) Tab actif explicite
              let target = document.querySelector(
                'li.x-tab-strip-active a.x-tab-strip-close,'
                + ' .x-tab-strip-active a.x-tab-strip-close'
              );
              // 2) Sinon, dernier .x-tab-strip-close visible
              if (!target) {
                const all = Array.from(
                  document.querySelectorAll('a.x-tab-strip-close')
                ).filter(el => el.offsetParent !== null);
                if (all.length) target = all[all.length - 1];
              }
              if (!target) return { closed: false, count: 0 };
              const before = document.querySelectorAll(
                'a.x-tab-strip-close'
              ).length;
              fire(target);
              return { closed: true, count: before };
            }
            """
        )
        if not result or not result.get("closed"):
            return

        before_count = result.get("count", 0)
        # Attente active : un tab a disparu (count diminue) -> ferme.
        deadline_ms = 3000
        step_ms = 40
        elapsed = 0
        while elapsed < deadline_ms:
            now_count = page.evaluate(
                "() => document.querySelectorAll('a.x-tab-strip-close').length"
            )
            if now_count < before_count:
                logging.info("Onglet courant ferme (%dms).", elapsed)
                return
            page.wait_for_timeout(step_ms)
            elapsed += step_ms

        logging.warning("Onglet pas ferme apres %dms.", deadline_ms)
    except Exception as exc:
        logging.debug("Fermeture onglet ignoree : %s", exc)


def close_all_tabs(page: Page) -> None:
    """Ferme tous les onglets ExtJS ouverts (max 30 iterations)."""
    for _ in range(30):
        closes = page.locator(".x-tab-strip-close:visible")
        if not closes.count():
            return
        try:
            closes.first.click(force=True, timeout=1000)
            page.wait_for_timeout(200)
        except Exception:
            return


def click_top_level_menu(page: Page, label: str) -> bool:
    logging.info("Ouverture du menu '%s'", label)
    candidates = [
        page.get_by_role("button", name=label),
        page.locator("button.x-btn-text").filter(has_text=label),
        page.locator("button").filter(has_text=label),
    ]
    for cand in candidates:
        first = cand.first
        if first.count():
            try:
                first.click(timeout=4000)
                page.wait_for_timeout(900)
                return True
            except PlaywrightTimeoutError:
                continue
    logging.error("Menu top-level introuvable : %s", label)
    return False


def _find_tree_node(page: Page, label: str):
    target = _normalize(label)
    nodes = page.locator(".x-tree3-node-text")
    count = nodes.count()
    # Pass 1 : match EXACT uniquement (evite ex. 'Annonces' qui matcherait
    # 'Consultation des annonces' et ouvrirait un mauvais onglet).
    for idx in range(count):
        node = nodes.nth(idx)
        try:
            text = node.inner_text() or ""
        except Exception:
            continue
        if not text.strip():
            continue
        if _normalize(text) != target:
            continue
        try:
            node.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass
        ancestor = node.locator(
            "xpath=ancestor::div[contains(@class,'x-tree3-node') or contains(@class,'x-tree-node')][1]"
        ).first
        if ancestor.count():
            return ancestor
        return node
    return None


def navigate_tree_path(
    page: Page,
    segments: List[str],
    final_selector: Optional[str] = None,
) -> bool:
    # Optimisation : si la feuille est deja visible (arbre deja deplie d'une
    # navigation precedente), on clique direct sans toucher aux parents
    # (le dblclick sur un parent deja deplie le COLLAPSE et fait disparaitre
    # la feuille).
    leaf_label = segments[-1]
    leaf_node = _find_tree_node(page, leaf_label)
    if leaf_node is not None:
        try:
            leaf_node.click(force=True, timeout=4000)
            logging.info("Ouverture directe de la feuille '%s'", leaf_label)
            page.wait_for_timeout(800)
            if final_selector:
                try:
                    page.wait_for_selector(final_selector, timeout=15_000)
                except PlaywrightTimeoutError:
                    logging.warning(
                        "Selecteur final '%s' non visible apres navigation directe.",
                        final_selector,
                    )
            return True
        except PlaywrightTimeoutError:
            logging.debug("Click direct feuille echoue, fallback navigation complete.")

    for idx, segment in enumerate(segments):
        is_leaf = idx == len(segments) - 1

        node = None
        # On laisse le temps a l'arbre de se rafraichir apres chaque expansion
        for _ in range(10):
            node = _find_tree_node(page, segment)
            if node is not None:
                break
            page.wait_for_timeout(300)

        if node is None:
            logging.error("Noeud d'arbre introuvable : '%s'", segment)
            return False

        try:
            if is_leaf:
                node.click(force=True, timeout=4000)
                logging.info("Ouverture de la feuille '%s'", segment)
            else:
                node.dblclick(force=True, timeout=4000)
                logging.info("Expansion du noeud '%s'", segment)
        except PlaywrightTimeoutError:
            logging.error("Echec interaction avec '%s'", segment)
            return False

        page.wait_for_timeout(800)

    if final_selector:
        try:
            page.wait_for_selector(final_selector, timeout=15_000)
        except PlaywrightTimeoutError:
            logging.warning(
                "Selecteur final '%s' non visible apres navigation, on poursuit.",
                final_selector,
            )
    return True


# ---------------------------------------------------------------------------
# Moteur de remplissage de formulaire
# ---------------------------------------------------------------------------

def _container_locator(page: Page, container_id: str) -> Locator:
    """Locator par attribut id (gere les '.' et autres caracteres speciaux)."""
    return page.locator(f'[id="{container_id}"]').first


def _focus_input(input_field: Locator) -> None:
    try:
        input_field.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        input_field.click(force=True, timeout=2500)
    except PlaywrightTimeoutError:
        pass


def _clear_input(input_field: Locator) -> None:
    try:
        input_field.fill("", timeout=1500)
        return
    except Exception:
        pass
    try:
        input_field.press("Control+A", timeout=800)
        input_field.press("Delete", timeout=800)
    except Exception:
        pass


def _fill_text(page: Page, container: Locator, value: str, *, field_label: str) -> bool:
    input_field = container.locator("input.x-form-text, input.x-form-field").first
    if not input_field.count():
        logging.error("Input introuvable pour '%s'", field_label)
        return False
    _focus_input(input_field)
    _clear_input(input_field)
    input_field.type(value, delay=20)
    page.wait_for_timeout(150)
    try:
        input_field.press("Tab")
    except Exception:
        pass
    page.wait_for_timeout(150)
    return True


def _fill_date(page: Page, container: Locator, value: str, *, field_label: str) -> bool:
    return _fill_text(page, container, value, field_label=field_label)


def _fill_search(page: Page, container: Locator, value: str, *, field_label: str) -> bool:
    """
    Champ de type 'search' (lookup F2). On saisit la valeur, on appuie sur F2
    pour ouvrir la grille de recherche, on selectionne la 1ere ligne puis on
    tabule. Si la grille n'apparait pas, on tabule directement.
    """
    input_field = container.locator("input.x-form-text, input.x-form-field").first
    if not input_field.count():
        logging.error("Input introuvable pour '%s' (search)", field_label)
        return False
    _focus_input(input_field)
    _clear_input(input_field)
    input_field.type(value, delay=20)
    page.wait_for_timeout(200)
    try:
        input_field.press("F2")
        page.wait_for_timeout(700)
    except Exception:
        pass
    grid_row = page.locator("div.x-grid3-body tr.x-grid3-row").first
    if grid_row.count():
        try:
            grid_row.dblclick(force=True, timeout=3000)
            page.wait_for_timeout(400)
        except PlaywrightTimeoutError:
            try:
                grid_row.click(force=True, timeout=2000)
            except PlaywrightTimeoutError:
                pass
            page.keyboard.press("Enter")
    try:
        input_field.press("Tab")
    except Exception:
        pass
    page.wait_for_timeout(200)
    return True


def _fill_combo(page: Page, container: Locator, value: str, *, field_label: str) -> bool:
    """Combo ExtJS : ouvre trigger, tape pour filtrer, clique l'item, evite
    tout acces au input apres commit (le formulaire peut etre recharge)."""
    input_field = container.locator("input.x-form-text, input.x-form-field").first
    if not input_field.count():
        logging.error("Input combo introuvable pour '%s'", field_label)
        return False

    try:
        input_field.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    try:
        input_field.click(force=True, timeout=2000)
    except PlaywrightTimeoutError:
        pass
    try:
        input_field.fill("", timeout=1000)
    except Exception:
        pass

    trigger = container.locator("img.x-form-trigger-arrow").first
    if trigger.count():
        try:
            trigger.click(force=True, timeout=1500)
        except PlaywrightTimeoutError:
            pass
    page.wait_for_timeout(250)

    try:
        input_field.type(value, delay=10, timeout=4000)
    except PlaywrightTimeoutError:
        logging.error("[%s] type() en timeout", field_label)
        return False
    page.wait_for_timeout(200)

    apostrophes = "['\u2019\u02bc\u2032]"
    escaped = re.escape(value)
    for ch in ("'", "\u2019", "\u02bc", "\u2032"):
        escaped = escaped.replace(re.escape(ch), apostrophes)
    pattern = re.compile(escaped, re.IGNORECASE)

    option = page.locator(
        ".x-combo-list-item:visible, .x-boundlist-item:visible"
    ).filter(has_text=pattern).first
    if not option.count():
        page.wait_for_timeout(300)
        option = page.locator(
            ".x-combo-list-item:visible, .x-boundlist-item:visible"
        ).filter(has_text=pattern).first
    if not option.count():
        option = page.locator(
            ".x-combo-list-item:visible, .x-boundlist-item:visible"
        ).first

    if option.count():
        try:
            option.click(force=True, timeout=2000)
            logging.info("[%s] item clique", field_label)
            page.wait_for_timeout(150)
            return True
        except PlaywrightTimeoutError:
            pass

    try:
        input_field.press("ArrowDown", timeout=1500)
        input_field.press("Enter", timeout=1500)
        logging.info("[%s] commit via Enter", field_label)
        page.wait_for_timeout(300)
        return True
    except PlaywrightTimeoutError:
        logging.error("[%s] commit echoue", field_label)
        return False


def select_type_ost(page: Page, value: str) -> bool:
    if not value:
        logging.warning("Valeur 'Type OST' vide, etape ignoree.")
        return False
    logging.info("Selection 'Type OST' = '%s'", value)
    field = page.locator("#Field_ComponentcaType").first
    try:
        field.wait_for(state="visible", timeout=10_000)
    except PlaywrightTimeoutError:
        logging.error("Champ 'Type OST' introuvable a l'ecran.")
        return False
    return _fill_combo(page, field, value, field_label="Type OST")


def fill_form(
    page: Page,
    fields: List[dict],
    entries: List[Tuple[str, str]],
) -> bool:
    """
    Remplit les champs DANS L'ORDRE de `fields`. Pour chaque champ, on
    consomme la prochaine occurrence de la cle correspondante dans
    `entries` (ce qui prend en compte l'ordre + les doublons du fichier).
    Les champs sans valeur fournie (cle absente ou valeur vide) sont sautes.
    """
    ok_global = True
    for index, spec in enumerate(fields, start=1):
        label = spec["label"]
        kind = spec["kind"]
        container_id = spec["container"]
        value = consume_value(entries, label)
        if value is None:
            logging.info(
                "[%02d] '%s' : aucune occurrence dans le txt, ignore.",
                index, label,
            )
            continue
        # Retire les commentaires entre parentheses (ex: "09/04/2026 (autofilled ...)")
        cleaned = re.sub(r"\([^)]*\)", "", value).strip()
        # Champ autofilled par MegaCor apres tabulation : on ne saisit rien
        if re.search(r"autofill", cleaned, re.IGNORECASE) or not cleaned:
            logging.info(
                "[%02d] '%s' : autofilled / vide, ignore.", index, label,
            )
            continue
        value = cleaned
        container = _container_locator(page, container_id)
        try:
            container.wait_for(state="visible", timeout=8000)
        except PlaywrightTimeoutError:
            logging.warning(
                "[%02d] Container '%s' (%s) non visible, ignore.",
                index, container_id, label,
            )
            ok_global = False
            continue
        try:
            container.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass

        logging.info("[%02d] %s (%s) = '%s'", index, label, kind, value)
        try:
            if kind == "combo":
                ok = _fill_combo(page, container, value, field_label=label)
            elif kind == "search":
                ok = _fill_search(page, container, value, field_label=label)
            elif kind == "date":
                ok = _fill_date(page, container, value, field_label=label)
            else:
                ok = _fill_text(page, container, value, field_label=label)
        except Exception as exc:
            logging.error("Erreur sur '%s' : %s", label, exc)
            ok = False
        if not ok:
            ok_global = False
    return ok_global


# ---------------------------------------------------------------------------
# Save + horodatage
# ---------------------------------------------------------------------------

def _format_timestamp(now: datetime) -> str:
    return now.strftime("%d/%m/%Y %H:%M:%S:") + f"{now.microsecond // 1000:03d}"


def _dismiss_notification_popup(
    page: Page,
    timeout_ms: int = 2000,
    *,
    screenshot_dir: Optional[Path] = None,
    step_label: Optional[str] = None,
) -> int:
    """
    Cherche brievement une pop-up ExtJS et clique tous les OK/Oui/Yes
    successifs (chaine de pop-ups). NE BLOQUE PAS si aucune pop-up.

    Si `screenshot_dir` est fourni, prend un screenshot full-page AVANT
    chaque click OK (capture l'etat avec la pop-up visible). Le nom du
    fichier est `<step_label>_popup<N>_<HHMMSS>.png`.

    Retourne le nombre de pop-ups fermees.
    """
    closed_total = 0

    def _popup_visible_js() -> bool:
        try:
            return bool(
                page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('.x-window'))
                      .some(w => w.offsetParent !== null
                        && Array.from(w.querySelectorAll('button.x-btn-text'))
                          .some(b => ['ok','oui','yes']
                            .includes((b.textContent||'').trim().toLowerCase())))
                    """
                )
            )
        except Exception:
            return False

    def _click_one_popup_js() -> int:
        try:
            return page.evaluate(
                """
                () => {
                  let n = 0;
                  const wins = document.querySelectorAll('.x-window');
                  wins.forEach(w => {
                    if (n) return;
                    if (w.offsetParent === null) return;
                    const btns = w.querySelectorAll('button.x-btn-text');
                    btns.forEach(b => {
                      if (n) return;
                      const t = (b.textContent || '').trim().toLowerCase();
                      if (t === 'ok' || t === 'oui' || t === 'yes') {
                        const opts = { bubbles: true, cancelable: true,
                                       view: window, button: 0 };
                        b.dispatchEvent(new MouseEvent('mousedown', opts));
                        b.dispatchEvent(new MouseEvent('mouseup', opts));
                        b.dispatchEvent(new MouseEvent('click', opts));
                        n++;
                      }
                    });
                  });
                  return n;
                }
                """
            ) or 0
        except Exception:
            return 0

    def _capture(idx: int) -> None:
        if not screenshot_dir:
            return
        try:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%H%M%S_%f")[:-3]
            label = _safe_filename(step_label or "step") or "step"
            path = screenshot_dir / f"{label}_popup{idx:02d}_{stamp}.png"
            page.screenshot(path=str(path), full_page=True)
            logging.info("Screenshot pop-up : %s", path.name)
        except Exception as exc:
            logging.debug("Screenshot ignore : %s", exc)

    # 1) Attente initiale courte d'une 1ere pop-up
    elapsed = 0
    step = 100
    while elapsed < timeout_ms:
        if _popup_visible_js():
            _capture(closed_total + 1)
            n = _click_one_popup_js()
            if n:
                closed_total += n
                logging.info("Pop-up fermee (%d).", closed_total)
                break
        page.wait_for_timeout(step)
        elapsed += step

    # 2) Pop-ups en chaine (max 5)
    for _ in range(5):
        appeared = False
        for _ in range(8):  # ~800ms max
            page.wait_for_timeout(100)
            if _popup_visible_js():
                _capture(closed_total + 1)
                n = _click_one_popup_js()
                if n:
                    closed_total += n
                    appeared = True
                    logging.info("Pop-up enchainee fermee (%d).", closed_total)
                    break
        if not appeared:
            break

    return closed_total


def _force_close_all_modals(page: Page) -> None:
    """Ferme de force toutes les fenetres ExtJS modales visibles (JS)."""
    try:
        n = page.evaluate(
            """
            () => {
              let n = 0;
              const wins = document.querySelectorAll('.x-window');
              wins.forEach(w => {
                if (w.offsetParent === null) return;
                // Essai 1 : bouton OK/Oui/Yes/Cancel/Annuler
                const btns = w.querySelectorAll('button.x-btn-text');
                let clicked = false;
                btns.forEach(b => {
                  if (clicked) return;
                  const t = (b.textContent || '').trim().toLowerCase();
                  if (['ok','oui','yes','annuler','cancel','close','fermer'].includes(t)) {
                    b.click(); clicked = true; n++;
                  }
                });
                // Essai 2 : croix de fermeture
                if (!clicked) {
                  const x = w.querySelector('.x-tool-close');
                  if (x) { x.click(); n++; }
                }
              });
              return n;
            }
            """
        )
        if n:
            logging.info("Modales fermees de force : %d", n)
            page.wait_for_timeout(400)
    except Exception as exc:
        logging.debug("Force close modals : %s", exc)


def click_save_and_capture_timestamp(
    page: Page,
    *,
    screenshot_dir: Optional[Path] = None,
) -> Optional[str]:
    save_btn = page.locator("#Component_PAGE_FORM_0_save_null").first
    if not save_btn.count():
        logging.error("Bouton Save introuvable.")
        return None
    try:
        save_btn.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    timestamp = _format_timestamp(datetime.now() - timedelta(minutes=3))
    try:
        save_btn.click(force=True, timeout=4000)
    except PlaywrightTimeoutError:
        logging.error("Click Save en timeout.")
        return None
    logging.info("Save clique a %s", timestamp)
    # Pop-ups (peuvent prendre ~30s a apparaitre cote serveur).
    # Non bloquant : on poursuit meme si rien n'apparait dans le delai.
    _dismiss_notification_popup(
        page,
        timeout_ms=35000,
        screenshot_dir=screenshot_dir,
        step_label="01_save_creation",
    )
    close_active_tab(page)
    return timestamp


# ---------------------------------------------------------------------------
# Validation / Activation
# ---------------------------------------------------------------------------

def _select_creation_date_operator_ge(page: Page) -> bool:
    """Ouvre le combo operateur du field 'Date de creation' et selectionne '>='."""
    container = page.locator("#Field_ComponentcreationDate").first
    if not container.count():
        logging.error("Field 'Date de création' introuvable.")
        return False

    # Le 1er trigger / input du container correspond a l'operateur
    op_input = container.locator(
        "input.x-triggerfield-noedit, input[role='combobox'], input.x-form-text"
    ).first
    if not op_input.count():
        logging.error("Input operateur 'Date de création' introuvable.")
        return False

    # Ouvrir la liste : on tente le trigger en premier, sinon click sur l'input
    trigger = container.locator("img.x-form-trigger-arrow").first
    opened = False
    if trigger.count():
        try:
            trigger.click(force=True, timeout=2500)
            opened = True
        except PlaywrightTimeoutError:
            pass
    if not opened:
        try:
            op_input.click(force=True, timeout=2000)
        except PlaywrightTimeoutError:
            pass
    page.wait_for_timeout(500)

    # Strategie 1 : matcher exactement '>='
    candidates = page.locator(
        ".x-combo-list-item, .x-boundlist-item, li.x-boundlist-item, "
        "div[role='listitem']"
    )
    pattern_ge = re.compile(r"^\s*>\s*=\s*$")
    option = candidates.filter(has_text=pattern_ge).first
    if option.count():
        try:
            option.click(force=True, timeout=2500)
            page.wait_for_timeout(300)
            logging.info("Operateur '>=' selectionne (match exact).")
            return True
        except PlaywrightTimeoutError:
            pass

    # Strategie 2 : 7eme item de la liste visible
    visible_items = candidates
    total = visible_items.count()
    if total >= 7:
        try:
            visible_items.nth(6).click(force=True, timeout=2500)
            page.wait_for_timeout(300)
            logging.info("Operateur '>=' selectionne (7eme item, total=%d).", total)
            return True
        except PlaywrightTimeoutError:
            pass

    # Strategie 3 : clavier (Down x7, Enter)
    try:
        op_input.click(force=True, timeout=1500)
    except PlaywrightTimeoutError:
        pass
    if trigger.count():
        try:
            trigger.click(force=True, timeout=1500)
        except PlaywrightTimeoutError:
            pass
    page.wait_for_timeout(300)
    try:
        for _ in range(7):
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(60)
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        logging.info("Operateur '>=' selectionne (clavier).")
        return True
    except Exception as exc:
        logging.error("Echec clavier '>=': %s", exc)

    logging.error(
        "Impossible de selectionner l'operateur '>=' (items visibles=%d).", total
    )
    return False


def _fill_creation_date_value(page: Page, timestamp: str) -> bool:
    container = page.locator("#Field_ComponentcreationDate").first
    if not container.count():
        return False
    value_input = container.locator(
        "input.x-form-text:not(.x-triggerfield-noedit)"
    ).last
    if not value_input.count():
        logging.error("Input valeur 'Date de création' introuvable.")
        return False
    # Le champ accepte les millisecondes -> on garde le timestamp complet
    filter_value = timestamp
    try:
        value_input.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    try:
        value_input.click(force=True, timeout=2500)
        value_input.fill("")
        value_input.type(filter_value, delay=15)
        page.wait_for_timeout(200)
        value_input.press("Tab")
        logging.info("Date de création filtre = '%s'", filter_value)
        return True
    except PlaywrightTimeoutError:
        logging.error("Saisie timestamp echouee.")
        return False


def _click_execute_criteria(page: Page) -> bool:
    # Plusieurs onglets peuvent contenir un bouton portant cet id : on prend
    # celui qui est REELLEMENT visible (onglet actif).
    visible = page.locator(
        "#Component_PAGE_FORM_0_executeCriteria_null:visible"
    ).first
    btn = visible if visible.count() else page.locator(
        "#Component_PAGE_FORM_0_executeCriteria_null"
    ).first
    if not btn.count():
        logging.error("Bouton 'Executer criteres' introuvable.")
        return False
    try:
        btn.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        btn.click(force=True, timeout=3000)
        page.wait_for_timeout(1200)
        # Instantly dismiss any warning/OK popup that appeared after execute
        try:
            page.evaluate(
                """
                () => {
                    const wins = document.querySelectorAll(
                        'div.x-window, div.x-window-plain, div.x-window-dlg'
                    );
                    for (const win of wins) {
                        const s = window.getComputedStyle(win);
                        if (s.display === 'none' || s.visibility === 'hidden') continue;
                        for (const btn of win.querySelectorAll('button')) {
                            if ((btn.textContent || '').trim().toUpperCase() === 'OK') {
                                btn.click();
                                return true;
                            }
                        }
                    }
                    return false;
                }
                """
            )
        except Exception:
            pass
        return True
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.error("Click executer criteres en timeout / non visible.")
        return False


def _select_first_result_row(page: Page) -> bool:
    row = page.locator("tr[id^='Component_PAGE_FORM_1_DataTable']").first
    if not row.count():
        row = page.locator("div.x-grid3-body tr.x-grid3-row").first
    if not row.count():
        logging.error("Aucune ligne de resultat trouvee.")
        return False
    checkbox = row.locator("input[type='checkbox']").first
    if checkbox.count():
        try:
            if not checkbox.is_checked():
                checkbox.check(force=True, timeout=2000)
        except Exception:
            try:
                checkbox.click(force=True, timeout=2000)
            except PlaywrightTimeoutError:
                pass
    else:
        try:
            row.click(force=True, timeout=2000)
        except PlaywrightTimeoutError:
            pass
    page.wait_for_timeout(300)
    return True


def _click_action_button(
    page: Page, button_text: str, container_id: Optional[str] = None
) -> bool:
    btn = None
    if container_id:
        btn = page.locator(f'[id="{container_id}"] button.x-btn-text').first
    if btn is None or not btn.count():
        btn = page.locator("button.x-btn-text").filter(has_text=button_text).first
    if not btn.count():
        btn = page.get_by_role("button", name=button_text).first
    if not btn.count():
        logging.error("Bouton '%s' introuvable.", button_text)
        return False
    try:
        btn.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        btn.click(force=True, timeout=3000)
        page.wait_for_timeout(800)
        return True
    except PlaywrightTimeoutError:
        logging.error("Click '%s' en timeout.", button_text)
        return False


def run_validation_or_activation(
    page: Page,
    *,
    tree_path: List[str],
    action_label: str,
    action_button_id: str,
    timestamp: str,
    screenshot_dir: Optional[Path] = None,
    step_label: str = "step",
) -> bool:
    # Tentative avec retry : si l'ecran de criteres ne charge pas, on referme
    # tout et on rejoue la navigation (max 2 essais).
    for attempt in range(1, 3):
        # Purge toute pop-up modale residuelle qui pourrait bloquer le menu
        _force_close_all_modals(page)
        if not click_top_level_menu(page, TOP_LEVEL_MENU):
            return False
        if not navigate_tree_path(
            page, tree_path, final_selector="#Field_ComponentcreationDate"
        ):
            return False
        # Verifie explicitement que le formulaire est rendu
        try:
            page.wait_for_selector(
                "#Field_ComponentcreationDate", state="visible", timeout=8000
            )
            break
        except PlaywrightTimeoutError:
            logging.warning(
                "Ecran '%s' non charge (essai %d/2), on retente.",
                tree_path[-1], attempt,
            )
            close_active_tab(page)
            page.wait_for_timeout(300)
    else:
        logging.error("Ecran '%s' indisponible apres 2 essais.", tree_path[-1])
        return False

    if not _select_creation_date_operator_ge(page):
        return False
    if not _fill_creation_date_value(page, timestamp):
        return False
    if not _click_execute_criteria(page):
        return False
    if not _select_first_result_row(page):
        return False
    if not _click_action_button(page, action_label, container_id=action_button_id):
        return False
    # Pop-ups (peuvent prendre ~30s a apparaitre cote serveur).
    # Non bloquant : on poursuit meme si rien n'apparait dans le delai.
    _dismiss_notification_popup(
        page,
        timeout_ms=35000,
        screenshot_dir=screenshot_dir,
        step_label=step_label,
    )
    # Fermeture immediate de l'onglet courant
    close_active_tab(page)
    logging.info("Action '%s' effectuee.", action_label)
    return True


# ---------------------------------------------------------------------------
# Flux post-activation : Consultation -> Show History -> Executions -> Paiements
# ---------------------------------------------------------------------------

def _build_screenshot_dir(type_ost_value: str) -> Path:
    safe = _safe_filename(type_ost_value) or "OST"
    target = SCREENSHOTS_ROOT / f"process_OST_{safe}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _right_click_first_grid_row(page: Page) -> bool:
    """Right-click sur la 1ere ligne de la grille principale ExtJS."""
    selectors = [
        "tr[id^='Component_PAGE_FORM_1_DataTable']",
        "div.x-grid3-body tr.x-grid3-row",
    ]
    row = None
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count():
            row = loc
            break
    if row is None or not row.count():
        logging.error("Aucune ligne de resultat pour right-click.")
        return False
    try:
        row.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        row.click(button="right", force=True, timeout=4000)
        page.wait_for_timeout(500)
        return True
    except PlaywrightTimeoutError:
        logging.error("Right-click ligne en timeout.")
        return False


def _select_grid_row_by_column(
    page: Page,
    column_class: str,
    pattern,
    *,
    action: str = "right",
) -> bool:
    """Trouve dans la grille ExtJS la 1ere ligne dont la cellule
    `td.x-grid3-td-<column_class>` matche `pattern` (regex ou chaine).
    Si trouvee, fait `action` ('right' ou 'left'). Sinon log les valeurs
    disponibles pour aider a diagnostiquer."""
    rx = (
        pattern
        if hasattr(pattern, "search")
        else re.compile(re.escape(str(pattern)), re.IGNORECASE)
    )
    rows = page.locator("tr[id^='Component_PAGE_FORM_1_DataTable']")
    if not rows.count():
        rows = page.locator("div.x-grid3-body tr.x-grid3-row")
    total = rows.count()
    if not total:
        logging.error("Aucune ligne de resultat dans la grille.")
        return False

    available: List[str] = []
    target = None
    for idx in range(total):
        row = rows.nth(idx)
        cell = row.locator(f"td.x-grid3-td-{column_class}").first
        if not cell.count():
            continue
        try:
            text = (cell.inner_text() or "").strip()
        except Exception:
            continue
        available.append(text)
        if rx.search(text):
            target = row
            break

    if target is None:
        logging.error(
            "Aucune ligne ne matche %s dans la colonne '%s'. Valeurs : %s",
            rx.pattern, column_class, available,
        )
        return False

    try:
        target.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    try:
        target.click(
            button="right" if action == "right" else "left",
            force=True,
            timeout=4000,
        )
        page.wait_for_timeout(500)
        return True
    except PlaywrightTimeoutError:
        logging.error("Click (%s) ligne en timeout.", action)
        return False


def _click_context_menu_item(
    page: Page,
    label_pattern,
    *,
    nth: int = 0,
    timeout_ms: int = 4000,
) -> bool:
    """
    Clique l'item du menu contextuel ExtJS dont le texte matche `label_pattern`.
    `label_pattern` peut etre une chaine ou un re.Pattern.
    Si plusieurs items matchent, prend l'item d'index `nth`.
    """
    pattern = (
        label_pattern
        if hasattr(label_pattern, "search")
        else re.compile(re.escape(str(label_pattern)), re.IGNORECASE)
    )
    deadline = 0
    while deadline < timeout_ms:
        items = page.locator(
            ".x-menu:visible .x-menu-item-text, "
            ".x-menu:visible a.x-menu-item, "
            ".x-menu:visible .x-menu-item"
        )
        total = items.count()
        matched = []
        for idx in range(total):
            try:
                txt = (items.nth(idx).inner_text() or "").strip()
            except Exception:
                continue
            if txt and pattern.search(txt):
                matched.append(idx)
        if matched:
            target_idx = matched[nth] if nth < len(matched) else matched[-1]
            target = items.nth(target_idx)
            try:
                target.click(force=True, timeout=2000)
                page.wait_for_timeout(500)
                return True
            except PlaywrightTimeoutError:
                pass
        page.wait_for_timeout(150)
        deadline += 150
    logging.error("Item de menu contextuel introuvable : %r", label_pattern)
    return False


def _scrape_main_reference_from_history(page: Page) -> Optional[str]:
    """
    Apres ouverture de la fenetre/panneau 'Show History', recupere la valeur
    de l'OST Reference Principale. Cherche dans le DERNIER conteneur visible
    (window/panel) la 1ere cellule de table avec un texte non vide qui
    ressemble a une reference (lettres + chiffres).
    """
    page.wait_for_timeout(1500)
    value = page.evaluate(
        """
        () => {
          // Conteneurs candidats : derniere window visible, sinon dernier
          // tab panel actif rendu apres l'action
          const wins = Array.from(document.querySelectorAll('.x-window'))
            .filter(w => w.offsetParent !== null);
          const panels = Array.from(document.querySelectorAll(
            '.x-tab-panel-body .x-panel-body'
          )).filter(p => p.offsetParent !== null);
          const containers = wins.concat(panels);
          if (!containers.length) return null;
          const root = containers[containers.length - 1];

          // Pattern d'une ref : >= 4 chars, contient des chiffres
          const looksLikeRef = (s) => {
            const t = (s||'').trim();
            if (t.length < 4) return false;
            return /\\d/.test(t) && /^[A-Za-z0-9._:\\-/]+$/.test(t);
          };

          // 1) Premiere cellule td > div correspondant
          const cells = root.querySelectorAll('td > div, td');
          for (const c of cells) {
            const txt = (c.innerText || c.textContent || '').trim();
            if (looksLikeRef(txt)) return txt;
          }
          // 2) Fallback : premier <input> avec valeur non vide
          const inputs = root.querySelectorAll('input.x-form-text');
          for (const i of inputs) {
            const v = (i.value || '').trim();
            if (looksLikeRef(v)) return v;
          }
          return null;
        }
        """
    )
    if value:
        logging.info("OST Reference Principale scrappee : '%s'", value)
        return value
    logging.error("Impossible de scrapper l'OST Reference Principale.")
    return None


def _fill_main_reference_and_search(page: Page, ref_value: str) -> bool:
    """Remplit #Field_ComponentcA_mainReference puis clique 'Execute Search'."""
    try:
        page.wait_for_selector(
            "#Field_ComponentcA_mainReference", state="visible", timeout=10_000
        )
    except PlaywrightTimeoutError:
        logging.error("Champ 'OST Reference Principale' non visible.")
        return False
    container = page.locator("#Field_ComponentcA_mainReference").first
    input_field = container.locator(
        "input.x-form-text:not(.x-triggerfield-noedit)"
    ).first
    if not input_field.count():
        logging.error("Input principal de la reference introuvable.")
        return False
    try:
        input_field.click(timeout=2000)
        input_field.fill("")
        input_field.type(ref_value, delay=20)
    except Exception as exc:
        logging.error("Saisie reference echouee : %s", exc)
        return False
    page.wait_for_timeout(200)
    return _click_execute_criteria(page)


def _navigate_under_top_menu(
    page: Page,
    top_menu: str,
    tree_segments: List[str],
    final_selector: str,
) -> bool:
    _force_close_all_modals(page)
    # Toujours fermer les onglets precedents pour eviter que des selecteurs
    # d'id matchent des elements caches d'un ancien ecran.
    close_all_tabs(page)
    page.wait_for_timeout(300)
    if not click_top_level_menu(page, top_menu):
        return False
    if not navigate_tree_path(page, tree_segments, final_selector=final_selector):
        return False
    try:
        page.wait_for_selector(final_selector, state="visible", timeout=10_000)
    except PlaywrightTimeoutError:
        logging.warning(
            "Selecteur final '%s' non visible, on poursuit.", final_selector
        )
    return True


def run_post_activation_flow(
    page: Page,
    *,
    type_ost_value: str,
    timestamp: str,
    screenshot_dir: Path,
) -> bool:
    """
    Apres Activation : se deconnecte, se reconnecte avec domaine 'awb', enchaine
    Consultation des annonces -> Show History (scrape ref) -> Executions Client
    OST d'Office -> Executions Marche OST d'Office -> Paiements Marche Adhoc ->
    Paiements Client Paiement Actuel. Capture toutes les pop-ups en screenshots.
    """
    # 1) Logout + relogin avec domaine awb
    logging.info("=== Post-activation : logout + relogin (domain=%s) ===",
                 AUTH_DOMAIN_POST)
    logout(page)
    if not login(page, domain=AUTH_DOMAIN_POST):
        logging.error("Re-login (domain=%s) echoue.", AUTH_DOMAIN_POST)
        return False

    # 2) Consultation des annonces -> filtre date >= timestamp -> execute
    if not _navigate_under_top_menu(
        page,
        TOP_LEVEL_MENU,
        TREE_PATH_CONSULTATION,
        "#Field_ComponentcreationDate",
    ):
        return False
    if not _select_creation_date_operator_ge(page):
        return False
    if not _fill_creation_date_value(page, timestamp):
        return False
    if not _click_execute_criteria(page):
        return False

    # 3) Right-click sur 1ere ligne -> Show History
    if not _right_click_first_grid_row(page):
        return False
    if not _click_context_menu_item(page, re.compile(r"show\s*history|historique",
                                                     re.IGNORECASE)):
        return False

    # 4) Scrape OST Reference Principale
    ref_value = _scrape_main_reference_from_history(page)
    if not ref_value:
        return False
    # Capture l'historique aussi (info)
    try:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(
            path=str(screenshot_dir / "02_show_history.png"), full_page=True
        )
    except Exception:
        pass

    # Ferme les onglets accumules (Show History + Consultation) avant de naviguer
    # aux ecrans suivants, sinon les selecteurs d'id matchent des elements caches.
    close_all_tabs(page)
    page.wait_for_timeout(400)

    # ------------------------------------------------------------------
    # Boucle sur les evenements de l'OST :
    #   pour chaque event => Exec Client + Exec Marche + Pay Marche Adhoc + Pay Client
    # ------------------------------------------------------------------
    events = POST_FLOW_BY_TYPE.get(_normalize_label(type_ost_value)) or []
    if not events:
        logging.error(
            "Aucun POST_FLOW_BY_TYPE pour '%s' : flux post-activation interrompu.",
            type_ost_value,
        )
        return False

    for ev_idx, event in enumerate(events, start=1):
        ev_key = event["key"]
        eca_label_rx = event["eca_label"]
        eca_name_rx = event["eca_name"]
        logging.info(
            "=== Event %d/%d (%s) : ecaLabel~%s | eCAName~%s ===",
            ev_idx, len(events), ev_key, eca_label_rx.pattern, eca_name_rx.pattern,
        )

        # 5) Executions Client > Calcul > OST d'Office
        if not _navigate_under_top_menu(
            page,
            TOP_LEVEL_EXECUTIONS,
            TREE_PATH_EXEC_CLIENT_OFFICE,
            "#Field_ComponentcA_mainReference",
        ):
            return False
        if not _fill_main_reference_and_search(page, ref_value):
            return False
        if not _select_grid_row_by_column(
            page, "ecaLabel", eca_label_rx, action="right"
        ):
            return False
        if not _click_context_menu_item(
            page, re.compile(r"calculer\s*ex[eé]cutions?", re.IGNORECASE)
        ):
            return False
        _dismiss_notification_popup(
            page, timeout_ms=35000,
            screenshot_dir=screenshot_dir,
            step_label=f"03_{ev_idx:02d}_{ev_key}_exec_client",
        )
        close_active_tab(page)

        # 6) Executions Marche > Calcul > OST d'Office
        if not _navigate_under_top_menu(
            page,
            TOP_LEVEL_EXECUTIONS,
            TREE_PATH_EXEC_MARKET_OFFICE,
            "#Field_ComponentcA_mainReference",
        ):
            return False
        if not _fill_main_reference_and_search(page, ref_value):
            return False
        if not _select_grid_row_by_column(
            page, "ecaLabel", eca_label_rx, action="right"
        ):
            return False
        if not _click_context_menu_item(
            page, re.compile(r"calculer\s*ex[eé]cutions?", re.IGNORECASE)
        ):
            return False
        _dismiss_notification_popup(
            page, timeout_ms=35000,
            screenshot_dir=screenshot_dir,
            step_label=f"04_{ev_idx:02d}_{ev_key}_exec_marche",
        )
        close_active_tab(page)

        # 7) Paiements Marche > Creer > Generer Ad-hoc
        if not _navigate_under_top_menu(
            page,
            TOP_LEVEL_PAYMENTS,
            TREE_PATH_PAY_MARKET_ADHOC,
            "#Field_ComponentcA_mainReference",
        ):
            return False
        if not _fill_main_reference_and_search(page, ref_value):
            return False
        # 1ere ligne de resultat (selection par checkbox / clic)
        if not _select_first_result_row(page):
            return False
        # Bouton "Generate Market Payment"
        gen_btn = page.locator(
            '[id="Component_PAGE_FORM_1_Generate MarketPayment_null"] button.x-btn-text'
        ).first
        if not gen_btn.count():
            gen_btn = page.locator("button:has-text('Generate Market Payment')").first
        if not gen_btn.count():
            logging.error("Bouton 'Generate Market Payment' introuvable.")
            return False
        try:
            gen_btn.click(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.error("Click 'Generate Market Payment' en timeout.")
            return False
        _dismiss_notification_popup(
            page, timeout_ms=35000,
            screenshot_dir=screenshot_dir,
            step_label=f"05_{ev_idx:02d}_{ev_key}_pay_market_adhoc",
        )
        close_active_tab(page)

        # 8) Paiements Client > Creation > Paiement Actuel
        if not _navigate_under_top_menu(
            page,
            TOP_LEVEL_PAYMENTS,
            TREE_PATH_PAY_CLIENT_ACTUAL,
            "#Field_ComponentcA_mainReference",
        ):
            return False
        if not _fill_main_reference_and_search(page, ref_value):
            return False
        if not _select_grid_row_by_column(
            page, "eCAName", eca_name_rx, action="right"
        ):
            return False
        if not _click_context_menu_item(
            page, re.compile(r"calculer\s*paiement", re.IGNORECASE)
        ):
            return False
        _dismiss_notification_popup(
            page, timeout_ms=35000,
            screenshot_dir=screenshot_dir,
            step_label=f"06_{ev_idx:02d}_{ev_key}_pay_client",
        )
        close_active_tab(page)

    logging.info("=== Flux post-activation termine OK ===")
    return True


# ---------------------------------------------------------------------------
# Resolution du fichier de variables specifique au Type OST
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", name).strip()


def resolve_form_variables_file(type_ost: str) -> Optional[Path]:
    """Cherche variable_saisies/ost_awb_<type>.txt en testant plusieurs variantes."""
    candidates = [
        VARIABLES_DIR / f"ost_awb_{type_ost}.txt",
        VARIABLES_DIR / f"ost_awb_{_safe_filename(type_ost)}.txt",
        VARIABLES_DIR / f"ost_awb_{_strip_accents(type_ost)}.txt",
    ]
    for path in candidates:
        if path.exists():
            return path
    target = _normalize(type_ost)
    for path in VARIABLES_DIR.glob("ost_awb_*.txt"):
        stem = _normalize(path.stem.replace("ost_awb_", ""))
        if stem == target:
            return path
    return None


def resolve_field_specs(type_ost: str) -> Optional[List[dict]]:
    return FORM_FIELDS_BY_TYPE.get(_normalize_label(type_ost))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(type_ost_override: Optional[str] = None) -> int:
    # 1. Recuperer le Type OST :
    #    Priorite : argument CLI / parametre > variable d'env OST_AWB_TYPE
    #             > ost_awb.txt > fichier dedie ost_awb_<type>.txt detecte auto.
    type_ost_value = (type_ost_override or os.getenv("OST_AWB_TYPE", "")).strip()
    if type_ost_value:
        logging.info("Type OST force par argument/env : '%s'", type_ost_value)
        type_entries: List[Tuple[str, str]] = []
    else:
        type_entries = load_variables_ordered(TYPE_OST_FILE)
        type_ost_value = consume_value(type_entries, "Type OST") or ""

    form_file: Optional[Path] = None
    if type_ost_value:
        form_file = resolve_form_variables_file(type_ost_value)
    if form_file is None:
        candidates = list(VARIABLES_DIR.glob("ost_awb_*.txt"))
        if len(candidates) == 1:
            form_file = candidates[0]
            logging.info("Fichier formulaire detecte automatiquement : %s", form_file)
        elif len(candidates) > 1 and type_ost_value:
            logging.error(
                "Plusieurs fichiers ost_awb_*.txt presents et aucun ne correspond a '%s'.",
                type_ost_value,
            )
            return 2

    if form_file is None:
        logging.error(
            "Fichier de variables formulaire introuvable. Attendu : %s",
            VARIABLES_DIR / "ost_awb_<TypeOST>.txt",
        )
        return 2

    form_entries = load_variables_ordered(form_file)
    if not type_ost_value:
        type_ost_value = consume_value(form_entries, "Type OST") or ""
    else:
        # Si le fichier dedie redeclare 'Type OST', on consomme aussi son entree
        # afin qu'elle ne soit pas confondue avec un champ de saisie.
        consume_value(form_entries, "Type OST")

    if not type_ost_value:
        logging.error("Impossible de determiner 'Type OST'.")
        return 2

    field_specs = resolve_field_specs(type_ost_value)
    if field_specs is None:
        logging.error(
            "Aucun mapping de champs defini pour le Type OST '%s'.", type_ost_value
        )
        return 2

    logging.info("Type OST : '%s' | fichier : %s", type_ost_value, form_file)
    logging.info("Entrees a remplir : %d", len(form_entries))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            locale="fr-FR",
            ignore_https_errors=True,
            no_viewport=True,
        )
        page = context.new_page()
        page.add_init_script(
            "window.addEventListener('contextmenu',"
            " e => e.preventDefault(), { capture: true });"
        )

        try:
            if not login(page):
                return 1

            # ---- Creation ----
            if not click_top_level_menu(page, TOP_LEVEL_MENU):
                return 1
            if not navigate_tree_path(
                page, TREE_PATH_CREATION, final_selector="#Field_ComponentcaType"
            ):
                return 1
            if not select_type_ost(page, type_ost_value):
                logging.error("Selection 'Type OST' echouee.")
                return 1

            # Attendre l'apparition du formulaire dedie (1er ET dernier champ)
            try:
                page.wait_for_selector(
                    f'[id="{field_specs[0]["container"]}"]', timeout=10_000
                )
                page.wait_for_selector(
                    f'[id="{field_specs[-1]["container"]}"]', timeout=10_000
                )
            except PlaywrightTimeoutError:
                logging.warning(
                    "Formulaire pas entierement charge, on tente le remplissage."
                )

            fill_form(page, field_specs, form_entries)

            screenshot_dir = _build_screenshot_dir(type_ost_value)
            logging.info("Dossier screenshots pop-ups : %s", screenshot_dir)

            timestamp = click_save_and_capture_timestamp(
                page, screenshot_dir=screenshot_dir
            )
            if not timestamp:
                return 1
            logging.info("Horodatage de creation : %s", timestamp)

            # ---- Validation ----
            # (close_active_tab est deja fait par click_save_and_capture_timestamp)
            if not run_validation_or_activation(
                page,
                tree_path=TREE_PATH_VALIDATION,
                action_label="Valider l'annonce",
                action_button_id="Component_PAGE_FORM_1_moveToReliableCA_null",
                timestamp=timestamp,
                screenshot_dir=screenshot_dir,
                step_label="02_validation",
            ):
                return 1

            # ---- Activation ----
            # (close_active_tab est deja fait par run_validation_or_activation)
            if not run_validation_or_activation(
                page,
                tree_path=TREE_PATH_ACTIVATION,
                action_label="Activer l'annonce",
                action_button_id="Component_PAGE_FORM_1_activateCA_null",
                timestamp=timestamp,
                screenshot_dir=screenshot_dir,
                step_label="03_activation",
            ):
                return 1

            # ---- Flux post-activation (Consultation -> Executions -> Paiements)
            if not run_post_activation_flow(
                page,
                type_ost_value=type_ost_value,
                timestamp=timestamp,
                screenshot_dir=screenshot_dir,
            ):
                logging.warning("Flux post-activation incomplet.")

            logging.info("Process OST complet OK.")
            page.wait_for_timeout(2000)
        finally:
            for name, action in (
                ("page", lambda: (not page.is_closed()) and page.close()),
                ("context", context.close),
                ("browser", browser.close),
            ):
                try:
                    action()
                except Exception as exc:
                    logging.debug("Ignore close %s: %s", name, exc)

    return 0


if __name__ == "__main__":
    # Type OST optionnel en argument CLI : python ost_awb.py "Paiement de dividendes en espèce"
    cli_type = " ".join(sys.argv[1:]).strip() or None
    sys.exit(run(type_ost_override=cli_type))
