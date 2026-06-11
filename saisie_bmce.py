import logging
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import playwright
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

# ---- Configuration ----

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
LOGIN_ENTRY = os.getenv("MODULE_URL", "http://10.1.146.163:9082/MegaCustody/login.jsp")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/BMCE/Custody/saisie.txt"))
SAISIE_VARIABLES_FILE = Path(
    os.getenv("SAISIE_VARIABLES_FILE", "variable_saisies/Instruction_Client_BMCE.txt")
)
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "migration")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Vermeg+123")
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "BMCE BANK")
AUTH_TYPE = os.getenv("AUTH_TYPE", "standard").strip().lower()

LOGIN_NAVIGATION_MAX_ATTEMPTS = int(os.getenv("LOGIN_NAVIGATION_MAX_ATTEMPTS", "3"))
LOGIN_NAVIGATION_TIMEOUT_MS = int(os.getenv("LOGIN_NAVIGATION_TIMEOUT_MS", "30000"))
LOGIN_NAVIGATION_RETRY_DELAY_MS = int(os.getenv("LOGIN_NAVIGATION_RETRY_DELAY_MS", "2500"))

# Pre-normalized tuple of the target menu path (accents stripped, / → space, lowercase).
# Must match what _normalize_text() produces from the raw path segments.
SAISIE_PATH_NORMALIZED = (
    "reglement livraison",
    "instructions clients marche local",
    "saisie instruction client",
)

SAVE_BUTTON_SELECTOR = "#Component_PAGE_FORM_0_save_null"
OK_BUTTON_PATTERN = re.compile(r"^ok$", re.IGNORECASE)
SUCCESS_MESSAGE_PATTERN = re.compile(r"saved|sauvegard", re.IGNORECASE)
ERROR_MESSAGE_PATTERN = re.compile(r"\b(log|internal_error|error|err)\b", re.IGNORECASE)

# Field specifications — order matters (top-to-bottom fill order).
# Each selector string is comma-separated; _find_field tries them in order.
# Component-ID selectors (#Component_PAGE_FORM_0_X input) are stable across sessions.
# x-auto-NNNN IDs are dynamic and listed last as fallbacks only.
BMCE_FIELD_SPECS: List[Dict] = [
    {
        "key": "otc",
        "label": "OTC",
        "selector": (
            "input[id^='x-auto-'][id$='-input'][name='Component_PAGE_FORM_0_oTCTraded'],"
            "#Component_PAGE_FORM_0_oTCTraded input[id^='x-auto-'][id$='-input'],"
            "#Component_PAGE_FORM_0_oTCTraded input,"
            "input[name='Component_PAGE_FORM_0_oTCTraded']"
        ),
        "is_combo": True,
    },
    {
        "key": "reference_client",
        "label": "Référence Client",
        "selector": (
            "input[name='Component_PAGE_FORM_0_clientReference'],"
            "#Component_PAGE_FORM_0_clientReference input"
        ),
        "is_combo": False,
    },
    {
        "key": "type_transaction",
        "label": "Type de transaction",
        "selector": (
            "#Component_PAGE_FORM_0_transactionType input[id^='x-auto-'][id$='-input'],"
            "#Component_PAGE_FORM_0_transactionType input,"
            "input[name='Component_PAGE_FORM_0_transactionType'],"
            "input[name='transactionType']"
        ),
        "is_combo": True,
    },
    {
        "key": "actif",
        "label": "Actif",
        "selector": (
            "input[name='Component_PAGE_FORM_0_tradableAsset'],"
            "#Component_PAGE_FORM_0_tradableAsset input[id^='x-auto-'][id$='-input'],"
            "#Component_PAGE_FORM_0_tradableAsset input"
        ),
        "is_combo": False,
    },
    {
        "key": "quantite_entrante",
        "label": "Quantité entrante",
        "selector": (
            "input[name='Component_PAGE_FORM_0_incomingQuantity'],"
            "#Component_PAGE_FORM_0_incomingQuantity input"
        ),
        "is_combo": False,
    },
    {
        "key": "ordered_qty",
        "label": "Ordered Qty",
        "selector": (
            "input[name='Component_PAGE_FORM_0_orderedQty'],"
            "#Component_PAGE_FORM_0_orderedQty input"
        ),
        "is_combo": False,
    },
    {
        "key": "compte_titres_client",
        "label": "Compte titres client",
        "selector": (
            "input[name='Component_PAGE_FORM_0_clientSecAccount'],"
            "#Component_PAGE_FORM_0_clientSecAccount input"
        ),
        "is_combo": False,
    },
    {
        "key": "contrepartie",
        "label": "Contrepartie",
        "selector": (
            "input[name='Component_PAGE_FORM_0_counterpart'],"
            "#Component_PAGE_FORM_0_counterpart input"
        ),
        "is_combo": False,
    },
    {
        "key": "beneficiaire",
        "label": "Bénéficiaire",
        "selector": (
            "input[name='Component_PAGE_FORM_0_beneficiary'],"
            "#Component_PAGE_FORM_0_beneficiary input"
        ),
        "is_combo": False,
    },
    {
        "key": "date_negociation",
        "label": "Date Négociation",
        "selector": (
            "input[name='Component_PAGE_FORM_0_tradeDate'],"
            "#Component_PAGE_FORM_0_tradeDate input[id^='x-auto-'][id$='-input'],"
            "#Component_PAGE_FORM_0_tradeDate input,"
            "input[name='Component_PAGE_FORM_0_negociationDate'],"
            "#Component_PAGE_FORM_0_negociationDate input"
        ),
        "is_combo": False,
    },
    {
        "key": "prix",
        "label": "Prix",
        "selector": (
            "input[name='Component_PAGE_FORM_0_price'],"
            "#Component_PAGE_FORM_0_price input[id^='x-auto-'][id$='-input'],"
            "#Component_PAGE_FORM_0_price input"
        ),
        "is_combo": False,
    },
    {
        "key": "taux_negocie",
        "label": "Taux Négocié",
        "selector": (
            "input[name='Component_PAGE_FORM_0_negociatedRate'],"
            "#Component_PAGE_FORM_0_negociatedRate input"
        ),
        "is_combo": False,
    },
]

# Maps normalized label (from variables file) -> internal key
_LABEL_KEY_MAP: Dict[str, str] = {
    "otc": "otc",
    "reference client": "reference_client",
    "type de transaction": "type_transaction",
    "actif": "actif",
    "quantite entrante": "quantite_entrante",
    "ordered qty": "ordered_qty",
    "compte titres client": "compte_titres_client",
    "contrepartie": "contrepartie",
    "beneficiaire": "beneficiaire",
    "date negociation": "date_negociation",
    "prix": "prix",
    "taux negocie": "taux_negocie",
}

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


# ---- Utilities ----

def ensure_playwright_node_path() -> None:
    if os.name != "nt" or os.getenv("PLAYWRIGHT_NODEJS_PATH"):
        return
    driver_node = Path(playwright.__file__).resolve().parent / "driver" / "node.exe"
    if driver_node.exists():
        os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(driver_node)
        logging.info("Configured PLAYWRIGHT_NODEJS_PATH.")


def slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    return cleaned.strip("_").lower() or "node"


def _normalize_text(value: str) -> str:
    nfkd = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    stripped = stripped.replace("/", " ")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _normalize_label(label: str) -> str:
    return _normalize_text(label.replace("*", "").strip())


def _first_words(value: str, count: int = 3) -> str:
    return " ".join(_normalize_text(value).split()[:count])


# ---- Variables file ----

def load_bmce_saisie_variables() -> Dict[str, str]:
    values: Dict[str, str] = {spec["key"]: "" for spec in BMCE_FIELD_SPECS}

    if not SAISIE_VARIABLES_FILE.exists():
        logging.warning("BMCE variables file not found: %s", SAISIE_VARIABLES_FILE)
        return values

    with SAISIE_VARIABLES_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
                continue
            label_raw, raw_value = cleaned.split("=", 1)
            key = _LABEL_KEY_MAP.get(_normalize_label(label_raw))
            if key:
                values[key] = raw_value.strip()

    filled = {k: v for k, v in values.items() if v}
    logging.info("BMCE variables loaded: %s", filled)
    return values


# ---- Menu paths ----

def load_menu_paths() -> List[List[str]]:
    if not MENU_PATH_FILE.exists():
        logging.warning("Menu path file not found: %s", MENU_PATH_FILE)
        return []
    paths: List[List[str]] = []
    with MENU_PATH_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            segments = [s.strip() for s in cleaned.split(">") if s.strip()]
            if segments:
                paths.append(segments)
    logging.info("Loaded %d menu paths from %s", len(paths), MENU_PATH_FILE)
    return paths


# ---- Dialog / error handling ----

def failure_indicators_present(page) -> bool:
    if page.locator("div.ext-mb-icon.ext-mb-warning").count():
        return True
    if page.locator("span.ext-mb-text").filter(has_text=ERROR_MESSAGE_PATTERN).count():
        return True
    if page.locator("span.x-window-header-text").filter(has_text=re.compile(r"error", re.IGNORECASE)).count():
        return True
    return False


def dismiss_error_dialog(page, path_label: str) -> None:
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        ok_btn = page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first
        if ok_btn.count():
            ok_btn.click(force=True, timeout=3000)
            page.wait_for_timeout(400)
    except Exception:
        pass


def capture_failure(page, path_label: str, *, always: bool = False) -> None:
    if not always and not failure_indicators_present(page):
        return
    target_dir = SCREENSHOT_DIR / "BMCE" / "saisie_instruction_unitaire"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(path_label)}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(target_dir / filename), full_page=True)
        logging.warning("Failure screenshot saved: %s", target_dir / filename)
    except Exception as exc:
        logging.warning("Could not save failure screenshot: %s", exc)
    dismiss_error_dialog(page, path_label)


def handle_error_dialog(page, path_label: str) -> bool:
    page.wait_for_timeout(400)
    if not failure_indicators_present(page):
        return False
    logging.warning("Error dialog detected for %s", path_label)
    capture_failure(page, path_label)
    return True


def dismiss_ok_popup_if_present(page, path_label: str) -> bool:
    try:
        dismissed = page.evaluate("""
            () => {
                const wins = document.querySelectorAll('div.x-window, div.x-window-plain, div.x-window-dlg');
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
        """)
        if dismissed:
            page.wait_for_timeout(300)
            logging.info("OK popup dismissed for %s", path_label)
            return True
    except Exception:
        pass
    return False


def close_work_window(page, path_label: str) -> None:
    if page.is_closed():
        return
    for selector in ["a.x-tab-strip-close", "div.x-tool-close", "button[aria-label='Close']"]:
        try:
            btn = page.locator(selector).first
            if btn.count():
                btn.click(force=True, timeout=3000)
                page.wait_for_timeout(400)
                return
        except Exception:
            pass


# ---- Form fill ----

def fill_bmce_saisie_form(page, path_label: str) -> bool:
    values = load_bmce_saisie_variables()
    fillable = {k: v for k, v in values.items() if v.strip()}
    logging.info("Filling BMCE saisie form for '%s', fields: %s", path_label, list(fillable.keys()))

    # ---- inner helpers (AWB methodology) ----

    def _split(selector: str):
        return [s.strip() for s in selector.split(",") if s.strip()]

    def _find_field(label: str, selector: str):
        norm = re.sub(r"\s+", " ", label.strip().lower())
        selectors = _split(selector)
        # Label-specific prepend of the most stable component-ID selectors
        if "otc" in norm:
            selectors = [
                "input[id^='x-auto-'][id$='-input'][name='Component_PAGE_FORM_0_oTCTraded']",
                "#Component_PAGE_FORM_0_oTCTraded input[id^='x-auto-'][id$='-input']",
                "#Component_PAGE_FORM_0_oTCTraded input",
                "input[name='Component_PAGE_FORM_0_oTCTraded']",
            ] + selectors
        if "type" in norm and "transaction" in norm:
            selectors = [
                "#Component_PAGE_FORM_0_transactionType input[id^='x-auto-'][id$='-input']",
                "#Component_PAGE_FORM_0_transactionType input",
                "input[name='Component_PAGE_FORM_0_transactionType']",
                "input[name='transactionType']",
            ] + selectors
        if "date" in norm and ("negociation" in norm or "n" in norm):
            selectors = [
                "input[name='Component_PAGE_FORM_0_tradeDate']",
                "#Component_PAGE_FORM_0_tradeDate input[id^='x-auto-'][id$='-input']",
                "#Component_PAGE_FORM_0_tradeDate input",
                "input[name='Component_PAGE_FORM_0_negociationDate']",
                "#Component_PAGE_FORM_0_negociationDate input",
            ] + selectors
        # Retry loop — up to 12 × 250 ms = 3 s
        for _ in range(12):
            for sel in selectors:
                try:
                    f = page.locator(sel).first
                    if f.count():
                        return f
                except Exception:
                    continue
            page.wait_for_timeout(250)
        return None

    def _safe_tab_to_target(target_selector: str, current_field=None, max_tabs: int = 12) -> bool:
        if not target_selector:
            return False
        selectors = _split(target_selector)
        target = None
        for sel in selectors:
            try:
                c = page.locator(sel).first
                if c.count():
                    target = c
                    break
            except Exception:
                continue
        # Try direct click first
        if target and target.count():
            try:
                target.scroll_into_view_if_needed()
                target.click(force=True, timeout=3000)
                page.wait_for_timeout(180)
                if target.evaluate("el => el === document.activeElement"):
                    return True
            except Exception:
                pass
        # Tab from current field
        if current_field and current_field.count():
            try:
                current_field.focus()
            except Exception:
                pass
        for _ in range(max_tabs):
            page.keyboard.press("Tab")
            page.wait_for_timeout(180)
            if target and target.count():
                try:
                    if target.evaluate("el => el === document.activeElement"):
                        return True
                except Exception:
                    pass
        # Force-click as last resort
        if target and target.count():
            try:
                target.click(force=True, timeout=3000)
                return True
            except Exception:
                pass
        return False

    def _set_value(field, value: str) -> bool:
        try:
            field.evaluate(
                "(el, v) => { el.focus(); el.value = v;"
                " el.dispatchEvent(new Event('input',{bubbles:true}));"
                " el.dispatchEvent(new Event('change',{bubbles:true})); }",
                value,
            )
            return True
        except Exception:
            pass
        try:
            field.fill(value)
            return True
        except Exception:
            pass
        for char in value:
            try:
                field.type(char, delay=60)
            except Exception:
                pass
        return False

    def _commit(field) -> None:
        try:
            field.evaluate(
                "el => { el.dispatchEvent(new Event('input',{bubbles:true}));"
                " el.dispatchEvent(new Event('change',{bubbles:true})); el.blur(); }"
            )
        except Exception:
            try:
                field.evaluate("el => { el.blur(); el.dispatchEvent(new Event('blur',{bubbles:true})); }")
            except Exception:
                pass

    def _get_value(field) -> str:
        try:
            return field.input_value().strip()
        except Exception:
            try:
                return field.evaluate("el => el.value").strip()
            except Exception:
                return ""

    def _select_combo_dropdown(field, value: str, label: str) -> bool:
        trigger_selectors = [
            "xpath=ancestor::div[contains(@class,'x-form-field-wrap')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
            "xpath=ancestor::div[contains(@class,'x-form-element')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
            "xpath=../img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
        ]
        trigger = None
        for sel in trigger_selectors:
            try:
                t = field.locator(sel).first
                if t.count():
                    trigger = t
                    break
            except Exception:
                continue
        if not trigger or not trigger.count():
            return False
        try:
            trigger.scroll_into_view_if_needed()
            trigger.click(force=True, timeout=4000)
            page.wait_for_timeout(600)
        except Exception:
            return False
        option_selectors = [
            "div.x-boundlist div.x-boundlist-item",
            "div.x-boundlist-item",
            "li.x-boundlist-item",
            "div.x-combo-list-item",
            ".x-menu-item",
        ]
        text_exact = re.compile(rf"^{re.escape(value.strip())}$", re.IGNORECASE)
        text_partial = re.compile(re.escape(value.strip()), re.IGNORECASE)
        for sel in option_selectors:
            try:
                opt = page.locator(sel).filter(has_text=text_exact).first
                if not opt.count():
                    opt = page.locator(sel).filter(has_text=text_partial).first
                if opt.count():
                    opt.scroll_into_view_if_needed()
                    opt.click(force=True, timeout=4000)
                    page.wait_for_timeout(500)
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(300)
                    return True
            except Exception:
                continue
        return False

    def _fill_one(field, value: str, label: str, next_selector: Optional[str], is_combo: bool) -> None:
        field.scroll_into_view_if_needed()
        field.click(force=True, timeout=4000)
        page.wait_for_timeout(200)

        # Combo: try dropdown first
        if is_combo and _select_combo_dropdown(field, value, label):
            if _get_value(field).lower() == value.strip().lower():
                if next_selector:
                    _safe_tab_to_target(next_selector, current_field=field)
                return
            logging.info("Combo '%s': dropdown selected but value differs, falling back to typing", label)

        # Text / combo fallback: DOM inject then commit
        _set_value(field, value)
        field.evaluate(
            "el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }"
        )
        page.wait_for_timeout(400)
        _commit(field)
        page.wait_for_timeout(1000)

        cur = _get_value(field)
        logging.info("Field '%s' value after commit: '%s'", label, cur)
        if cur != value.strip():
            logging.warning("Field '%s' mismatch (expected='%s'), retrying", label, value.strip())
            field.click(force=True, timeout=4000)
            field.fill(value)
            field.evaluate(
                "el => { el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }"
            )
            page.wait_for_timeout(400)
            _commit(field)
            page.wait_for_timeout(1000)

        page.keyboard.press("Tab")
        page.wait_for_timeout(300)

        if next_selector:
            clicked = False
            for sel in _split(next_selector):
                try:
                    cand = page.locator(sel).first
                    if cand.count():
                        cand.scroll_into_view_if_needed()
                        cand.click(force=True, timeout=4000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                _safe_tab_to_target(next_selector, current_field=field)

    # ---- main loop ----
    ordered = list(BMCE_FIELD_SPECS)
    fillable_keys = set(fillable)

    page.wait_for_timeout(800)

    for idx, spec in enumerate(ordered):
        key = spec["key"]
        label = spec["label"]
        selector = spec["selector"]
        is_combo = spec.get("is_combo", False)
        value = fillable.get(key, "")
        if not value:
            logging.info("Skipping '%s' (no value configured)", label)
            continue

        next_selector = None
        for later in ordered[idx + 1:]:
            if later["key"] in fillable_keys:
                next_selector = later["selector"]
                break

        field = _find_field(label, selector)
        if not field:
            logging.warning("Field '%s' not found for %s", label, path_label)
            capture_failure(page, f"{path_label} > missing:{label}", always=True)
            return False

        try:
            _fill_one(field, value, label, next_selector, is_combo)
            logging.info("Filled '%s' with '%s'", label, value)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            logging.warning("Playwright error filling '%s' for %s: %s", label, path_label, exc)
            capture_failure(page, f"{path_label} > error:{label}", always=True)
            return False

    # After filling Taux Négocié, re-tab to Compte titres client to trigger validation
    compte_titres_spec = next((s for s in BMCE_FIELD_SPECS if s["key"] == "compte_titres_client"), None)
    if compte_titres_spec:
        compte_field = _find_field(compte_titres_spec["label"], compte_titres_spec["selector"])
        if compte_field:
            try:
                compte_field.scroll_into_view_if_needed()
                compte_field.click(force=True, timeout=3000)
                page.wait_for_timeout(200)
                page.keyboard.press("Tab")
                page.wait_for_timeout(300)
                logging.info("Re-tabbed through Compte titres client after Taux Négocié")
            except Exception as exc:
                logging.warning("Re-tab on Compte titres client failed: %s", exc)

    # Scroll to top — save button is at the top of the form
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)

    save_btn = page.locator(SAVE_BUTTON_SELECTOR).first
    if not save_btn.count():
        # Try scrolling up in small steps
        for _ in range(5):
            page.evaluate("window.scrollBy(0, -200)")
            page.wait_for_timeout(150)
            save_btn = page.locator(SAVE_BUTTON_SELECTOR).first
            if save_btn.count():
                break

    if not save_btn.count():
        logging.warning("Save button '%s' not found for %s", SAVE_BUTTON_SELECTOR, path_label)
        capture_failure(page, path_label, always=True)
        return False

    try:
        save_btn.scroll_into_view_if_needed()
        save_btn.click(force=True, timeout=4000)
        logging.info("Save button clicked for %s", path_label)
    except PlaywrightTimeoutError:
        logging.warning("Save button click timed out for %s", path_label)
        capture_failure(page, path_label, always=True)
        return False

    # Wait for popup (up to 15 s) then screenshot
    popup_selectors = [
        "div.x-window-plain.x-window-dlg.x-window.x-component",
        "div.x-window.x-window-dlg",
        "div.x-window:not(.x-hidden)",
        "span.ext-mb-text",
    ]
    popup_found = False
    deadline = time.time() + 15
    while time.time() < deadline:
        for sel in popup_selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    popup_found = True
                    break
            except Exception:
                pass
        if popup_found:
            break
        page.wait_for_timeout(200)

    outcome = "no_popup"
    try:
        if page.locator("span.ext-mb-text").filter(has_text=SUCCESS_MESSAGE_PATTERN).count():
            outcome = "success"
        elif failure_indicators_present(page):
            outcome = "failure"
        elif popup_found:
            outcome = "popup"
    except Exception:
        outcome = "popup" if popup_found else "no_popup"

    target_dir = SCREENSHOT_DIR / "BMCE" / "saisie_instruction_unitaire"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(path_label)}_{outcome}_{int(time.time())}.png"
    screenshot_path = target_dir / filename
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        logging.info("Post-save screenshot [%s] saved at %s", outcome, screenshot_path)
    except Exception as exc:
        logging.warning("Could not save post-save screenshot: %s", exc)

    handle_error_dialog(page, path_label)
    dismiss_ok_popup_if_present(page, path_label)
    page.wait_for_timeout(500)
    return True


# ---- Tree traversal ----

def _normalize_menu_segments(path: List[str]) -> Tuple[str, ...]:
    return tuple(_normalize_text(seg) for seg in path)


def find_tree_node(page, label: str, level: int):
    if page.is_closed():
        return page.locator("xpath=/*[false()]")

    exact_pattern = re.compile(rf"^\s*{re.escape(label)}\s*$", re.IGNORECASE)
    level_selector = f'div[role="treeitem"][aria-level="{level}"]'

    try:
        exact_node = page.locator(level_selector).filter(has_text=exact_pattern).first
        if exact_node.count():
            return exact_node
    except PlaywrightError:
        pass

    normalized_label = _normalize_text(label)
    target_prefix = _first_words(label, 3)
    selectors = [level_selector, 'div[role="treeitem"]']

    deadline = time.time() + 8
    while time.time() < deadline:
        if page.is_closed():
            return page.locator("xpath=/*[false()]")

        for selector in selectors:
            try:
                treeitems = page.locator(selector)
                count = treeitems.count()
            except PlaywrightError:
                return page.locator("xpath=/*[false()]")

            for idx in range(count):
                candidate = treeitems.nth(idx)
                try:
                    candidate_text = _normalize_text(candidate.inner_text() or "")
                    if not candidate_text:
                        continue
                    if candidate_text == normalized_label or normalized_label in candidate_text:
                        return candidate
                    if level == 2 and target_prefix and _first_words(candidate_text, 3) == target_prefix:
                        return candidate
                except Exception:
                    continue

        # Fallback: search node text spans
        try:
            node_texts = page.locator(".x-tree3-node-text")
            for idx in range(node_texts.count()):
                candidate = node_texts.nth(idx)
                try:
                    candidate_text = _normalize_text(candidate.inner_text() or "")
                    if not candidate_text:
                        continue
                    if candidate_text == normalized_label or normalized_label in candidate_text:
                        ancestor = candidate.locator(
                            "xpath=ancestor::div[contains(@class,'x-tree3-node') or contains(@class,'x-tree-node')]"
                        ).first
                        return ancestor if ancestor.count() else candidate
                    if level == 2 and target_prefix and _first_words(candidate_text, 3) == target_prefix:
                        ancestor = candidate.locator(
                            "xpath=ancestor::div[contains(@class,'x-tree3-node') or contains(@class,'x-tree-node')]"
                        ).first
                        return ancestor if ancestor.count() else candidate
                except Exception:
                    continue
        except PlaywrightError:
            return page.locator("xpath=/*[false()]")

        page.wait_for_timeout(300)

    return page.locator('div[role="treeitem"]').filter(has_text=label).first


def _build_parent_prefixes(paths: List[List[str]]) -> set:
    prefixes: set = set()
    for path in paths:
        for depth in range(1, len(path)):
            prefixes.add(tuple(path[:depth]))
    return prefixes


def traverse_menu_paths(page, menu_paths: List[List[str]]) -> None:
    if not menu_paths:
        logging.warning("No menu paths to traverse")
        return

    parent_prefixes = _build_parent_prefixes(menu_paths)
    expanded_nodes: set = set()

    for path in menu_paths:
        if page.is_closed():
            logging.warning("Page closed; stopping traversal")
            return
        if len(path) < 2:
            logging.warning("Skipping short path: %s", path)
            continue

        top_level = path[0]
        path_label = " > ".join(path)
        dismiss_ok_popup_if_present(page, path_label)

        button = page.get_by_role("button", name=top_level)
        if not button.count():
            logging.warning("Top-level tab '%s' not found for path: %s", top_level, path_label)
            continue

        try:
            button.click()
        except Exception as exc:
            logging.warning("Could not click tab '%s' for %s: %s", top_level, path_label, exc)
            continue

        logging.info("Traversing: %s", path_label)
        page.wait_for_timeout(300)

        try:
            page.wait_for_selector("div[role='treeitem']", timeout=12000)
        except PlaywrightTimeoutError:
            logging.warning("Tree items did not load for tab '%s'", top_level)

        normalized_path = _normalize_menu_segments(path)

        for child_index, segment in enumerate(path[1:], start=1):
            level = child_index + 1
            prefix = tuple(path[: child_index + 1])
            node_is_leaf = prefix not in parent_prefixes

            node = find_tree_node(page, segment, level)
            found = node.count() > 0
            try:
                found = found and node.is_visible()
            except Exception:
                pass

            if not found:
                logging.warning("Tree node '%s' at level %d not found for: %s", segment, level, path_label)
                break

            try:
                node.scroll_into_view_if_needed()
            except Exception:
                pass

            already_expanded = prefix in expanded_nodes
            try:
                if node_is_leaf:
                    node.click(force=True, timeout=4000)
                elif already_expanded:
                    node.click(force=True, timeout=4000)
                else:
                    node.dblclick(force=True, timeout=5000)
                    expanded_nodes.add(prefix)
            except PlaywrightTimeoutError:
                logging.warning("Failed to interact with '%s' at level %d for: %s", segment, level, path_label)
                break

            handle_error_dialog(page, path_label)
            page.wait_for_timeout(100)

            if node_is_leaf:
                if normalized_path == SAISIE_PATH_NORMALIZED:
                    fill_bmce_saisie_form(page, path_label)
                else:
                    # Generic leaf: wait a moment then close
                    page.wait_for_timeout(800)
                close_work_window(page, path_label)
                break


# ---- Login ----

def _find_first_visible(page, selectors: List[str]):
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count():
            try:
                if loc.is_visible():
                    return loc
            except Exception:
                return loc
    return None


def _submit_credentials(page, username: str, password: str, domain: str) -> bool:
    username_input = _find_first_visible(
        page, ["#username", "input[name='username']", "input[name='j_username']"]
    )
    password_input = _find_first_visible(
        page, ["#password", "input[name='password']", "input[name='j_password']"]
    )

    if username_input is None or password_input is None:
        logging.error("Login form inputs not found")
        return False

    username_input.fill(username)
    password_input.fill(password)

    domain_field = _find_first_visible(
        page,
        ["input[name='j_asp']", "#domain", "select[name='domain']", "input[name='domain']", "input[id*='domain']"],
    )
    if domain_field is not None and domain:
        try:
            tag_name = (domain_field.evaluate("el => el.tagName") or "").lower()
        except Exception:
            tag_name = ""

        if tag_name == "select":
            try:
                domain_field.select_option(label=domain)
            except Exception:
                try:
                    opts = domain_field.locator("option")
                    domain_norm = domain.strip().lower()
                    for idx in range(opts.count()):
                        opt = opts.nth(idx)
                        opt_label = (opt.inner_text() or "").strip().lower()
                        opt_value = (opt.get_attribute("value") or "").strip().lower()
                        if domain_norm in opt_label or domain_norm in opt_value:
                            val = opt.get_attribute("value") or ""
                            if val:
                                domain_field.select_option(value=val)
                            break
                except Exception:
                    logging.warning("Could not select domain '%s' in select", domain)
        else:
            try:
                domain_field.click(force=True, timeout=3000)
                domain_field.fill(domain)
                page.wait_for_timeout(200)
                if domain_field.get_attribute("name") == "j_asp":
                    page.keyboard.press("Tab")
                else:
                    suggestion = page.locator(
                        "//div[contains(@class,'x-boundlist-item') or contains(@class,'x-combo-list-item')]"
                    ).filter(has_text=re.compile(re.escape(domain), re.IGNORECASE)).first
                    if suggestion.count():
                        suggestion.click(force=True, timeout=2000)
                    else:
                        page.keyboard.press("Tab")
                logging.info("Domain '%s' entered", domain)
            except Exception as exc:
                logging.warning("Domain field interaction failed: %s", exc)

    submit = page.locator(
        "#kc-login, button[name='login'], input[name='login'], button[type=submit], input[type=submit]"
    )
    if submit.count():
        try:
            submit.first.wait_for(state="visible", timeout=10000)
            submit.first.click()
            return True
        except Exception as exc:
            logging.error("Submit click failed: %s", exc)
            return False

    submit_by_role = page.get_by_role("button", name="Submit")
    if submit_by_role.count():
        try:
            submit_by_role.wait_for(state="visible", timeout=10000)
            submit_by_role.click()
            return True
        except Exception as exc:
            logging.error("Submit-by-role click failed: %s", exc)
            return False

    logging.error("No submit button found on login page")
    return False


def login(page) -> bool:
    logging.info("Navigating to %s", LOGIN_ENTRY)

    for attempt in range(1, LOGIN_NAVIGATION_MAX_ATTEMPTS + 1):
        try:
            page.goto(
                LOGIN_ENTRY,
                wait_until="domcontentloaded",
                timeout=LOGIN_NAVIGATION_TIMEOUT_MS,
            )
            break
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            if attempt >= LOGIN_NAVIGATION_MAX_ATTEMPTS:
                logging.error("Failed to open login page: %s", exc)
                return False
            logging.warning("Navigation attempt %d failed: %s. Retrying...", attempt, exc)
            page.wait_for_timeout(LOGIN_NAVIGATION_RETRY_DELAY_MS)

    if AUTH_TYPE == "keycloak":
        kc_link = page.locator("a#social-internal-keycloak-oidc-link").first
        if kc_link.count():
            try:
                kc_link.click(timeout=10000)
            except Exception:
                pass

    try:
        page.wait_for_selector(
            "#username, input[name='username'], input[name='j_username']", timeout=15000
        )
    except PlaywrightTimeoutError:
        logging.error("Login form not displayed in time")
        return False

    if not _submit_credentials(page, AUTH_USERNAME, AUTH_PASSWORD, AUTH_DOMAIN):
        return False

    app_ready = "div[role='treeitem'], button:has-text('Règlement'), a.x-tab-strip-text"
    try:
        page.wait_for_selector(app_ready, timeout=45000)
    except PlaywrightTimeoutError:
        if page.locator("#username, input[name='username']").count():
            logging.error("Login form still visible after submit — credentials may be wrong")
            return False
    except PlaywrightError as exc:
        logging.error("Error waiting for app ready: %s", exc)
        return False

    logging.info("Login successful (user=%s, domain=%s)", AUTH_USERNAME, AUTH_DOMAIN)
    return True


# ---- Entry point ----

def main() -> None:
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    ensure_playwright_node_path()
    menu_paths = load_menu_paths()

    def _safe_close(name: str, action) -> None:
        try:
            action()
        except Exception as exc:
            logging.debug("Ignoring %s close error: %s", name, exc)

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
        try:
            if not login(page):
                logging.error("Login failed. Aborting.")
                return
            traverse_menu_paths(page, menu_paths)
        finally:
            _safe_close("page", lambda: (not page.is_closed()) and page.close())
            _safe_close("context", context.close)
            _safe_close("browser", browser.close)


if __name__ == "__main__":
    main()
