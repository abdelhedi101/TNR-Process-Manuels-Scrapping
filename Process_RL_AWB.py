import logging
import os
import re
import time
import traceback
from pathlib import Path
from typing import Dict

import Process_RL_CDG as base
import saisie_awb as awb
from saisie_awb import (
    load_or_initialize_saisie_variables,
    SAISIE_VARIABLES_FILE,
    SAISIE_FIELD_SPECS,
    capture_failure,
    handle_error_dialog,
    dismiss_save_success_popup_if_present,
)
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError, sync_playwright

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)

LOGIN_ENTRY = os.getenv("MODULE_URL", "http://10.1.140.244:9082/MegaCustody/login.jsp")
MEGACOMMON_ENTRY = os.getenv("MEGACOMMON_URL", "http://10.1.140.244:9080/MegaCommon/login.jsp")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/AWB/custody/process_rl.txt"))
AWB_PROCESS_RL_VARIABLES_FILE = Path(os.getenv("AWB_PROCESS_RL_VARIABLES_FILE", "variable_saisies/Instruction_Client_awb.txt"))
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "migration")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Vermeg+123")
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "awb")
AUTH_TYPE = os.getenv("AUTH_TYPE", "standard").strip().lower()
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}

MEGACOMMON_POSITION_CONSULTATION_PATH = (
    "position",
    "titres",
    "gestion de la position client",
    "consultation",
)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_") or "value"


def is_target_closed_error(exc: Exception) -> bool:
    return "Target page, context or browser has been closed" in str(exc)


original_dismiss_help_description_popup_if_present = awb.dismiss_help_description_popup_if_present

def safe_dismiss_help_description_popup_if_present(page):
    try:
        return original_dismiss_help_description_popup_if_present(page)
    except PlaywrightError as exc:
        if is_target_closed_error(exc):
            logging.warning("Ignored closed page during help popup handling")
            return False
        raise


def take_awb_save_screenshot(page, module_name: str, path_label: str, suffix: str) -> None:
    try:
        if page.is_closed():
            logging.info("Skipping AWB save screenshot because page is already closed for %s", path_label)
            return
    except Exception:
        logging.info("Skipping AWB save screenshot because page state is unavailable for %s", path_label)
        return

    target_dir = SCREENSHOT_DIR / "awb" / "megacustody" / slugify(path_label.split('>')[0].strip())
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(path_label)}_{suffix}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(target_dir / filename), full_page=True)
        logging.info("Saved AWB screenshot for %s at %s", path_label, target_dir / filename)
    except PlaywrightError as exc:
        if is_target_closed_error(exc):
            logging.warning("Skipped AWB save screenshot because page closed for %s", path_label)
        else:
            logging.warning("AWB save screenshot failed for %s: %s", path_label, exc)


original_wait_for_and_dismiss_success_popup = awb.wait_for_and_dismiss_success_popup

def wrapped_wait_for_and_dismiss_success_popup(page, path_label: str, timeout_ms: int = 10000) -> bool:
    result = original_wait_for_and_dismiss_success_popup(page, path_label, timeout_ms=timeout_ms)
    if result:
        take_awb_save_screenshot(page, "AWB", path_label, "save_message")
    return result

awb.dismiss_help_description_popup_if_present = safe_dismiss_help_description_popup_if_present
awb.wait_for_and_dismiss_success_popup = wrapped_wait_for_and_dismiss_success_popup

# ── Save popup: wait (blocking) before allowing close_work_window to run ─────
# dismiss_save_success_popup_if_present is called non-blocking by traverse_menu_paths
# BEFORE close_work_window, so the window can close before the popup appears.
# Replacing it with a polling version ensures we wait up to 12 s for the popup.
_original_dismiss_save_success_popup_if_present = awb.dismiss_save_success_popup_if_present

def _wait_for_save_popup_before_close(page, path_label: str) -> bool:
    """Blocking: polls for save success popup up to 12 s before returning False.

    Skipped for market-action paths (Appariement / Dénouement) where the
    workflow already handled its own confirmation popup — otherwise the 12 s
    polling pokes the DOM and may briefly trigger an unrelated window.
    """
    if path_label in _MARKET_HANDLED_PATHS:
        return False
    normalized = path_label.lower()
    if "appariement" in normalized or "dénouement" in normalized or "denouement" in normalized:
        return False
    deadline = time.time() + 12.0
    while time.time() < deadline:
        if _original_dismiss_save_success_popup_if_present(page, path_label):
            return True
        page.wait_for_timeout(300)
    return False

awb.dismiss_save_success_popup_if_present = _wait_for_save_popup_before_close


# ── OK popup: quick pre-check before the slow 6-second polling loop ──────────
# saisie_awb.dismiss_ok_popup_if_present blindly polls 6 s every time it is
# invoked between paths. When no popup is actually present (the common case
# after a market workflow already dismissed its own popup), this wastes 6 s
# per path. The wrapper does a fast (≤300 ms) JS scan first; only if a
# candidate popup element exists do we delegate to the original 6-second logic.
_original_awb_dismiss_ok_popup_if_present = awb.dismiss_ok_popup_if_present


def _fast_awb_dismiss_ok_popup_if_present(page, path_label: str) -> bool:
    try:
        if page.is_closed():
            return False
    except Exception:
        return False

    # Fast detect: any visible OK-bearing popup element right now?
    try:
        has_popup = page.evaluate(
            """
            () => {
                const candidates = document.querySelectorAll(
                    'div.x-window:not(.x-hidden), div.x-window-plain, div.x-window-dlg, div.ext-mb-content'
                );
                for (const el of candidates) {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const text = (el.textContent || '').trim().toUpperCase();
                    if (text.includes('OK')) return true;
                }
                return false;
            }
            """
        )
    except (PlaywrightTimeoutError, PlaywrightError):
        has_popup = False

    if not has_popup:
        logging.info("No OK popup detected (fast scan) for %s; skipping 6s wait", path_label)
        return False

    return _original_awb_dismiss_ok_popup_if_present(page, path_label)


awb.dismiss_ok_popup_if_present = _fast_awb_dismiss_ok_popup_if_present


def normalize_position_basis_value(raw_value: str) -> str:
    normalized = (raw_value or "").strip()
    if not normalized:
        return "Date métier"

    lower = normalized.lower().replace(" ", "")
    if lower in {"businessdate"}:
        return "Date métier"
    if lower in {"datemetier"}:
        return "Date métier"
    return normalized


# fill_saisie_instruction_client_form: delegated to saisie_awb — awb.traverse_menu_paths calls it directly


def _get_app_affiliate(page) -> str:
    """Read the current affiliate/domain shown in the app header toolbar.

    The Mega header row has the logout button at td[4]; the affiliate label
    is usually displayed in td[1], td[2] or td[3] of the same row.
    Returns the affiliate text in lowercase, or empty string if undetectable.
    """
    header_row_sel = (
        "xpath=/html/body/div[2]/div/div[1]/div[2]/div[1]/table/tbody/tr[1]/td"
        "/div/table/tbody/tr"
    )
    generic_selectors = [
        "xpath=/html/body/div[2]/div/div[1]/div[2]/div[1]/table/tbody/tr[1]/td/div/table/tbody/tr/td[1]/div",
        "xpath=/html/body/div[2]/div/div[1]/div[2]/div[1]/table/tbody/tr[1]/td/div/table/tbody/tr/td[2]/div",
        "xpath=/html/body/div[2]/div/div[1]/div[2]/div[1]/table/tbody/tr[1]/td/div/table/tbody/tr/td[3]/div",
    ]
    for sel in generic_selectors:
        try:
            el = page.locator(sel).first
            if el.count():
                text = (el.inner_text(timeout=2000) or "").strip().lower()
                if text:
                    return text
        except Exception:
            continue
    # Fallback: read all td content from the toolbar row
    try:
        row = page.locator(header_row_sel).first
        if row.count():
            cells = row.locator("td")
            for i in range(min(cells.count(), 4)):
                try:
                    text = (cells.nth(i).inner_text(timeout=1000) or "").strip().lower()
                    if text and text not in ("|", "-", ""):
                        return text
                except Exception:
                    continue
    except Exception:
        pass
    return ""


def _awb_login(page, entry_url: str) -> bool:
    """Login to any AWB module using AWB-specific domain/affiliate credentials.

    Handles SSO auto-login with wrong affiliate (e.g. ALL) by forcing logout
    and re-logging in with the correct AUTH_DOMAIN (e.g. awb).
    """
    app_ready = (
        "div[role='treeitem'], "
        "button:has-text('Position'), "
        "button:has-text('Referentiel'), "
        "a.x-tab-strip-text"
    )
    login_form_sel = "#username, input[name='username'], input[name='j_username']"

    logging.info("AWB login: navigating to %s", entry_url)
    try:
        page.goto(entry_url, wait_until="domcontentloaded", timeout=30000)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.error("AWB login: failed to navigate to %s: %s", entry_url, exc)
        return False

    # Poll for either the login form or the app shell (SSO may redirect silently)
    deadline = time.time() + 35.0
    state = "none"
    while time.time() < deadline:
        try:
            if page.locator(app_ready).count():
                state = "app"
                break
            if page.locator(login_form_sel).count():
                state = "login"
                break
        except Exception:
            pass
        try:
            page.wait_for_timeout(300)
        except Exception:
            break

    if state == "app":
        # SSO logged in automatically — check if the affiliate is the expected one
        current_affiliate = _get_app_affiliate(page)
        expected = AUTH_DOMAIN.strip().lower()
        logging.info(
            "AWB login: SSO auto-login detected for %s (affiliate detected='%s', expected='%s')",
            entry_url, current_affiliate, expected,
        )
        affiliate_ok = expected and current_affiliate and expected in current_affiliate
        if affiliate_ok:
            logging.info("AWB login: correct affiliate '%s' confirmed, no relogin needed", current_affiliate)
            return True
        # Wrong affiliate (e.g. ALL) — force logout and relogin with AUTH_DOMAIN
        logging.info(
            "AWB login: wrong affiliate '%s', forcing logout to relogin with affiliate='%s'",
            current_affiliate or "(undetected)", AUTH_DOMAIN,
        )
        awb.logout_to_login_page(page, "AWB", entry_url)
        try:
            page.wait_for_selector(login_form_sel, timeout=15000)
        except PlaywrightTimeoutError:
            logging.error("AWB login: login form did not appear after forced logout for %s", entry_url)
            return False
        state = "login"

    if state == "login":
        if not awb._submit_credentials(page, AUTH_USERNAME, AUTH_PASSWORD, AUTH_DOMAIN):
            return False
        try:
            page.wait_for_selector(app_ready, timeout=45000)
        except PlaywrightTimeoutError:
            if page.locator(login_form_sel).count():
                logging.error("AWB login: form still visible after submit for %s", entry_url)
                return False
        logging.info("AWB login: successful for %s (domain=%s)", entry_url, AUTH_DOMAIN)
        return True

    logging.error("AWB login: neither login form nor app shell appeared for %s", entry_url)
    return False


# Selector for the Référence client criteria input in appariement/dénouement windows
_CLIENT_REF_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_atomicCriteria_clientReference_criteria']"

# Set of path_labels already fully handled by _awb_run_market_action_workflow.
# Used to short-circuit saisie_awb's downstream row-search / view-edit fallback
# (which would otherwise reopen empty windows / spend ~30 s scanning rows).
_MARKET_HANDLED_PATHS: set = set()


def _awb_run_market_action_workflow(page, module_name: str, path_label: str, action_label: str) -> bool:
    """Workflow complet appariement/dénouement AWB.

    Déclenché juste après ouverture du menu (avant que saisie_awb ne cherche
    table.x-form-search ou PalmyraGrid_0). Séquence inspirée de
    Process_RL_CDG.run_market_result_action_workflow :
      1. Remplir Référence client dans le formulaire de critères
      2. Cliquer Execute pour lancer la recherche filtrée
      3. Sélectionner la première ligne du résultat
      4. Cliquer le bouton Match / Dénouer
      5. Attendre et fermer la popup de confirmation
      6. Fermer la fenêtre de travail
    """
    logging.info("AWB market workflow START: %s → %s", path_label, action_label)

    # 0. Attendre que la fenêtre Appariement/Dénouement soit réellement ouverte.
    # Poll rapide (100ms) via Playwright wait_for_selector — beaucoup plus
    # efficace que la boucle Python avec multiples appels is_visible.
    window_ready = False
    try:
        page.wait_for_selector(
            f"{_CLIENT_REF_INPUT_SELECTOR}, {awb.EXECUTE_CRITERIA_SELECTOR}",
            timeout=10000,
            state="visible",
        )
        window_ready = True
    except (PlaywrightTimeoutError, PlaywrightError):
        window_ready = False

    if not window_ready:
        logging.warning("Fenêtre %s pas ouverte après 10s — abandon du workflow", path_label)
        return False

    logging.info("Fenêtre %s ouverte, lancement du workflow", path_label)

    # 1. Remplir le champ Référence client (JS direct set — instantané)
    variables = load_or_initialize_saisie_variables(SAISIE_VARIABLES_FILE)
    client_ref = variables.get("client_reference", "").strip()
    if client_ref:
        ref_field = page.locator(_CLIENT_REF_INPUT_SELECTOR).first
        if ref_field.count():
            try:
                ref_field.evaluate(
                    "(el, value) => { el.focus(); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
                    client_ref,
                )
                logging.info("Filled client_reference=%s for %s", client_ref, path_label)
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                logging.warning("Could not fill client_reference for %s: %s", path_label, exc)
        else:
            logging.warning("Champ Référence client introuvable pour %s", path_label)

    # 2. Exécuter la recherche — viser uniquement le bouton visible
    execute_locator = page.locator(awb.EXECUTE_CRITERIA_SELECTOR)
    execute_button = None
    for i in range(execute_locator.count()):
        candidate = execute_locator.nth(i)
        try:
            if candidate.is_visible():
                execute_button = candidate
                break
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    if execute_button is not None:
        try:
            execute_button.click(force=True, timeout=3000)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        try:
            base.handle_execute_search_popup(page, module_name, path_label)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        logging.info("Recherche exécutée pour %s", path_label)
    else:
        logging.warning("Bouton Execute introuvable/non visible pour %s", path_label)
        awb.close_work_window(page, path_label)
        return False

    # 3. Sélectionner la première ligne résultat (un seul wait_for_selector
    # combiné pour tous les sélecteurs candidats)
    row_selector = "[id$='PalmyraGrid_0'], div.x-grid3-body div.x-grid3-row, tr.x-grid3-row"
    result_row = None
    try:
        page.wait_for_selector(row_selector, timeout=6000, state="visible")
        result_row = page.locator(row_selector).first
    except (PlaywrightTimeoutError, PlaywrightError):
        result_row = None

    if result_row is None or not result_row.count():
        logging.warning("Aucune ligne résultat avant %s pour %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        awb.close_work_window(page, path_label)
        return False

    try:
        result_row.click(force=True, timeout=3000)
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.warning("Clic ligne résultat échoué pour %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
        awb.close_work_window(page, path_label)
        return False

    # 4. Cliquer le bouton action (Match / Dénouer)
    action_candidates = [
        page.locator(f"xpath=//button[contains(normalize-space(string(.)), '{action_label}')]").first,
        page.locator("button.x-btn-text").filter(
            has_text=re.compile(rf"^\s*{re.escape(action_label)}\s*$", re.IGNORECASE)
        ).first,
        page.get_by_role(
            "button", name=re.compile(rf"^\s*{re.escape(action_label)}\s*$", re.IGNORECASE)
        ).first,
    ]
    action_button = None
    for candidate in action_candidates:
        try:
            if candidate.count():
                action_button = candidate
                break
        except PlaywrightError:
            continue

    if action_button is None:
        logging.warning("Bouton %s introuvable pour %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        awb.close_work_window(page, path_label)
        return False

    try:
        action_button.click(force=True, timeout=4000)
        logging.info("Cliqué bouton %s pour %s", action_label, path_label)
    except PlaywrightTimeoutError:
        logging.warning("Clic bouton %s timeout pour %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        awb.close_work_window(page, path_label)
        return False

    # 5. Attendre la popup OK (une seule), screenshot, puis UN SEUL clic OK.
    popup_found = base.wait_for_market_action_popup(
        page, module_name, path_label, action_label, timeout_ms=20000
    )
    if popup_found:
        try:
            awb.dismiss_ok_popup_if_present(page, path_label)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

    # 6. Fermer la fenêtre de travail (avant ouverture du menu suivant)
    try:
        awb.close_work_window(page, path_label)
    except (PlaywrightTimeoutError, PlaywrightError):
        pass

    # Marquer ce path comme traité pour que la suite saisie_awb
    # (right_click_row_after_execute / awb_view_then_edit_flow) soit no-op.
    _MARKET_HANDLED_PATHS.add(path_label)

    logging.info("AWB market workflow DONE: %s", path_label)
    return popup_found


# Patch awb.click_search_button_if_available pour intercepter Appariement/Dénouement.
# Hook choisi car il est appelé juste après ouverture du leaf, AVANT que
# saisie_awb cherche table.x-form-search / PalmyraGrid_0 (qui n'apparaissent
# que si l'utilisateur a d'abord rempli les critères et exécuté la recherche).
# Pour les autres menus (Saisie Instruction Client, etc.) on délègue à
# l'implémentation originale.
_original_awb_click_search_button = awb.click_search_button_if_available


def _custom_awb_click_search_button_if_available(page, module_name: str, path_label: str) -> bool:
    normalized_path = tuple(part.strip().lower() for part in path_label.split(">"))
    if any("appariement" in part for part in normalized_path):
        _awb_run_market_action_workflow(page, module_name, path_label, "Match")
        # Retourner False pour que la suite saisie_awb tombe dans capture_failure
        # (no-op si pas d'erreur) sans rejouer le clic Execute.
        return False
    if any("dénouement" in part or "denouement" in part for part in normalized_path):
        _awb_run_market_action_workflow(page, module_name, path_label, "Dénouer")
        return False
    return _original_awb_click_search_button(page, module_name, path_label)


awb.click_search_button_if_available = _custom_awb_click_search_button_if_available


# Patch right_click_row_after_execute: skip when path already handled by our
# market workflow — otherwise saisie_awb spends ~30 s scanning rows that are
# no longer present (work window was closed by our workflow).
_original_awb_right_click_row_after_execute = awb.right_click_row_after_execute


def _custom_awb_right_click_row_after_execute(page, module_name: str, path_label: str):
    if path_label in _MARKET_HANDLED_PATHS:
        logging.info("Skip right_click_row_after_execute: %s already handled by market workflow", path_label)
        return None
    return _original_awb_right_click_row_after_execute(page, module_name, path_label)


awb.right_click_row_after_execute = _custom_awb_right_click_row_after_execute


# Patch awb_view_then_edit_flow: no-op for paths already handled.
_original_awb_view_then_edit_flow = awb.awb_view_then_edit_flow


def _custom_awb_view_then_edit_flow(page, module_name: str, path_label: str) -> None:
    if path_label in _MARKET_HANDLED_PATHS:
        logging.info("Skip awb_view_then_edit_flow: %s already handled by market workflow", path_label)
        return None
    return _original_awb_view_then_edit_flow(page, module_name, path_label)


awb.awb_view_then_edit_flow = _custom_awb_view_then_edit_flow



def load_awb_process_rl_variables(file_path: Path) -> Dict[str, str]:
    defaults = {
        "client_sec_account": "",
        "tradable_asset": "",
        "trade_date": "",
        "position_basis": "Date métier",
    }
    values = defaults.copy()

    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                if "=" not in cleaned:
                    continue
                key, raw_value = cleaned.split("=", 1)
                key = key.strip()
                value = raw_value.strip()
                if key == "position_basis":
                    value = normalize_position_basis_value(value)
                values[key] = value
    else:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as fh:
        fh.write("# Valeurs modifiables pour le menu Process RL AWB\n")
        for key, value in values.items():
            fh.write(f"{key}={value}\n")

    logging.info("Loaded AWB Process RL variables from %s", file_path)
    return values


def fill_awb_trade_date(page, path_label: str, value: str) -> bool:
    value = (value or "").strip()
    if not value:
        logging.warning("Skipping empty Trade Date for %s", path_label)
        return False

    selectors = [
        "input#x-auto-786-input",
        "xpath=//*[@id='x-auto-786-input']",
        "xpath=//*[@id='Component_PAGE_FORM_0_atomicCriteria_positionDate_criteria']//input",
    ]

    for selector in selectors:
        field = page.locator(selector).first
        if not field.count():
            continue
        try:
            try:
                field.scroll_into_view_if_needed()
            except PlaywrightError:
                pass
            field.click(force=True, timeout=4000)
            field.press("Control+A")
            field.fill(value)
            page.wait_for_timeout(200)
            logging.info("Filled Trade Date with %s using selector %s", value, selector)
            return True
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    logging.warning("Trade Date field not found for %s", path_label)
    return False


def fill_awb_position_basis(page, value: str) -> bool:
    """
    Position Basis is an ExtJS combobox (dropdown). It MUST be selected by
    opening the trigger arrow and clicking the matching list item — typing
    the text alone leaves the underlying value uncommitted and corrupts the
    MegaCommon screen. Mirrors the OTC TRADED handler in saisie_awb.py.
    """
    value = (value or "").strip()
    if not value:
        logging.warning("Skipping empty Position Basis")
        return False

    input_selectors = [
        "#Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria input",
        "input[name='Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria']",
        "xpath=//*[@id='x-auto-792-input']",
        "xpath=//*[@id='Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria']//input",
    ]

    field = None
    for selector in input_selectors:
        candidate = page.locator(selector).first
        if candidate.count():
            field = candidate
            break

    if field is None:
        logging.warning("Position Basis field not found")
        return False

    try:
        field.scroll_into_view_if_needed()
    except PlaywrightError:
        pass

    trigger_selectors = [
        "xpath=ancestor::div[contains(@class,'x-form-field-wrap')][1]//img[contains(@class,'x-form-trigger-arrow')]",
        "xpath=ancestor::div[contains(@class,'x-form-element')][1]//img[contains(@class,'x-form-trigger-arrow')]",
        "xpath=../img[contains(@class,'x-form-trigger-arrow')]",
    ]
    trigger = None
    for selector in trigger_selectors:
        try:
            candidate = field.locator(selector).first
        except PlaywrightError:
            continue
        if candidate.count():
            trigger = candidate
            break

    if trigger is None or not trigger.count():
        logging.warning("Position Basis dropdown trigger arrow not found")
        return False

    try:
        trigger.scroll_into_view_if_needed()
        trigger.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Position Basis dropdown trigger click failed: %s", exc)
        return False

    option = None
    option_selectors = [
        "div.x-boundlist div.x-boundlist-item",
        "div.x-boundlist-item",
        "li.x-boundlist-item",
        "div.x-combo-list-item",
        ".x-menu-item",
    ]
    text_pattern = re.compile(rf"^{re.escape(value)}$", re.IGNORECASE)
    for selector in option_selectors:
        try:
            candidate = page.locator(selector).filter(has_text=text_pattern).first
        except PlaywrightError:
            continue
        if candidate.count():
            option = candidate
            break

    if option is None or not option.count():
        logging.warning("Position Basis option '%s' not found in dropdown", value)
        return False

    try:
        option.scroll_into_view_if_needed()
        option.click(force=True, timeout=4000)
        page.wait_for_timeout(500)
        page.keyboard.press("Tab")
        page.wait_for_timeout(300)
        logging.info("Filled Position Basis with %s", value)
        return True
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Position Basis option click failed: %s", exc)
        return False


def fill_awb_client_sec_account_consultation(page, value: str) -> bool:
    value = (value or "").strip()
    if not value:
        logging.warning("Skipping empty value for Client Sec Account consultation")
        return False

    selectors = [
        "#Component_PAGE_FORM_0_atomicCriteria_clientSecAccount_criteria input",
        "input[name='Component_PAGE_FORM_0_atomicCriteria_clientSecAccount_criteria']",
        "xpath=//*[@id='x-auto-775-input']",
        "xpath=//*[@id='Component_PAGE_FORM_0_atomicCriteria_clientSecAccount_criteria']//input",
    ]

    for selector in selectors:
        field = page.locator(selector).first
        if not field.count():
            continue
        try:
            try:
                field.scroll_into_view_if_needed()
            except PlaywrightError:
                pass
            field.click(force=True, timeout=4000)
            field.press("Control+A")
            field.fill(value)
            page.wait_for_timeout(200)
            logging.info("Filled Client Sec Account consultation with %s", value)
            return True
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            logging.warning("fill_awb_client_sec_account_consultation failed with selector %s: %s", selector, exc)
            continue

    logging.warning("Client Sec Account consultation field not found")
    return False


def wait_for_megacommon_consultation_form(page) -> bool:
    combined = (
        "#Component_PAGE_FORM_0_atomicCriteria_clientSecAccount_criteria, "
        "#Component_PAGE_FORM_0_atomicCriteria_tradableAsset_criteria, "
        "#Component_PAGE_FORM_0_atomicCriteria_positionDate_criteria, "
        "#Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria"
    )
    try:
        page.wait_for_selector(combined, timeout=15000, state="visible")
        logging.info("MegaCommon consultation form visible")
        return True
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.warning("MegaCommon consultation form did not become visible in time")
        return False


def prepare_megacommon_consultation(page, criteria: Dict[str, str]) -> bool:
    path_label = " > ".join(MEGACOMMON_POSITION_CONSULTATION_PATH)

    alive_page = base.ensure_alive_page(page)
    if alive_page is None:
        logging.warning("No alive MegaCommon page available while preparing consultation")
        return False

    if not base.open_menu_path_exact(alive_page, MEGACOMMON_POSITION_CONSULTATION_PATH):
        return False

    if not wait_for_megacommon_consultation_form(alive_page):
        return False

    ok_local = True
    ok_local &= base.fill_consultation_field(
        alive_page,
        [
            "#Component_PAGE_FORM_0_atomicCriteria_tradableAsset_criteria input",
            "input[name='Component_PAGE_FORM_0_atomicCriteria_tradableAsset_criteria']",
            "xpath=//*[@id='x-auto-780-input']",
            "xpath=//*[@id='Component_PAGE_FORM_0_atomicCriteria_tradableAsset_criteria']//input",
        ],
        criteria.get("tradable_asset", ""),
        "Tradable Asset",
        settle_ms=200,
    )
    ok_local &= fill_awb_trade_date(alive_page, path_label, criteria.get("trade_date", ""))
    ok_local &= fill_awb_position_basis(alive_page, criteria.get("position_basis", "Date métier"))
    # client_sec_account filled last so no subsequent field blur resets it
    ok_local &= fill_awb_client_sec_account_consultation(
        alive_page,
        criteria.get("client_sec_account", ""),
    )

    if ok_local:
        logging.info("Prepared MegaCommon consultation criteria for %s", path_label)
    return ok_local


def execute_megacommon_consultation(page, criteria: Dict[str, str]) -> bool:
    if not prepare_megacommon_consultation(page, criteria):
        return False

    # Settle: let ExtJS commit the criteria changes before pressing Execute.
    # MegaCommon is sensitive to early Execute clicks (screen damage if rushed).
    page.wait_for_timeout(1000)

    execute_button = page.locator(base.EXECUTE_CRITERIA_SELECTOR).first
    if not execute_button.count():
        logging.warning("Execute Criteria button not found on MegaCommon consultation")
        return False

    try:
        execute_button.click(force=True, timeout=8000)
        page.wait_for_timeout(800)
        base.handle_execute_search_popup(page, "MegaCommon", " > ".join(MEGACOMMON_POSITION_CONSULTATION_PATH))
        logging.info("Executed MegaCommon consultation search")
        return True
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.warning("Execute Criteria click failed on MegaCommon consultation")
        return False


def view_first_result_and_screenshot_position(page, suffix: str) -> bool:
    """
    After a search has been executed on the MegaCommon Position Consultation grid:
      1. Finds the first result row (TR id ending in PalmyraGrid_0).
      2. Right-clicks it and chooses "Voir" from the context menu.
      3. Waits for the "Consultation : Position" panel to appear.
      4. Scrolls to the bottom of the page.
      5. Takes a full-page screenshot.
      6. Clicks the return button to go back to the grid.
    """
    # --- find the first result TR row ---
    result_row = None
    for selector in [
        "[id$='PalmyraGrid_0']",
        "tr[id*='PalmyraGrid_0']",
        "div.x-grid3-body tr.x-grid3-row",
        "tr.x-grid3-row",
    ]:
        try:
            page.wait_for_selector(selector, timeout=4000)
            candidate = page.locator(selector).first
            if candidate.count():
                try:
                    if candidate.is_visible():
                        result_row = candidate
                        break
                except PlaywrightError:
                    continue
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    if result_row is None:
        logging.warning(
            "No result row (PalmyraGrid_0) found for position screenshot (%s); skipping", suffix
        )
        return False

    # --- right-click the TR row ---
    try:
        result_row.scroll_into_view_if_needed()
        result_row.click(button="right", force=True, timeout=4000)
        page.wait_for_timeout(600)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Right-click on result row failed (%s): %s", suffix, exc)
        return False

    # --- click "Voir" in the context menu ---
    voir_item = None
    for selector in [
        "xpath=//span[contains(@class,'x-menu-item-text') and normalize-space(text())='Voir']",
        "xpath=//li[contains(@class,'x-menu-item')]//span[normalize-space(text())='Voir']",
        "xpath=//a[contains(@class,'x-menu-item') and contains(normalize-space(string(.)),'Voir')]",
    ]:
        candidate = page.locator(selector).first
        if candidate.count():
            try:
                if candidate.is_visible():
                    voir_item = candidate
                    break
            except PlaywrightError:
                continue

    if voir_item is None:
        logging.warning("'Voir' context menu item not found (%s); dismissing menu", suffix)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False

    try:
        voir_item.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Click 'Voir' failed (%s): %s", suffix, exc)
        return False

    # --- wait for "Consultation : Position" panel header to appear ---
    panel_found = False
    deadline = time.time() + 10.0
    while time.time() < deadline:
        for selector in [
            "xpath=//*[contains(@class,'x-panel-header-text') and contains(normalize-space(text()),'Consultation')]",
            "xpath=//span[contains(@class,'x-panel-header-text') and contains(normalize-space(text()),'Position')]",
            "xpath=//*[contains(@class,'x-panel-header') and contains(normalize-space(string(.)),'Consultation')]",
        ]:
            try:
                if page.locator(selector).first.count():
                    panel_found = True
                    break
            except Exception:
                pass
        if panel_found:
            break
        page.wait_for_timeout(300)

    if not panel_found:
        logging.warning("Consultation : Position panel not found after 'Voir' (%s); taking screenshot anyway", suffix)

    # --- scroll until 'Nature d'actif' field (#Field_ComponentassetNature) is visible ---
    ASSET_NATURE_SELECTOR = "#Field_ComponentassetNature"
    asset_nature_visible = False
    for _ in range(20):
        try:
            el = page.locator(ASSET_NATURE_SELECTOR).first
            if el.count() and el.is_visible():
                el.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
                asset_nature_visible = True
                break
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        try:
            page.evaluate("window.scrollBy(0, 400)")
            page.wait_for_timeout(200)
        except Exception:
            break

    if not asset_nature_visible:
        logging.warning(
            "'Nature d'actif' field (#Field_ComponentassetNature) not visible after scroll (%s); taking screenshot anyway",
            suffix,
        )

    # --- take screenshot ---
    target_dir = SCREENSHOT_DIR / "AWB" / "Process_RL" / "megacommon" / "position"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"position_{suffix}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(target_dir / filename), full_page=True)
        logging.info("Position consultation screenshot saved: %s", target_dir / filename)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Failed to take position screenshot (%s): %s", suffix, exc)

    # --- click return button to go back to the results grid ---
    for selector in [
        "#Component_PAGE_FORM_2_return_null",
        "xpath=//*[@id='Component_PAGE_FORM_2_return_null']",
        "xpath=//*[contains(@id,'_return_null')]",
    ]:
        btn = page.locator(selector).first
        if btn.count():
            try:
                btn.scroll_into_view_if_needed()
                btn.click(force=True, timeout=4000)
                page.wait_for_timeout(400)
                logging.info("Clicked return button after position screenshot (%s)", suffix)
                break
            except (PlaywrightTimeoutError, PlaywrightError):
                continue

    return True


def main() -> None:
    base.SCREENSHOT_DIR = SCREENSHOT_DIR
    base.SCREENSHOT_PROJECT_ROOT = "AWB"
    base.SCREENSHOT_RUN_ROOT = "Process_RL"
    base.AUTH_USERNAME = AUTH_USERNAME
    base.AUTH_PASSWORD = AUTH_PASSWORD
    base.AUTH_DOMAIN = AUTH_DOMAIN
    base.AUTH_TYPE = AUTH_TYPE

    os.environ.setdefault("MENU_CATEGORY_SLUG", "MegaCustody")
    menu_paths = [
        ["Règlement/Livraison", "Instructions Clients", "Saisie Instruction Client"],
        ["Règlement/Livraison", "Instructions Marché", "Appariement"],
        ["Règlement/Livraison", "Instructions Marché", "Dénouement"],
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": 35.6895, "longitude": 139.6917},
            locale="fr-FR",
            ignore_https_errors=True,
            no_viewport=True,
        )
        common_page = context.new_page()
        try:
            criteria = load_awb_process_rl_variables(AWB_PROCESS_RL_VARIABLES_FILE)

            if not _awb_login(common_page, MEGACOMMON_ENTRY):
                logging.error("MegaCommon login failed, stopping execution.")
                return
            common_page = base.get_alive_page(common_page)
            if common_page.is_closed():
                logging.error("No alive MegaCommon page available after login.")
                return
            if not execute_megacommon_consultation(common_page, criteria):
                logging.error("MegaCommon pre-consultation execute search failed; stopping before custody process.")
                return
            view_first_result_and_screenshot_position(common_page, "pre_denouement")

            custody_page = context.new_page()
            logging.info("Starting custody login for %s", LOGIN_ENTRY)
            if not _awb_login(custody_page, LOGIN_ENTRY):
                logging.error("Custody login failed, stopping execution.")
                return
            custody_page = base.get_alive_page(custody_page)
            if custody_page.is_closed():
                logging.error("No alive custody page available after login.")
                return
            try:
                logging.info("Custody page ready, URL=%s", custody_page.url)
            except Exception:
                logging.info("Custody page ready, URL unavailable")

            if menu_paths:
                logging.info("Starting AWB custody traversal with %d paths", len(menu_paths))
                try:
                    awb.traverse_menu_paths(custody_page, menu_paths)
                    logging.info("Custody traversal completed; returning to MegaCommon for final execute")
                except PlaywrightError as exc:
                    if is_target_closed_error(exc):
                        logging.warning("Custody traversal aborted because page closed: %s", exc)
                    else:
                        logging.error("Custody traversal raised PlaywrightError: %s", exc)
                        logging.error(traceback.format_exc())
                        raise
                except Exception as exc:
                    logging.error("Custody traversal raised unexpected exception: %s", exc)
                    logging.error(traceback.format_exc())
                    raise
            else:
                logging.error("No menu paths defined; strict ordered execution aborted.")
                return

            common_page = base.find_megacommon_page(context, common_page)
            if common_page is None or common_page.is_closed():
                logging.info("MegaCommon page closed during custody traversal; opening a fresh tab")
                try:
                    common_page = context.new_page()
                except Exception as exc:
                    logging.error("Cannot create new MegaCommon page: %s", exc)
                    common_page = None

            if common_page and not common_page.is_closed():
                try:
                    common_page.bring_to_front()
                except Exception:
                    pass

                # Re-login MegaCommon if its app shell is no longer visible
                # (session expired during the long custody traversal, OR we
                # just opened a fresh blank tab above).
                shell_ok = False
                try:
                    shell_ok = base.app_shell_visible(common_page)
                except (PlaywrightTimeoutError, PlaywrightError):
                    shell_ok = False

                if not shell_ok:
                    logging.info("MegaCommon app shell not visible at final step; relogin")
                    if not _awb_login(common_page, MEGACOMMON_ENTRY):
                        logging.error("Final MegaCommon relogin failed; cannot execute final search")
                        return
                    common_page = base.ensure_alive_page(common_page)
                    if common_page is None:
                        logging.error("No alive MegaCommon page after final relogin")
                        return

                # Close any leftover work window from the pre-dénouement view
                # so we restart from a clean state — exactly like the pre-flow
                # which begins right after a fresh login.
                try:
                    awb.close_work_window(common_page, " > ".join(MEGACOMMON_POSITION_CONSULTATION_PATH))
                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    logging.info("MegaCommon: no work window to close pre-final-execute (%s)", exc)

                # Refresh the MegaCommon page so the consultation reflects the
                # latest state after the custody dénouement.
                try:
                    logging.info("Refreshing MegaCommon page before post-dénouement consultation")
                    common_page.reload(wait_until="domcontentloaded", timeout=30000)
                    common_page.wait_for_timeout(1500)
                    # If the reload landed back on the login page, re-authenticate.
                    try:
                        login_visible = common_page.locator(
                            "#username, input[name='username'], input[name='j_username']"
                        ).first.is_visible()
                    except (PlaywrightTimeoutError, PlaywrightError):
                        login_visible = False
                    if login_visible:
                        logging.info("Reload landed on login form — re-authenticating MegaCommon")
                        if not _awb_login(common_page, MEGACOMMON_ENTRY):
                            logging.error("Re-authentication after reload failed; aborting post-dénouement flow")
                            return
                        common_page = base.ensure_alive_page(common_page)
                        if common_page is None:
                            logging.error("No alive MegaCommon page after reload re-authentication")
                            return
                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    logging.warning("MegaCommon page reload failed (%s); continuing", exc)

                # Run the SAME steps as before custody access (mirror pre-flow):
                #   1. execute_megacommon_consultation (open menu + fill + execute)
                #   2. view_first_result_and_screenshot_position
                try:
                    if not execute_megacommon_consultation(common_page, criteria):
                        logging.error("MegaCommon post-consultation execute search failed.")
                    else:
                        logging.info("Final MegaCommon execute completed")
                        view_first_result_and_screenshot_position(common_page, "post_denouement")
                except PlaywrightError as exc:
                    if is_target_closed_error(exc):
                        logging.error("MegaCommon page closed during post-dénouement consultation: %s", exc)
                    else:
                        logging.error("MegaCommon post-dénouement raised: %s", exc)
            else:
                logging.warning("MegaCommon tab not available for final consultation execution")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
