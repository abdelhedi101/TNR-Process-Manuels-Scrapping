RESULT_ROW_PREFIX_SELECTOR = "[id^='Component_PAGE_FORM_1_']"
RESULT_ROW_TABLE_SELECTOR = "[id^='Component_PAGE_FORM_1_DataTable_']"
# Imports
import logging
import os
import re
import time
import unicodedata
from pathlib import Path
import sys
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import Error as PlaywrightError, sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- Marche Transfer de Nostro & Consultation selectors ---
MARCHE_TRANSFER_PATH = (
    "position",
    "titres",
    "gestion de la position marche",
    "transfer de nostro",
)
MARCHE_CONSULTATION_PATH = (
    "position",
    "titres",
    "gestion de la position marche",
    "consultation",
)

# --- Mouvement Suspens Marche selectors ---
MARCHE_SUSPENS_PATH = (
    "position",
    "titres",
    "gestion de la position marche",
    "mouvement suspens marche",
)
MARCHE_SUSPENS_DATE_INPUT_SELECTOR = "input[id^='x-auto-'][id$='-input']"
MARCHE_SUSPENS_DATE_VALUE = "02/03/2026"

def fill_marche_suspens_date(page, module_name: str, path_label: str) -> None:
    input_field = page.locator(MARCHE_SUSPENS_DATE_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Marche Suspens Position Date input not found for %s", path_label)
        return
    try:
        input_field.click(force=True, timeout=4000)
        input_field.fill(MARCHE_SUSPENS_DATE_VALUE)
        page.wait_for_timeout(400)
    except PlaywrightTimeoutError:
        logging.warning("Marche Suspens Position Date fill timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
def close_active_tab_and_others(page):
    # Locate any active closable tab
    tab = page.locator("li.x-tab-strip-closable.x-component.x-tab-strip-active").first
    if not tab.count():
        logging.info("No active closable tab found.")
        return
    try:
        tab.click(button="right", force=True, timeout=4000)
        page.wait_for_timeout(400)
        # Choose 'Close all other tabs' from context menu
        close_others = page.locator(".x-menu-list .x-menu-item", has_text=re.compile(r"close all other tabs", re.IGNORECASE)).first
        if close_others.count():
            close_others.click(force=True, timeout=4000)
            page.wait_for_timeout(400)
        # Right click again to close this tab
        tab.click(button="right", force=True, timeout=4000)
        page.wait_for_timeout(400)
        close_this = page.locator(".x-menu-list .x-menu-item", has_text=re.compile(r"close (this )?tab", re.IGNORECASE)).first
        if close_this.count():
            close_this.click(force=True, timeout=4000)
            page.wait_for_timeout(400)
        logging.info("Closed active tab and others.")
    except PlaywrightTimeoutError:
        logging.warning("Failed to close active tab and others.")
# --- Handle max screens popup ---
def handle_max_screens_popup(page):
    # Look for the Information popup with the specific message
    info_popup = page.locator("div.x-window-plain.x-window-dlg.x-window.x-component")
    if not info_popup.count():
        return False
    header = info_popup.locator("span.x-window-header-text").filter(has_text="Information")
    icon = info_popup.locator("div.ext-mb-icon.ext-mb-info")
    text = info_popup.locator("span.ext-mb-text").filter(has_text=re.compile(r"can’t open more than \\b10\\b screens", re.IGNORECASE))
    if header.count() and icon.count() and text.count():
        ok_button = info_popup.locator("button.x-btn-text", has_text="OK").first
        if ok_button.count():
            try:
                ok_button.click(force=True, timeout=4000)
                page.wait_for_timeout(400)
                logging.info("Closed max screens popup.")
                close_active_tab_and_others(page)
                return True
            except PlaywrightTimeoutError:
                logging.warning("Failed to click OK on max screens popup.")
    return False
# --- Position Detaillée Par Période Tradable Asset and Date From selectors/workflow ---
PERIODE_TRADABLE_ASSET_FIELD_SELECTOR = "#Field_ComponenttradableAsset"
PERIODE_TRADABLE_ASSET_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_tradableAsset']"
PERIODE_TRADABLE_ASSET_GRID_ROW_SELECTOR = "tr[id^='Component_PAGE_FORM_1_DataTable_']"
PERIODE_TRADABLE_ASSET_VALUE = "MA0002"
PERIODE_DATE_FROM_INPUT_SELECTOR = "input[id^='x-auto-'][id$='-input']"
PERIODE_DATE_FROM_VALUE = "01/03/2026"

def ensure_periode_tradable_asset_selected(page, module_name: str, path_label: str) -> None:
    field = page.locator(PERIODE_TRADABLE_ASSET_FIELD_SELECTOR)
    if not field.count():
        logging.info("Periode Tradable Asset field not present for %s", path_label)
        return
    input_field = field.locator(PERIODE_TRADABLE_ASSET_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Periode Tradable Asset input not found for %s", path_label)
        return
    try:
        input_field.click(force=True, timeout=4000)
        input_field.fill(PERIODE_TRADABLE_ASSET_VALUE)
        page.wait_for_timeout(400)
        page.keyboard.press("F2")
        try:
            page.wait_for_selector(PERIODE_TRADABLE_ASSET_GRID_ROW_SELECTOR, timeout=6000)
        except PlaywrightTimeoutError:
            logging.warning("Periode Tradable Asset lookup grid missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        grid_row = page.locator(PERIODE_TRADABLE_ASSET_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Periode Tradable Asset lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Periode Tradable Asset row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Periode Tradable Asset lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)

def fill_periode_date_from(page, module_name: str, path_label: str) -> None:
    input_field = page.locator(PERIODE_DATE_FROM_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Periode Date From input not found for %s", path_label)
        return
    try:
        input_field.click(force=True, timeout=4000)
        input_field.fill(PERIODE_DATE_FROM_VALUE)
        page.wait_for_timeout(400)
    except PlaywrightTimeoutError:
        logging.warning("Periode Date From fill timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
# --- Position Detaillée Par Période selectors and workflow ---
POSITION_DETAILLEE_PERIODE_PATH = (
    "position",
    "titres",
    "gestion de la position client",
    "position detaillee par periode",
)
PERIODE_OWNER_FIELD_SELECTOR = "#Field_Componentowner"
PERIODE_OWNER_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_owner']"
PERIODE_OWNER_GRID_ROW_SELECTOR = "tr[id^='Component_PAGE_FORM_1_DataTable_']"

def ensure_periode_owner_selected(page, module_name: str, path_label: str) -> None:
    field = page.locator(PERIODE_OWNER_FIELD_SELECTOR)
    if not field.count():
        logging.info("Periode Owner field not present for %s", path_label)
        return
    input_field = field.locator(PERIODE_OWNER_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Periode Owner input not found for %s", path_label)
        return
    try:
        input_field.click(force=True, timeout=4000)
        page.wait_for_timeout(400)
        page.keyboard.press("F2")
        try:
            page.wait_for_selector(PERIODE_OWNER_GRID_ROW_SELECTOR, timeout=6000)
        except PlaywrightTimeoutError:
            logging.warning("Periode Owner lookup grid missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        grid_row = page.locator(PERIODE_OWNER_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Periode Owner lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Periode Owner row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Periode Owner lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
# --- PositionControlContext dropdown selectors and workflow ---
POSITION_CONTROL_CONTEXT_DROPDOWN_SELECTOR = "[id^='x-auto-']"
POSITION_CONTROL_CONTEXT_OPTION_SELECTOR = "//div[contains(@class,'x-boundlist-item') and contains(text(),'PositionControlContext')]"

def select_position_control_context(page, module_name: str, path_label: str) -> None:
    dropdown = page.locator(POSITION_CONTROL_CONTEXT_DROPDOWN_SELECTOR)
    if not dropdown.count():
        logging.info("PositionControlContext dropdown not present for %s", path_label)
        return
    try:
        dropdown.click(force=True, timeout=4000)
        page.wait_for_timeout(400)
        option = page.locator(POSITION_CONTROL_CONTEXT_OPTION_SELECTOR).first
        if not option.count():
            logging.warning("PositionControlContext option not found for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        option.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("PositionControlContext dropdown interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
# --- Tradable Asset selectors and workflow ---
TRADABLE_ASSET_FIELD_SELECTOR = "#Field_ComponenttradableAsset"
TRADABLE_ASSET_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_tradableAsset']"
TRADABLE_ASSET_GRID_ROW_SELECTOR = "tr[id^='Component_PAGE_FORM_1_DataTable_']"
TRADABLE_ASSET_VALUE = "MA00020"

def ensure_tradable_asset_selected(page, module_name: str, path_label: str) -> None:
    field = page.locator(TRADABLE_ASSET_FIELD_SELECTOR)
    if not field.count():
        logging.info("Tradable Asset field not present for %s", path_label)
        return
    input_field = field.locator(TRADABLE_ASSET_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Tradable Asset input not found for %s", path_label)
        return
    try:
        input_field.click(force=True, timeout=4000)
        input_field.fill(TRADABLE_ASSET_VALUE)
        page.wait_for_timeout(400)
        page.keyboard.press("F2")
        try:
            page.wait_for_selector(TRADABLE_ASSET_GRID_ROW_SELECTOR, timeout=6000)
        except PlaywrightTimeoutError:
            logging.warning("Tradable Asset lookup grid missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        grid_row = page.locator(TRADABLE_ASSET_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Tradable Asset lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Tradable Asset row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Tradable Asset lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
# --- Position Disponible selectors and workflow ---
POSITION_DISPONIBLE_PATH = (
    "position",
    "titres",
    "gestion de la position client",
    "position disponible",
)
OWNER_FIELD_SELECTOR = "#Field_Componentowner"
OWNER_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_owner']"
OWNER_GRID_ROW_SELECTOR = "tr[id^='Component_PAGE_FORM_1_DataTable_']"

def ensure_owner_selected(page, module_name: str, path_label: str) -> None:
    field = page.locator(OWNER_FIELD_SELECTOR)
    if not field.count():
        logging.info("Owner field not present for %s", path_label)
        return
    input_field = field.locator(OWNER_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Owner input not found for %s", path_label)
        return
    try:
        input_field.click(force=True, timeout=4000)
        page.wait_for_timeout(400)
        page.keyboard.press("F2")
        try:
            page.wait_for_selector(OWNER_GRID_ROW_SELECTOR, timeout=6000)
        except PlaywrightTimeoutError:
            logging.warning("Owner lookup grid missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        grid_row = page.locator(OWNER_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Owner lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Owner row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Owner lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)

LOGIN_ENTRY = os.getenv("MODULE_URL", "https://10.1.140.42/MegaCor/")
MEGACOMMON_ENTRY = os.getenv("MEGACOMMON_URL", "https://10.1.140.42/MegaCommon/")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/CDG/Custody menu/saisie.txt"))
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "migration")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Vermeg+123")
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "CDG_CAPITAL")
AUTH_TYPE = os.getenv("AUTH_TYPE", "keycloak").strip().lower()

MENU_TABS = [
    "Referentiel",
    "Position",
    "Facturation",
    "Fiscalite",
    "Parametrage",
    "Rapport",
    "Report",
]

VIEW_OPTION_PATTERN = re.compile(r"(?:voir|view)", re.IGNORECASE)
EDIT_OPTION_PATTERN = re.compile(r"edit", re.IGNORECASE)
ERROR_MESSAGE_PATTERN = re.compile(r"\b(log|internal_error|error|err)\b", re.IGNORECASE)
EMPTY_HEADING_PATTERN = re.compile(r"^\s*$")
OK_BUTTON_PATTERN = re.compile(r"^ok$", re.IGNORECASE)
ERROR_HEADING_TEXT = "Error in ProcessPageResult.onFailure"
NO_VALIDATION_MESSAGE = "No Validation Configuration Found."
POSITION_MENU_NAME = "position"
POSITION_DATE_LABEL = "Position Date"
POSITION_DATE_VALUE = "01/01/2026"
POSITION_BASIS_LABEL = "Position Basis"
POSITION_BASIS_VALUE = "businessdate"
POSITION_FILTER_PATHS: Dict[Tuple[str, ...], Dict[str, bool]] = {
    ("position", "titres", "gestion de la position client", "consultation"): {"basis": True},
    ("position", "titres", "gestion de la position client", "consultation des positions fermes"): {"basis": True},
    ("position", "titres", "gestion de la position client", "consultation avancee des positions"): {"basis": True},
    ("position", "titres", "gestion de la position client", "mouvement en cours client"): {"basis": False},
    ("position", "titres", "gestion de la position client", "position disponible"): {"basis": True},
    ("position", "titres", "gestion de la position client", "position detaillee par periode"): {"basis": True},
    ("position", "titres", "gestion de la position client", "consultation des releves"): {"basis": True},
    ("position", "titres", "gestion de la position marche", "transfer de nostro"): {"basis": True},
    ("position", "titres", "gestion de la position marche", "consultation"): {"basis": True},
    ("position", "titres", "gestion de la position marche", "mouvement suspens marche"): {"basis": False},
}
SUCCESS_MESSAGE_PATTERN = re.compile(r"saved", re.IGNORECASE)
LOG_FILE_ERROR_MESSAGE = "The program has generated an error described in the log file"
TOO_MUCH_DATA_MESSAGE = "Please refine the search criteria. Too much data correspond"
ADVANCED_POSITION_PATH = (
    "position",
    "titres",
    "gestion de la position client",
    "consultation avancee des positions",
)
CLIENT_SEC_ACCOUNT_FIELD_SELECTOR = "#Field_ComponentclientSecAccount"
CLIENT_SEC_ACCOUNT_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_clientSecAccount']"
CLIENT_SEC_ACCOUNT_GRID_CELL_SELECTOR = "td.x-grid3-col-client"


def get_position_filter_mode(path: List[str]) -> Optional[Dict[str, bool]]:
    if not path:
        return None
    normalized = tuple(segment.strip().lower() for segment in path)
    return POSITION_FILTER_PATHS.get(normalized)

EXECUTE_CRITERIA_SELECTOR = "#Component_PAGE_FORM_0_executeCriteria_null"
VIEW_RETURN_SELECTOR = "#Component_PAGE_FORM_2_return_null"
SAVE_BUTTON_SELECTOR = "#Component_PAGE_FORM_2_save_null"
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}

# --- Saisie Instruction Client selectors for CDG ---
SAISIE_INSTRUCTION_CLIENT_PATH = (
    "règlement/livraison",
    "instructions clients",
    "saisie instruction client",
)
INSTRUCTIONS_MARCHE_APPARIEMENT_PATH = (
    "règlement/livraison",
    "instructions marché",
    "appariement",
)
INSTRUCTIONS_MARCHE_DENOUEMENT_PATH = (
    "règlement/livraison",
    "instructions marché",
    "dénouement",
)
MEGACOMMON_POSITION_CONSULTATION_PATH = (
    "position",
    "titres",
    "gestion de la position client",
    "consultation",
)
MEGACOMMON_POSITION_DATE_CONTAINER_ID = "Component_PAGE_FORM_0_atomicCriteria_positionDate_criteria"
MEGACOMMON_POSITION_DATE_FULL_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div/div[2]/div[1]/table/tbody/tr[1]/td[1]/div/table/tbody/tr/td[3]/div/input"
MEGACOMMON_POSITION_DATE_ID_SUFFIX = "-input"
SAISIE_INSTRUCTION_CLIENT_FORM_SELECTOR = "table.x-form-body.x-component[id^='x-auto-']"


def is_saisie_instruction_client_path(normalized_path: Tuple[str, ...]) -> bool:
    return (
        len(normalized_path) >= 3
        and normalized_path[0] == "règlement/livraison"
        and normalized_path[-1] == "saisie instruction client"
        and normalized_path[1].startswith("instructions clients")
    )


SAISIE_INSTRUCTION_CLIENT_VARIABLES_FILE = Path(
    os.getenv("SAISIE_INSTRUCTION_CLIENT_VARIABLES_FILE", "variable_saisies/Instruction_Client_CDG.txt")
)
SCREENSHOT_PROJECT_ROOT = "CDG"
SCREENSHOT_RUN_ROOT = "Process_RL"
SAISIE_SAVE_POPUP_OBSERVE_MS = 5000
SAISIE_BLOCKING_POPUP_TEXT_PATTERN = re.compile(r"Deal\s+Reference\s+must\s+not\s+exceed\s+10\s+characters", re.IGNORECASE)
SAISIE_FIELD_SPECS: List[Dict[str, str]] = [
    {
        "key": "otc_traded",
        "label": "O TC Traded",
        "selector": "input[id^='x-auto-'][id$='-input'][name='Component_PAGE_FORM_0_oTCTraded'], input[name='Component_PAGE_FORM_0_oTCTraded']",
    },
    {"key": "client_reference", "label": "Client Reference", "selector": "input[name='Component_PAGE_FORM_0_clientReference']"},
    {
        "key": "transaction_type",
        "label": "Transaction Type",
        "selector": "#Component_PAGE_FORM_0_transactionType input[id^='x-auto-'][id$='-input'], input[name='Component_PAGE_FORM_0_transactionType'], input[name='transactionType']",
    },
    {"key": "tradable_asset", "label": "Tradable Asset", "selector": "input[name='Component_PAGE_FORM_0_tradableAsset']"},
    {"key": "incoming_quantity", "label": "Incoming Quantity", "selector": "input[name='Component_PAGE_FORM_0_incomingQuantity']"},
    {"key": "client_sec_account", "label": "Client Sec Account", "selector": "input[name='Component_PAGE_FORM_0_clientSecAccount']"},
    {"key": "counterpart", "label": "Counterpart", "selector": "input[name='Component_PAGE_FORM_0_counterpart']"},
    {"key": "beneficiary", "label": "Beneficiary", "selector": "input[name='Component_PAGE_FORM_0_beneficiary']"},
    {
        "key": "trade_date",
        "label": "Trade Date",
        "selector": "#Component_PAGE_FORM_0_tradeDate input[id^='x-auto-'][id$='-input'], input[name='Component_PAGE_FORM_0_tradeDate']",
    },
    {"key": "price", "label": "Price", "selector": "input[name='Component_PAGE_FORM_0_price']"},
    {
        "key": "effective_value_date",
        "label": "Effective Value Date",
        "selector": "#Component_PAGE_FORM_0_effectiveValueDate input[id^='x-auto-'][id$='-input'], input[name='Component_PAGE_FORM_0_effectiveValueDate']",
    },
    {"key": "negociated_rate", "label": "Negociated Rate", "selector": "input[name='Component_PAGE_FORM_0_negociatedRate']"},
]

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def load_or_initialize_saisie_variables(file_path: Path) -> Dict[str, str]:
    """Load saisie variables from file, creating if missing."""
    values: Dict[str, str] = {}
    label_to_key: Dict[str, str] = {spec["label"].lower(): spec["key"] for spec in SAISIE_FIELD_SPECS}
    
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                label, raw_value = line.split("=", 1)
                normalized_label = label.strip().lower()
                key = label_to_key.get(normalized_label)
                if key:
                    values[key] = raw_value.strip()
    else:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with file_path.open("w", encoding="utf-8") as fh:
        fh.write("# Valeurs modifiables pour le menu Saisie Instruction Client\n")
        for spec in SAISIE_FIELD_SPECS:
            key = spec["key"]
            label = spec["label"]
            fh.write(f"{label}={values.get(key, '')}\n")
    
    logging.info("Loaded saisie variables from %s", file_path)
    return values


def dismiss_saisie_blocking_popup_if_present(page, path_label: str) -> bool:
    popup_text = page.locator("span.ext-mb-text").filter(has_text=SAISIE_BLOCKING_POPUP_TEXT_PATTERN).first
    if not popup_text.count():
        return False

    ok_button = page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first
    if ok_button.count():
        try:
            ok_button.click(force=True, timeout=4000)
            page.wait_for_timeout(300)
            logging.info("Dismissed blocking popup for %s", path_label)
            return True
        except PlaywrightTimeoutError:
            logging.warning("Failed to click OK on blocking popup for %s", path_label)
    return False


def is_saisie_instruction_client_label(path_label: str) -> bool:
    return "saisie instruction client" in (path_label or "").strip().lower()


def get_process_rl_screenshot_dir(module_name: str, path_label: str) -> Path:
    module_folder = slugify(module_name)
    top_level_menu = slugify(path_label.split(">")[0].strip()) if ">" in path_label else slugify(path_label)
    target_dir = SCREENSHOT_DIR / SCREENSHOT_PROJECT_ROOT / SCREENSHOT_RUN_ROOT / module_folder / top_level_menu
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def capture_saisie_save_popup_screenshot(page, module_name: str, path_label: str) -> None:
    target_dir = get_process_rl_screenshot_dir(module_name, path_label)

    timestamp = int(time.time())
    filename = f"save_popup_{slugify(path_label)}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.info("Captured save popup screenshot for %s at %s", path_label, target)


def wait_for_saisie_save_popup_and_capture(page, module_name: str, path_label: str) -> bool:
    checks = 0
    while True:
        if page.is_closed():
            logging.warning("Page closed while waiting for post-save popup on %s", path_label)
            return False
        popup_visible = (
            page.locator("div.x-window-plain.x-window-dlg.x-window.x-component:visible").count() > 0
            or page.locator("span.ext-mb-text:visible").count() > 0
            or page.locator("span.x-window-header-text:visible").count() > 0
        )
        if popup_visible:
            capture_saisie_save_popup_screenshot(page, module_name, path_label)
            if SAISIE_SAVE_POPUP_OBSERVE_MS > 0:
                logging.info("Keeping popup visible for %d ms on %s", SAISIE_SAVE_POPUP_OBSERVE_MS, path_label)
                page.wait_for_timeout(SAISIE_SAVE_POPUP_OBSERVE_MS)
            dismiss_informational_popup(page)
            dismiss_error_dialog(page, path_label)
            return True
        checks += 1
        if checks % 20 == 0:
            logging.info("Still waiting for post-save popup on %s", path_label)
        page.wait_for_timeout(250)


def capture_market_action_popup_screenshot(page, module_name: str, path_label: str, action_label: str) -> None:
    target_dir = get_process_rl_screenshot_dir(module_name, path_label)

    timestamp = int(time.time())
    filename = f"{slugify(action_label)}_popup_{slugify(path_label)}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.info("Captured %s popup screenshot for %s at %s", action_label, path_label, target)


def wait_for_market_action_popup(page, module_name: str, path_label: str, action_label: str, timeout_ms: int = 15000) -> bool:
    popup_selector = (
        "div.x-window-plain.x-window-dlg.x-window.x-component:visible, "
        "span.ext-mb-text:visible, "
        "span.x-window-header-text:visible"
    )
    try:
        page.wait_for_selector(popup_selector, timeout=timeout_ms)
        capture_market_action_popup_screenshot(page, module_name, path_label, action_label)
        page.wait_for_timeout(1000)
        return True
    except PlaywrightTimeoutError:
        logging.warning("%s popup not detected for %s", action_label, path_label)
        return False


def run_market_result_action_workflow(
    page,
    module_name: str,
    path_label: str,
    action_label: str,
    action_xpath: str,
) -> bool:
    result_row = find_first_result_row(page)
    if result_row is None:
        logging.warning("No result row available before %s for %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False

    try:
        result_row.scroll_into_view_if_needed()
        result_row.click(force=True, timeout=4000)
        page.wait_for_timeout(300)
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.warning("Unable to click first result row before %s for %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False

    action_candidates = [
        page.locator(f"xpath={action_xpath}").first,
        page.locator("button.x-btn-text").filter(has_text=re.compile(rf"^\s*{re.escape(action_label)}\s*$", re.IGNORECASE)).first,
        page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(action_label)}\s*$", re.IGNORECASE)).first,
    ]

    action_button = None
    for candidate in action_candidates:
        if candidate.count():
            action_button = candidate
            break

    if action_button is None:
        logging.warning("%s button not found for %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False

    try:
        action_button.click(force=True, timeout=4000)
        page.wait_for_timeout(300)
    except PlaywrightTimeoutError:
        logging.warning("%s button click timed out for %s", action_label, path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False

    popup_found = wait_for_market_action_popup(page, module_name, path_label, action_label)
    if popup_found:
        dismiss_informational_popup(page)
        dismiss_error_dialog(page, path_label)
    return popup_found


def fill_saisie_instruction_client_form(page, module_name: str, path_label: str) -> bool:
    """Fill saisie instruction client form with variables from config file, pressing Tab to navigate between non-consecutive fields."""
    logging.info("Filling saisie instruction client form for %s", path_label)
    
    variables = load_or_initialize_saisie_variables(SAISIE_INSTRUCTION_CLIENT_VARIABLES_FILE)
    form_root = page.locator(SAISIE_INSTRUCTION_CLIENT_FORM_SELECTOR).first
    try:
        form_root.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        logging.warning("Saisie instruction client form not found for %s", path_label)
        return False

    populated_fields = [spec for spec in SAISIE_FIELD_SPECS if variables.get(spec["key"], "").strip()]
    tab_count = 0
    max_tabs = 40
    
    for field_index, spec in enumerate(populated_fields):
        key = spec["key"]
        label = spec["label"]
        selector = spec["selector"]
        value = variables.get(key, "").strip()
        
        try:
            field = form_root.locator(selector).first
            if not field.count():
                field = page.locator(selector).first
            if not field.count():
                logging.warning("Field '%s' not found for %s", label, path_label)
                continue
            
            # Click the field to ensure focus
            field.click(force=True, timeout=4000)
            page.wait_for_timeout(200)

            if key == "otc_traded" and value.lower() == "true":
                arrow_trigger = page.locator("#Component_PAGE_FORM_0_oTCTraded img.x-form-trigger-arrow").first
                if not arrow_trigger.count():
                    arrow_trigger = field.locator(
                        "xpath=ancestor::div[contains(@class,'x-form-field-wrap')][1]//img[contains(@class,'x-form-trigger-arrow')]"
                    ).first

                if arrow_trigger.count():
                    arrow_trigger.click(force=True, timeout=4000)
                    page.wait_for_timeout(300)

                true_option = page.locator("div[role='listitem'].x-combo-list-item").filter(has_text=re.compile(r"^true$", re.IGNORECASE)).first
                if true_option.count():
                    true_option.click(force=True, timeout=4000)
                    page.wait_for_timeout(300)
                    logging.info("Selected %s = true via dropdown", label)
                else:
                    field.fill(value)
                    page.wait_for_timeout(300)
                    logging.info("Filled %s with value: %s (combo fallback)", label, value)
            elif key == "transaction_type":
                transaction_container = page.locator("#Component_PAGE_FORM_0_transactionType").first
                transaction_arrow = transaction_container.locator("img.x-form-trigger-arrow").first if transaction_container.count() else page.locator("#Component_PAGE_FORM_0_transactionType img.x-form-trigger-arrow").first
                if transaction_arrow.count():
                    transaction_arrow.click(force=True, timeout=4000)
                    page.wait_for_timeout(300)

                transaction_option = page.locator("div[role='listitem'].x-combo-list-item").filter(
                    has_text=re.compile(rf"^\s*{re.escape(value)}\s*$", re.IGNORECASE)
                ).first
                if transaction_option.count():
                    transaction_option.click(force=True, timeout=4000)
                    page.wait_for_timeout(300)
                    logging.info("Selected %s = %s via dropdown", label, value)
                else:
                    field.fill(value)
                    page.wait_for_timeout(300)
                    logging.info("Filled %s with value: %s (fallback)", label, value)
            else:
                # Fill the field
                field.fill(value)
                page.wait_for_timeout(300)
                logging.info("Filled %s with value: %s (Tab count: %d)", label, value, tab_count)

            page.wait_for_timeout(2000)

            if field_index < len(populated_fields) - 1 and tab_count < max_tabs:
                page.keyboard.press("Tab")
                tab_count += 1
                page.wait_for_timeout(1000)
                dismiss_saisie_blocking_popup_if_present(page, path_label)
                logging.info("Pressed Tab #%d after %s", tab_count, label)
            
        except PlaywrightTimeoutError:
            logging.warning("Timeout filling field '%s' for %s", label, path_label)
            return False
        except Exception as e:
            logging.error("Error filling field '%s': %s", label, e)
            return False
    
    logging.info("Total Tab presses used during saisie: %d", tab_count)
    
    # Click Save button
    try:
        save_button_candidates = [
            page.locator("#Component_PAGE_FORM_0_save_null").first,
            page.locator("div.x-icon-btn.x-nodrag.x-component#Component_PAGE_FORM_0_save_null").first,
            page.locator(SAVE_BUTTON_SELECTOR).first,
            page.get_by_role("button", name=re.compile(r"save", re.IGNORECASE)).first,
            page.locator("button.x-btn-text").filter(has_text=re.compile(r"save", re.IGNORECASE)).first,
        ]
        save_button = None
        for candidate in save_button_candidates:
            if candidate.count():
                save_button = candidate
                break

        if save_button is not None:
            save_button.click(force=True, timeout=4000)
            page.wait_for_timeout(600)
            logging.info("Clicked Save button for %s", path_label)
            if wait_for_saisie_save_popup_and_capture(page, module_name, path_label):
                logging.info("Detected post-save popup for %s", path_label)
            return True
        else:
            logging.warning("Save button not found for %s", path_label)
            return False
    except PlaywrightTimeoutError:
        logging.warning("Timeout clicking Save button for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False


def open_menu_path_exact(page, path: Tuple[str, ...]) -> bool:
    if not path:
        return False

    normalized_path = tuple(normalize_menu_text(part) for part in path)
    if normalized_path == tuple(normalize_menu_text(part) for part in MEGACOMMON_POSITION_CONSULTATION_PATH):
        return open_position_client_consultation_turbo(page)

    if not open_top_level_menu(page, path[0]):
        logging.warning("Top level menu %s not opened", path[0])
        return False

    for idx, segment in enumerate(path[1:], start=1):
        level = idx + 1

        # Fast dedicated handling for the first child level (e.g. Position -> Titres)
        # because this is where lazy-rendering often causes the traversal to stall.
        if idx == 1 and len(path) > 2:
            node = force_expand_first_child_level(page, segment)
            if not node.count():
                logging.warning("Tree node %s at level %s not found", segment, level)
                return False
            page.wait_for_timeout(60)
            continue

        node = find_tree_node(
            page,
            segment,
            level,
            max_scroll_steps=10,
            scroll_step_px=520,
            settle_ms=80,
        )
        if not node.count():
            logging.warning("Tree node %s at level %s not found", segment, level)
            return False
        try:
            scroll_tree_area_into_view(page)
            node.scroll_into_view_if_needed()
            # Intermediate path items: always double-click. Leaf item: single-click.
            if idx < len(path) - 1:
                node.dblclick(force=True, timeout=3000)
                wait_for_tree_level_items(page, level + 1, timeout_ms=1600)
            else:
                node.click(force=True, timeout=3000)
            page.wait_for_timeout(120)
        except (PlaywrightTimeoutError, PlaywrightError):
            logging.warning("Failed to open node %s at level %s", segment, level)
            return False
    return True


def open_position_client_consultation_turbo(page) -> bool:
    page = ensure_alive_page(page)
    if page is None:
        logging.warning("No alive page available for MegaCommon turbo navigation")
        return False

    logging.info("[MegaCommon NAV] Ouverture du menu 'position'")
    if not open_top_level_menu(page, "position"):
        logging.warning("Top level menu position not opened")
        return False

    logging.info("[MegaCommon NAV] Recherche du noeud 'titres' (level 2)")
    titres = find_tree_node(
        page,
        "titres",
        2,
        max_scroll_steps=14,
        scroll_step_px=650,
        settle_ms=45,
    )
    if not titres.count():
        logging.error("[MegaCommon NAV] Titres node not found at level 2")
        return False
    try:
        titres.scroll_into_view_if_needed()
        titres.dblclick(force=True, timeout=2500)
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.error("[MegaCommon NAV] Echec scroll/dblclick sur 'titres'")
        return False
    wait_for_tree_level_items(page, 3, timeout_ms=1800)

    logging.info("[MegaCommon NAV] Recherche du noeud 'gestion de la position client' (level 3)")
    gestion_client = find_tree_node(
        page,
        "gestion de la position client",
        3,
        max_scroll_steps=10,
        scroll_step_px=620,
        settle_ms=45,
    )
    if not gestion_client.count():
        logging.error("[MegaCommon NAV] Gestion de la Position Client node not found at level 3")
        return False
    try:
        gestion_client.scroll_into_view_if_needed()
        gestion_client.dblclick(force=True, timeout=2500)
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.error("[MegaCommon NAV] Echec scroll/dblclick sur 'gestion de la position client'")
        return False
    wait_for_tree_level_items(page, 4, timeout_ms=1800)

    logging.info("[MegaCommon NAV] Recherche du noeud 'consultation' (level 4)")
    consultation = find_tree_node(
        page,
        "consultation",
        4,
        max_scroll_steps=8,
        scroll_step_px=620,
        settle_ms=45,
    )
    if not consultation.count():
        logging.error("[MegaCommon NAV] Consultation node not found at level 4")
        return False
    try:
        consultation.scroll_into_view_if_needed()
        consultation.click(force=True, timeout=2500)
        page.wait_for_timeout(80)
        logging.info("[MegaCommon NAV] Consultation node ouvert (click)")
        return True
    except (PlaywrightTimeoutError, PlaywrightError):
        try:
            consultation.dblclick(force=True, timeout=2200)
            page.wait_for_timeout(80)
            logging.info("[MegaCommon NAV] Consultation node ouvert (dblclick)")
            return True
        except (PlaywrightTimeoutError, PlaywrightError):
            logging.error("[MegaCommon NAV] Echec ouverture Consultation node")
            return False


def force_expand_first_child_level(page, segment: str):
    for _ in range(6):
        node = find_tree_node(
            page,
            segment,
            2,
            max_scroll_steps=5,
            scroll_step_px=620,
            settle_ms=50,
        )
        if node.count():
            try:
                scroll_tree_area_into_view(page)
                node.scroll_into_view_if_needed()
                expand_tree_node_fast(page, node)
                wait_for_tree_level_items(page, 3, timeout_ms=1400)
                return node
            except (PlaywrightTimeoutError, PlaywrightError):
                pass

        scroll_tree_container_step(page, step_px=420, settle_ms=50)
        page.wait_for_timeout(80)

    return page.locator("div[role=\"treeitem\"][aria-level=\"-1\"]").first


def fill_consultation_field(page, selectors: List[str], value: str, label: str, settle_ms: int = 80) -> bool:
    value = (value or "").strip()
    if not value:
        logging.warning("Skipping empty value for %s", label)
        return False

    for selector in selectors:
        field = page.locator(selector).first
        if not field.count():
            continue
        try:
            field.scroll_into_view_if_needed()
        except PlaywrightError:
            pass
        try:
            field.click(force=True, timeout=4000)
            field.press("Control+A")
            field.fill(value)
            page.wait_for_timeout(settle_ms)
            logging.info("Filled %s with %s", label, value)
            return True
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    logging.warning("Field %s not found", label)
    return False


def fill_position_date_with_indicator(page, value: str) -> bool:
    value = (value or "").strip()
    if not value:
        logging.warning("Skipping empty value for Position Date")
        return False

    # Keep container-first targeting, with controlled fallbacks for dynamic layouts.
    selectors = [
        f"#{MEGACOMMON_POSITION_DATE_CONTAINER_ID} input.x-form-field.x-form-text",
        f"xpath=//*[@id='{MEGACOMMON_POSITION_DATE_CONTAINER_ID}']//input[contains(@class,'x-form-text')]",
        f"xpath={MEGACOMMON_POSITION_DATE_FULL_XPATH}",
        "//label[normalize-space()='Date de la position']/ancestor::tr[1]//input[contains(@class,'x-form-text')]",
        "//label[normalize-space()='Date de la position']/ancestor::tr//input[contains(@class,'x-form-field')]",
        "//label[normalize-space()='Position Date']/ancestor::tr[1]//input[contains(@class,'x-form-text') and contains(@id,'x-auto-') and contains(@id,'-input')]",
        "//label[normalize-space()='Position Date']/ancestor::tr[1]//input[contains(@class,'x-form-field') and contains(@id,'-input')]",
        "//label[normalize-space()='Position Date']/ancestor::tr//input[contains(@class,'x-form-field')]",
    ]

    for selector in selectors:
        field = page.locator(selector).first
        if not field.count():
            continue
        try:
            field.scroll_into_view_if_needed()
        except PlaywrightError:
            pass
        try:
            field.click(force=True, timeout=4000)
            field.press("Control+A")
            field.fill(value)
            # Visual marker to validate the exact targeted input during runtime.
            field.evaluate("el => el.style.outline = '2px solid #ff8c00'")
            field_id = field.get_attribute("id") or "<no-id>"
            logging.info("POSITION_DATE_INDICATOR: targeted input id=%s selector=%s", field_id, selector)
            page.wait_for_timeout(80)
            return True
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    logging.warning("Position Date field not found with dedicated selectors")
    return False


def tree_node_label_text(node) -> str:
    try:
        label = node.locator(".x-tree3-node-text, .x-tree-node-text, span").first
        if label.count():
            text = (label.inner_text() or "").strip()
            if text:
                return text
    except PlaywrightError:
        pass
    try:
        return (node.inner_text() or "").strip()
    except PlaywrightError:
        return ""


def expand_tree_node_fast(page, node) -> None:
    if node.get_attribute("aria-expanded") == "true":
        return

    expanders = [
        node.locator(".x-tree-ec-icon").first,
        node.locator(".x-tree-elbow-plus").first,
        node.locator(".x-tree-elbow-end-plus").first,
    ]
    for expander in expanders:
        try:
            if expander.count():
                expander.click(force=True, timeout=1200)
                page.wait_for_timeout(40)
                if node.get_attribute("aria-expanded") == "true":
                    return
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

    try:
        node.click(force=True, timeout=2000)
    except (PlaywrightTimeoutError, PlaywrightError):
        pass
    if node.get_attribute("aria-expanded") != "true":
        try:
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(40)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
    if node.get_attribute("aria-expanded") != "true":
        try:
            node.dblclick(force=True, timeout=1800)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass


def load_pre_consultation_values() -> Dict[str, str]:
    values = load_or_initialize_saisie_variables(SAISIE_INSTRUCTION_CLIENT_VARIABLES_FILE)
    return {
        "position_date": (values.get("effective_value_date", "") or "").strip(),
        "position_basis": "Date métier",
        "client_sec_account": (values.get("client_sec_account", "") or "").strip(),
        "tradable_asset": (values.get("tradable_asset", "") or "").strip(),
    }


def fill_position_basis_dropdown(page, value: str) -> bool:
    value = (value or "").strip()
    if not value:
        logging.warning("Skipping empty Position Basis")
        return False

    input_selectors = [
        "#Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria input",
        "input[name='Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria']",
        "xpath=//*[@id='Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria']//input",
        "//label[normalize-space()='Base de la position']/ancestor::tr[1]//input[contains(@class,'x-form-field')]",
        "//label[normalize-space()='Position Basis']/ancestor::tr[1]//input[contains(@class,'x-form-field')]",
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
    text_pattern = re.compile(rf"^{re.escape(value)}$", re.IGNORECASE)
    for selector in [
        "div.x-boundlist div.x-boundlist-item",
        "div.x-boundlist-item",
        "li.x-boundlist-item",
        "div.x-combo-list-item",
        ".x-menu-item",
    ]:
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


def prepare_megacommon_consultation(page, criteria: Dict[str, str]) -> bool:
    path_label = " > ".join(MEGACOMMON_POSITION_CONSULTATION_PATH)

    def _fill_once() -> bool:
        alive_page = ensure_alive_page(page)
        if alive_page is None:
            logging.warning("No alive MegaCommon page available while preparing consultation")
            return False

        if not open_menu_path_exact(alive_page, MEGACOMMON_POSITION_CONSULTATION_PATH):
            return False

        ok_local = True
        ok_local &= fill_position_date_with_indicator(alive_page, criteria.get("position_date", ""))
        ok_local &= fill_position_basis_dropdown(alive_page, criteria.get("position_basis", "Date métier"))
        ok_local &= fill_consultation_field(
            alive_page,
            ["input[name='Component_PAGE_FORM_0_atomicCriteria_clientSecAccount_criteria']"],
            criteria.get("client_sec_account", ""),
            "Client Sec Account",
            settle_ms=60,
        )
        ok_local &= fill_consultation_field(
            alive_page,
            ["input[name='Component_PAGE_FORM_0_atomicCriteria_tradableAsset_criteria']"],
            criteria.get("tradable_asset", ""),
            "Tradable Asset",
            settle_ms=60,
        )
        return ok_local

    ok = _fill_once()
    if not ok:
        logging.warning("MegaCommon consultation field fill failed on first attempt; retrying once")
        try:
            page.wait_for_timeout(1200)
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        ok = _fill_once()

    if ok:
        logging.info("Prepared MegaCommon consultation criteria for %s", path_label)
    return ok


def execute_megacommon_consultation(page, criteria: Dict[str, str]) -> bool:
    if not prepare_megacommon_consultation(page, criteria):
        return False

    page.wait_for_timeout(1000)

    execute_button = page.locator(EXECUTE_CRITERIA_SELECTOR).first
    if not execute_button.count():
        logging.warning("Execute Criteria button not found on MegaCommon consultation")
        return False

    try:
        execute_button.click(force=True, timeout=8000)
        page.wait_for_timeout(800)
        handle_execute_search_popup(page, "MegaCommon", " > ".join(MEGACOMMON_POSITION_CONSULTATION_PATH))
        logging.info("Executed final MegaCommon consultation search")
        return True
    except (PlaywrightTimeoutError, PlaywrightError):
        logging.warning("Execute Criteria click failed on MegaCommon consultation")
        return False


def view_first_result_and_screenshot_position(page, suffix: str) -> bool:
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
        logging.warning("No result row found for position screenshot (%s); skipping", suffix)
        return False

    try:
        result_row.scroll_into_view_if_needed()
        result_row.click(button="right", force=True, timeout=4000)
        page.wait_for_timeout(600)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Right-click on result row failed (%s): %s", suffix, exc)
        return False

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

    panel_found = False
    deadline = time.time() + 10.0
    while time.time() < deadline:
        for selector in [
            "xpath=//*[contains(@class,'x-panel-header-text') and contains(normalize-space(text()),'Consultation')]",
            "xpath=//span[contains(@class,'x-panel-header-text') and contains(normalize-space(text()),'Position')]",
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
        logging.warning("Consultation panel not found after 'Voir' (%s); taking screenshot anyway", suffix)

    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)
    except Exception:
        pass

    target_dir = SCREENSHOT_DIR / "CDG" / "Process_RL" / "megacommon" / "position"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"position_{suffix}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(target_dir / filename), full_page=True)
        logging.info("Position consultation screenshot saved: %s", target_dir / filename)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Failed to take position screenshot (%s): %s", suffix, exc)

    for selector in [
        "#Component_PAGE_FORM_2_return_null",
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


def slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    return cleaned.strip("_").lower() or "node"


def capture_failure(page, module_name: str, node_text: str, *, always: bool = False) -> None:
    logging.info(
        "Skipping generic screenshot for %s; only popup-triggered screenshots are enabled",
        node_text,
    )
    dismiss_error_dialog(page, node_text)
    return


def failure_indicators_present(page) -> bool:
    # Check if this is just a "too much data" informational popup - not an error
    too_much_data_popup = page.locator("span.ext-mb-text").filter(has_text=TOO_MUCH_DATA_MESSAGE).count()
    if too_much_data_popup:
        logging.info("Too much data informational popup detected - not an error, will dismiss")
        return False
    
    warning_icon_locator = page.locator("div.ext-mb-icon.ext-mb-warning")
    warning_icon_count = warning_icon_locator.count()
    header_locator = page.locator("span.x-window-header-text")
    header_error_count = header_locator.filter(has_text="error").count()
    header_count = header_locator.count()

    # Trigger screenshot when the inline error icon and "Action Not Found" label appear together.
    action_not_found_icon = page.locator("[id^='x-auto-'] > img")
    action_not_found_label = page.locator("[id^='x-auto-']").filter(
        has_text=re.compile(r"Action\s+Not\s+Found", re.IGNORECASE)
    )

    if page.locator("[id^='x-auto-'][id$='-label']").filter(has_text=ERROR_HEADING_TEXT).count():
        return True
    if page.locator("[id^='x-auto-'][id$='-label']").filter(has_text=EMPTY_HEADING_PATTERN).count():
        return True
    if warning_icon_count:
        return True
    if page.locator("span.ext-mb-text[id^='x-auto-'][id$='-content']").filter(has_text="null").count():
        return True
    if page.locator("span.ext-mb-text[id^='x-auto-'][id$='-content']").filter(has_text=NO_VALIDATION_MESSAGE).count():
        return True
    if page.locator("div.ext-mb-content span.ext-mb-text").filter(has_text=NO_VALIDATION_MESSAGE).count():
        return True
    if page.locator("span.ext-mb-text").filter(has_text=ERROR_MESSAGE_PATTERN).count():
        return True
    if header_error_count:
        return True
    if page.locator("label").filter(has_text=LOG_FILE_ERROR_MESSAGE).count():
        return True
    # New error label as screenshot declencher
    if page.locator("label[id^='x-auto-']").filter(has_text=LOG_FILE_ERROR_MESSAGE).count():
        return True

    special_content = page.locator("[id^='x-auto-'][id$='-content']")
    if special_content.count() and not warning_icon_count and not header_count:
        return True

    # Ajout du déclencheur custom demandé
    custom_alert = page.locator("xpath=/html/body/div[10]/div[2]/div[1]/div/div/div/div[2]/span")
    if custom_alert.count():
        return True

    if action_not_found_icon.count() and action_not_found_label.count():
        return True

    return False


def dismiss_error_dialog(page, path_label: str) -> None:
    def click_force(target):
        try:
            target.click(force=True, timeout=4000)
            target.click(force=True, timeout=4000)
            page.wait_for_timeout(600)
        except PlaywrightTimeoutError:
            logging.warning("Unable to dismiss error dialog for %s", path_label)

    # Dedicated handler for the Action Not Found popup.
    action_not_found_label = page.locator("[id^='x-auto-']").filter(
        has_text=re.compile(r"Action\s+Not\s+Found", re.IGNORECASE)
    ).first
    if action_not_found_label.count():
        try:
            action_dialog = action_not_found_label.locator(
                "xpath=ancestor::div[contains(@class,'x-window')][1]"
            )
            dialog_ok = action_dialog.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first
            if dialog_ok.count():
                click_force(dialog_ok)
                return
        except PlaywrightTimeoutError:
            logging.warning("Action Not Found dialog OK click timed out for %s", path_label)

    ok_targets = [
        page.locator("[id^='x-auto-'] button.x-btn-text").first,
        page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first,
        page.locator("//button[normalize-space()='OK']").first,
        page.get_by_role("button", name="OK"),
        page.locator("[id^='x-auto-'] tbody tr:nth-child(2) td.x-btn-mc em button").first,
        page.locator("[id^='x-auto-'] table tbody tr td table tbody tr td").first,
    ]

    ok_found = False
    for ok_target in ok_targets:
        if ok_target.count():
            click_force(ok_target)
            ok_found = True

    # If error popup and no OK button, click the close icon
    # Look for error header
    error_header = page.locator("span.x-panel-header-text").filter(has_text="Error").first
    if error_header.count():
        # Check if the error dialog footer contains an OK button
        error_dialog = error_header.locator("xpath=ancestor::div[contains(@class,'x-panel-header')]/following-sibling::div[contains(@class,'x-window-footer')]")
        ok_in_footer = error_dialog.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).count() if error_dialog.count() else 0
        if not ok_found and not ok_in_footer:
            # Try to click the close icon for the error dialog
            close_icon = error_header.locator("xpath=ancestor::div[contains(@class,'x-panel-header')]/descendant::div[contains(@class,'x-tool-close')]").first
            if close_icon.count():
                try:
                    close_icon.click(force=True, timeout=4000)
                    page.wait_for_timeout(600)
                except PlaywrightTimeoutError:
                    logging.warning("Failed to click error dialog close icon for %s", path_label)
            else:
                # Fallback: try global close targets
                close_targets = [
                    page.locator("a.x-tab-strip-close").first,
                    page.locator("button[aria-label='Close']").first,
                ]
                for close_target in close_targets:
                    if close_target.count():
                        try:
                            close_target.click(force=True, timeout=4000)
                        except PlaywrightTimeoutError:
                            logging.warning("Failed to click close target for %s", path_label)


def dismiss_informational_popup(page) -> bool:
    """Close informational popups (like 'Too much data') without treating as errors."""
    # Check for "Too much data" informational popup
    too_much_data_popup = page.locator("span.ext-mb-text").filter(has_text=TOO_MUCH_DATA_MESSAGE).first
    if too_much_data_popup.count():
        logging.info("Dismissing 'Too much data' informational popup")
        ok_targets = [
            page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first,
            page.locator("//button[normalize-space()='OK']").first,
            page.get_by_role("button", name="OK"),
        ]
        for ok_button in ok_targets:
            if ok_button.count():
                try:
                    ok_button.click(force=True, timeout=800)
                    page.wait_for_timeout(100)
                    logging.info("Successfully dismissed informational popup")
                    return True
                except (PlaywrightTimeoutError, PlaywrightError):
                    pass
        return False
    return False


def load_menu_paths(file_path: Path) -> List[List[str]]:
    if not file_path.exists():
        logging.warning("Menu path file %s not found", file_path)
        return []

    paths: List[List[str]] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            segments = [segment.strip() for segment in cleaned.split(">") if segment.strip()]
            if segments:
                paths.append(segments)

    logging.info("Loaded %d menu paths from %s", len(paths), file_path)
    return paths


def normalize_menu_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (value or "").strip().lower())
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def first_words_key(value: str, words_count: int = 3) -> str:
    words = normalize_menu_text(value).split()
    return " ".join(words[:words_count]) if words else ""


def labels_equal_normalized(candidate_text: str, target_label: str) -> bool:
    normalized_candidate = normalize_menu_text(candidate_text)
    normalized_target = normalize_menu_text(target_label)
    return bool(normalized_candidate and normalized_target and normalized_candidate == normalized_target)


def scroll_tree_area_into_view(page) -> None:
    tree_candidates = [
        page.locator("div[role='tree']").first,
        page.locator("div.x-tree-root-ct").first,
        page.locator("div.x-tree3").first,
    ]
    for tree in tree_candidates:
        try:
            if tree.count():
                tree.scroll_into_view_if_needed()
                return
        except PlaywrightError:
            continue


def scroll_tree_container_step(page, step_px: int = 320, settle_ms: int = 180) -> None:
    containers = [
        page.locator("div[role='tree']").first,
        page.locator("div.x-tree-root-ct").first,
        page.locator("div.x-tree3").first,
    ]
    for container in containers:
        try:
            if container.count():
                container.evaluate(
                    "([el, step]) => { el.scrollTop = Math.min(el.scrollHeight, el.scrollTop + step); }",
                    [step_px],
                )
                page.wait_for_timeout(settle_ms)
                return
        except PlaywrightError:
            continue

    try:
        page.mouse.wheel(0, step_px)
    except PlaywrightError:
        pass
    page.wait_for_timeout(settle_ms)


def find_tree_node(
    page,
    label: str,
    level: int,
    *,
    max_scroll_steps: int = 16,
    scroll_step_px: int = 320,
    settle_ms: int = 180,
):
    target_label = label.strip()

    # Fast pass before iterative scrolling.
    treeitems = page.locator(f"div[role=\"treeitem\"][aria-level=\"{level}\"]")
    try:
        initial_count = treeitems.count()
    except PlaywrightError:
        return page.locator("div[role=\"treeitem\"][aria-level=\"-1\"]").first

    for idx in range(initial_count):
        candidate = treeitems.nth(idx)
        try:
            if not candidate.is_visible():
                continue
            candidate_text = tree_node_label_text(candidate)
            if labels_equal_normalized(candidate_text, target_label):
                try:
                    candidate.scroll_into_view_if_needed()
                except PlaywrightError:
                    pass
                return candidate
        except Exception:
            continue

    for _ in range(max_scroll_steps):
        try:
            scroll_tree_area_into_view(page)
        except Exception:
            pass

        treeitems = page.locator(f"div[role=\"treeitem\"][aria-level=\"{level}\"]")
        try:
            current_count = treeitems.count()
        except PlaywrightError:
            return page.locator("div[role=\"treeitem\"][aria-level=\"-1\"]").first

        for idx in range(current_count):
            candidate = treeitems.nth(idx)
            try:
                if not candidate.is_visible():
                    continue
                candidate_text = tree_node_label_text(candidate)
                if labels_equal_normalized(candidate_text, target_label):
                    try:
                        candidate.scroll_into_view_if_needed()
                    except PlaywrightError:
                        pass
                    return candidate
            except Exception:
                continue

        scroll_tree_container_step(page, step_px=scroll_step_px, settle_ms=settle_ms)

    return page.locator("div[role=\"treeitem\"][aria-level=\"-1\"]").first


def wait_for_tree_level_items(page, level: int, timeout_ms: int = 1600) -> bool:
    deadline = time.time() + (timeout_ms / 1000.0)
    selector = f"div[role='treeitem'][aria-level='{level}']"
    while time.time() < deadline:
        try:
            if page.locator(selector).count() > 0:
                return True
        except PlaywrightError:
            pass
        page.wait_for_timeout(120)
    return False


def find_top_level_entry(page, top_level: str):
    pattern = re.compile(rf"^\s*{re.escape(top_level)}\s*$", re.IGNORECASE)
    candidates = [
        page.get_by_role("button", name=pattern).first,
        page.locator("button").filter(has_text=pattern).first,
        page.locator("a.x-tab-strip-text").filter(has_text=pattern).first,
        page.locator("div[role='treeitem'][aria-level='1']").filter(has_text=pattern).first,
    ]
    for candidate in candidates:
        try:
            if candidate.count() and labels_equal_normalized((candidate.inner_text() or "").strip(), top_level):
                return candidate
        except PlaywrightError:
            continue

    fallback_targets = [
        page.locator("button"),
        page.locator("a.x-tab-strip-text"),
        page.locator("div[role='treeitem'][aria-level='1']"),
    ]
    for target_group in fallback_targets:
        try:
            count = target_group.count()
        except PlaywrightError:
            continue
        for idx in range(count):
            candidate = target_group.nth(idx)
            try:
                if not candidate.is_visible():
                    continue
                text = (candidate.inner_text() or "").strip()
                if labels_equal_normalized(text, top_level):
                    return candidate
            except PlaywrightError:
                continue
    return None


def open_top_level_menu(page, top_level: str) -> bool:
    for _ in range(3):
        entry = find_top_level_entry(page, top_level)
        if entry is None:
            page.wait_for_timeout(500)
            continue
        try:
            entry.scroll_into_view_if_needed()
        except PlaywrightError:
            pass
        try:
            entry.click(force=True, timeout=5000)
            page.wait_for_timeout(400)
            return True
        except PlaywrightError as exc:
            if is_target_closed_error(exc):
                return False
            page.wait_for_timeout(500)
    return False


def click_view_context_option(page, module_name: str, path_label: str) -> bool:
    return click_context_menu_option(page, VIEW_OPTION_PATTERN, module_name, path_label)


def click_edit_context_option(page, module_name: str, path_label: str) -> bool:
    return click_context_menu_option(page, EDIT_OPTION_PATTERN, module_name, path_label)


def click_context_menu_option(page, pattern, module_name: str, path_label: str) -> bool:
    option = (
        page.locator(".x-menu-list .x-menu-item")
        .filter(has_text=pattern)
        .first
    )
    if not option.count():
        return False

    option.click(force=True, timeout=3500)
    handle_error_dialog(page, module_name, path_label)
    return True


def activate_row_checkbox(result_row, path_label: str):
    checkbox = result_row.locator("td.x-grid3-td-rowOperations input[type=checkbox]").first
    if not checkbox.count():
        return None

    try:
        checkbox.click(force=True, timeout=1000)
    except PlaywrightTimeoutError:
        logging.info("Inline checkbox click timed out for %s", path_label)
    return checkbox


def get_row_operations_target(result_row):
    cell = result_row.locator("td.x-grid3-td-rowOperations").first
    return cell if cell.count() else result_row


def result_grid_is_empty(page) -> bool:
    empty_grid = page.locator("div.x-grid3-scroller div.x-grid-empty")
    if empty_grid.count():
        return True

    empty_text = page.locator("div.x-grid-empty")
    return empty_text.count() > 0


def find_first_result_row(page):
    selectors = [
        "div.x-grid3-body div.x-grid3-row",
        "tr.x-grid3-row",
        "[id^='Component_PAGE_FORM_1_DataTable_'][id$='PalmyraGrid_0']",
        "[id^='Component_PAGE_FORM_1_DataTable_'][id*='PalmyraGrid_']",
        "[id$=PalmyraGrid_0]",
        GRID0_RIGHT_CLICK_SELECTOR,
        RESULT_ROW_TABLE_SELECTOR,
        RESULT_ROW_PREFIX_SELECTOR,
    ]
    for selector in selectors:
        candidates = page.locator(selector)
        count = candidates.count()
        for idx in range(count):
            candidate = candidates.nth(idx)
            try:
                if candidate.is_visible():
                    return candidate
            except PlaywrightError:
                continue
    return None


def wait_for_first_result_row(page, timeout_ms: int = 10000):
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        row = find_first_result_row(page)
        if row is not None:
            return row
        page.wait_for_timeout(300)
    return None


GRID0_RIGHT_CLICK_SELECTOR = "#Component_PAGE_FORM_1_DataTable_355_PalmyraGrid_x-auto-1432"
CLOSE_WORK_WINDOW_SELECTOR = "#x-auto-6__3 > a.x-tab-strip-close"


def close_work_window(page, path_label: str) -> None:
    close_targets = [
        page.locator(CLOSE_WORK_WINDOW_SELECTOR).first,
        page.locator("a.x-tab-strip-close").first,
        page.locator("div.x-tool-close").first,
        page.locator("button[aria-label='Close']").first,
    ]
    for target in close_targets:
        if not target.count():
            continue
        try:
            target.click(force=True, timeout=4000)
            page.wait_for_timeout(600)
            return
        except (PlaywrightTimeoutError, PlaywrightError):
            logging.info("Close candidate timed out for %s", path_label)


def capture_save_ok_screenshot(page, module_name: str, path_label: str) -> None:
    target_dir = get_process_rl_screenshot_dir(module_name, path_label)

    timestamp = int(time.time())
    filename = f"save_ok_{slugify(path_label)}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.info("Captured save OK screenshot for %s at %s", path_label, target)


def capture_execute_search_popup_screenshot(page, module_name: str, path_label: str) -> None:
    target_dir = get_process_rl_screenshot_dir(module_name, path_label)

    timestamp = int(time.time())
    filename = f"execute_search_popup_{slugify(path_label)}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.info("Captured Execute Search popup screenshot for %s at %s", path_label, target)


def open_first_row_context_menu(page, module_name: str, path_label: str):
    selectors = [
        GRID0_RIGHT_CLICK_SELECTOR,
        "[id^='Component_PAGE_FORM_1_DataTable_'][id$='PalmyraGrid_0']",
        "[id^='Component_PAGE_FORM_1_']",
        "[id$=PalmyraGrid_0]",
    ]
    result_row = None
    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=1500)
        except PlaywrightTimeoutError:
            continue

        candidate = page.locator(selector).first
        if candidate.count():
            result_row = candidate
            break

    if result_row is None:
        logging.warning("First grid row missing for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
        return None

    def context_menu_is_visible() -> bool:
        return page.locator(".x-menu-list:visible, .x-menu:visible").count() > 0

    def right_click_with_mouse(target) -> bool:
        try:
            target.scroll_into_view_if_needed()
        except PlaywrightError:
            pass

        try:
            target.click(button="right", timeout=1000)
            page.wait_for_timeout(200)
            if context_menu_is_visible():
                return True
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

        try:
            target.click(button="right", force=True, timeout=1000)
            page.wait_for_timeout(150)
            if context_menu_is_visible():
                return True
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

        try:
            box = target.bounding_box()
            if not box:
                return False
            page.mouse.click(
                box["x"] + max(box["width"] / 2, 5),
                box["y"] + max(box["height"] / 2, 5),
                button="right",
            )
            page.wait_for_timeout(200)
            if context_menu_is_visible():
                return True
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

        # Some ExtJS grids open context menu via keyboard on selected row.
        try:
            page.keyboard.press("Shift+F10")
            page.wait_for_timeout(500)
            return context_menu_is_visible()
        except (PlaywrightTimeoutError, PlaywrightError):
            return False

    right_clicked = False
    for attempt in range(2):
        try:
            result_row.scroll_into_view_if_needed()
            result_row.click(force=True, timeout=4000)
            page.wait_for_timeout(200)

            # Try row first because some menus are bound to row, not operations cell.
            right_clicked = right_click_with_mouse(result_row)
            if not right_clicked:
                operations_target = get_row_operations_target(result_row)
                if operations_target.count():
                    right_clicked = right_click_with_mouse(operations_target)

            if right_clicked:
                page.wait_for_timeout(500)
                break
        except (PlaywrightTimeoutError, PlaywrightError):
            logging.info("Right-click retry %d failed for %s", attempt + 1, path_label)

    if not right_clicked:
        logging.warning("Right-click failed for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
        return None

    menu_list = page.locator(".x-menu-list").first
    try:
        if menu_list.count():
            menu_list.wait_for(timeout=4000)
    except PlaywrightTimeoutError:
        logging.info("Context menu delayed for %s", path_label)

    return result_row


def context_menu_has_edit_option(page) -> bool:
    return page.locator(".x-menu-list .x-menu-item").filter(has_text=EDIT_OPTION_PATTERN).first.count() > 0


def run_view_edit_workflow(page, module_name: str, path_label: str) -> bool:
    # Step 1: right-click and verify edit availability.
    first_menu_row = open_first_row_context_menu(page, module_name, path_label)
    if first_menu_row is None:
        close_work_window(page, path_label)
        return False
    edit_seen_initially = context_menu_has_edit_option(page)
    logging.info("Edit option initially available for %s: %s", path_label, edit_seen_initially)
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    except Exception:
        pass

    # Step 2: right-click again and open View/Voir.
    view_menu_row = open_first_row_context_menu(page, module_name, path_label)
    if view_menu_row is None:
        close_work_window(page, path_label)
        return False
    if not click_view_context_option(page, module_name, path_label):
        logging.warning("View option not available for %s; closing window", path_label)
        close_work_window(page, path_label)
        return False

    handle_view_panel(page, module_name, path_label)

    # Step 3: right-click after return and open Edit if available, else close.
    edit_menu_row = open_first_row_context_menu(page, module_name, path_label)
    if edit_menu_row is None:
        close_work_window(page, path_label)
        return False

    if context_menu_has_edit_option(page) and click_edit_context_option(page, module_name, path_label):
        handle_edit_panel(page, module_name, path_label)
        return True
    else:
        logging.info("Edit option not available after return for %s; closing window", path_label)
        close_work_window(page, path_label)
        return False


def right_click_first_grid_row_after_view(page, module_name: str, path_label: str) -> None:
    result_row = page.locator("[id$=PalmyraGrid_0]").first
    if not result_row.count():
        logging.warning("First grid row missing after view for %s", path_label)
        capture_failure(page, module_name, path_label)
        raise PlaywrightTimeoutError("First grid row missing after view")

    try:
        result_row.wait_for(timeout=6000)
    except PlaywrightTimeoutError:
        logging.warning("First grid row not ready after view for %s", path_label)
        capture_failure(page, module_name, path_label)
        raise

    result_row.scroll_into_view_if_needed()
    result_row.click(force=True, timeout=4000)
    page.wait_for_timeout(200)

    operations_target = get_row_operations_target(result_row)
    def perform_right_click(target):
        try:
            target.click(button="right", force=True, timeout=4000)
            target.click(button="right", force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Right-click attempt failed on target for %s", path_label)

    if operations_target.count():
        try:
            operations_target.wait_for(timeout=4000)
            operations_target.scroll_into_view_if_needed()
            perform_right_click(operations_target)
        except PlaywrightTimeoutError:
            logging.info("Operations cell not ready; falling back to row right-click for %s", path_label)
            perform_right_click(result_row)
    else:
        logging.info("Operations cell missing, right-clicking row for %s", path_label)
        perform_right_click(result_row)
    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(800)

    menu_list = page.locator(".x-menu-list")
    if menu_list.count():
        try:
            menu_list.first.wait_for(timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Context menu delayed for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)

    # Always click 'Voir' first, then close the view tab
    if click_view_context_option(page, module_name, path_label):
        logging.info("Clicked 'Voir' for %s, will close the view tab.", path_label)
        page.wait_for_timeout(1200)
        close_button = page.locator("a.x-tab-strip-close")
        if close_button.count():
            try:
                close_button.first.click()
                page.wait_for_timeout(600)
            except Exception as exc:
                logging.warning("Failed to close view tab for %s: %s", path_label, exc)
    else:
        logging.info("'Voir' option not available for %s", path_label)

    # Right-click again for 'Editer'
    perform_right_click(operations_target if operations_target.count() else result_row)
    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(800)
    menu_list = page.locator(".x-menu-list")
    if menu_list.count():
        try:
            menu_list.first.wait_for(timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Context menu delayed for %s (second time)", path_label)
            capture_failure(page, module_name, path_label, always=True)

    if click_edit_context_option(page, module_name, path_label):
        handle_edit_panel(page, module_name, path_label)
    else:
        logging.info("Edit option not available for %s after viewing.", path_label)
        # Close the window/tab if 'Editer' is not available after viewing
        close_button = page.locator("a.x-tab-strip-close")
        if close_button.count():
            try:
                close_button.first.click()
                page.wait_for_timeout(600)
            except Exception as exc:
                logging.warning("Failed to close tab for %s after viewing: %s", path_label, exc)


def handle_error_dialog(page, module_name: str, path_label: str) -> bool:
    page.wait_for_timeout(600)
    if not failure_indicators_present(page):
        return False

    logging.warning("Detected error dialog for %s", path_label)
    capture_failure(page, module_name, path_label)
    return True


def wait_for_post_popup_settle(page, path_label: str, timeout_ms: int = 6000) -> None:
    blockers = [
        "div.x-mask:visible",
        "div.x-mask-msg:visible",
        "div.x-window-mask:visible",
        "div.x-mask-loading:visible",
    ]
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        blocked = False
        for selector in blockers:
            try:
                if page.locator(selector).count():
                    blocked = True
                    break
            except PlaywrightError:
                continue
        if not blocked:
            return
        page.wait_for_timeout(250)
    logging.info("UI overlay still visible after popup for %s; continuing", path_label)


def handle_execute_search_popup(page, module_name: str, path_label: str) -> bool:
    """Click OK inside the panel-fbar container shown after Execute Search."""
    def page_is_alive() -> bool:
        try:
            return page is not None and not page.is_closed()
        except Exception:
            return False

    def safe_count(locator) -> int:
        if not page_is_alive():
            return 0
        try:
            return locator.count()
        except PlaywrightError as exc:
            if is_target_closed_error(exc):
                return 0
            return 0

    def try_click(target) -> bool:
        if not page_is_alive():
            return False
        try:
            target.click(force=True, timeout=1500)
            page.wait_for_timeout(200)
            return True
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        try:
            target.evaluate("el => el.click()")
            page.wait_for_timeout(200)
            return True
        except (PlaywrightError, Exception):
            pass
        try:
            page.keyboard.press("Enter")
            page.wait_for_timeout(200)
            return True
        except (PlaywrightError, Exception):
            pass
        return False

    # Fast selector attempts - no waiting for invisible elements
    selectors = [
        ("[id^='x-auto-'] button.x-btn-text", "exact"),
        ("div.x-small-editor.x-panel-btns-center.x-panel-fbar.x-component.x-toolbar-layout-ct button.x-btn-text", "action_zone"),
        ("button.x-btn-text", "generic"),
    ]

    for selector, selector_type in selectors:
        try:
            page.wait_for_selector(selector, timeout=8000)
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

        ok_button = page.locator(selector).filter(has_text=OK_BUTTON_PATTERN).first
        if safe_count(ok_button):
            logging.warning("Execute Search popup %s OK button detected for %s", selector_type, path_label)
            # Don't capture screenshot if it's the "too much data" informational popup
            if not page.locator("span.ext-mb-text").filter(has_text=TOO_MUCH_DATA_MESSAGE).count():
                capture_execute_search_popup_screenshot(page, module_name, path_label)
            if try_click(ok_button):
                return True

    return False



def apply_position_field_filters(page, apply_basis: bool = True) -> None:
    try:
        date_input = page.locator(
            f"//label[normalize-space()='{POSITION_DATE_LABEL}']/ancestor::tr//td[contains(@class,'widget')]//input[contains(@class,'x-form-field')]"
        ).first
        if date_input.count():
            date_input.fill(POSITION_DATE_VALUE)
            logging.info("Set %s to %s", POSITION_DATE_LABEL, POSITION_DATE_VALUE)

        if not apply_basis:
            return

        basis_row = page.locator(f"xpath=//label[normalize-space()='{POSITION_BASIS_LABEL}']/ancestor::tr").first
        if not basis_row.count():
            logging.info("%s row missing", POSITION_BASIS_LABEL)
            return
        basis_arrow = basis_row.locator("xpath=.//img[contains(@class,'x-form-trigger-arrow')]").first
        if basis_arrow.count():
            try:
                basis_arrow.click(force=True, timeout=3000)
                option = page.locator("//div[contains(@class,'x-boundlist')]//div[contains(@class,'x-boundlist-item')]").filter(
                    has_text=re.compile(POSITION_BASIS_VALUE, re.IGNORECASE)
                ).first
                if option.count():
                    option.click(force=True, timeout=4000)
                else:
                    logging.info("No bound list option matched %s", POSITION_BASIS_VALUE)
            except PlaywrightTimeoutError:
                logging.info("Basis dropdown interaction timed out")
        basis_input = basis_row.locator("xpath=.//input[@name='Component_PAGE_FORM_0_atomicCriteria_positionBasis_criteria']").first
        if basis_input.count():
            basis_input.fill(POSITION_BASIS_VALUE)
            logging.info("Filled %s with %s", POSITION_BASIS_LABEL, POSITION_BASIS_VALUE)
    except PlaywrightTimeoutError:
        logging.warning("Position field filtering timed out")


def ensure_client_sec_account_selected(page, module_name: str, path_label: str) -> None:
    field = page.locator(CLIENT_SEC_ACCOUNT_FIELD_SELECTOR)
    if not field.count():
        logging.info("Client Sec Account field not present for %s", path_label)
        return

    input_field = field.locator(CLIENT_SEC_ACCOUNT_INPUT_SELECTOR).first
    if not input_field.count():
        logging.info("Client Sec Account input not found for %s", path_label)
        return

    try:
        input_field.click(force=True, timeout=4000)
        page.wait_for_timeout(400)
        page.keyboard.press("F2")
        try:
            page.wait_for_selector(CLIENT_SEC_ACCOUNT_GRID_CELL_SELECTOR, timeout=6000)
        except PlaywrightTimeoutError:
            logging.warning("Client Sec Account lookup grid missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return

        grid_cell = page.locator(CLIENT_SEC_ACCOUNT_GRID_CELL_SELECTOR).first
        if not grid_cell.count():
            logging.warning("Client Sec Account lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label, always=True)
            return

        try:
            grid_cell.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Client Sec Account row double-click timed out for %s", path_label)
            grid_cell.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Client Sec Account lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)


def handle_view_panel(page, module_name: str, path_label: str) -> None:
    page.wait_for_timeout(1200)
    return_button = page.locator(VIEW_RETURN_SELECTOR)
    if not return_button.count():
        return

    try:
        return_button.first.click(force=True, timeout=4000)
        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Unable to close view panel for %s", path_label)


def try_edit_from_view(page, module_name: str, path_label: str) -> bool:
    edit_icon = page.locator("#Component_PAGE_FORM_2_edit_null").first
    if not edit_icon.count():
        logging.info("View edit icon not present for %s", path_label)
        return False

    try:
        edit_icon.click(force=True, timeout=4000)
    except PlaywrightTimeoutError:
        logging.warning("Edit icon click timed out for %s", path_label)
        capture_failure(page, module_name, path_label)
        return False

    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(600)
    handle_edit_panel(page, module_name, path_label)
    return True


def handle_edit_panel(page, module_name: str, path_label: str) -> None:
    page.wait_for_timeout(800)
    save_button = page.locator(SAVE_BUTTON_SELECTOR).first
    if not save_button.count():
        logging.warning("Save button not found for %s", path_label)
        capture_failure(page, module_name, path_label)
        close_work_window(page, path_label)
        return


    # Special workflow for advanced position menu
    advanced_position_path = (
        "position",
        "titres",
        "gestion de la position client",
        "consultation avancee des positions",
    )
    # If the current path matches the advanced position menu, ensure client sec account is selected
    if tuple(segment.strip().lower() for segment in path_label.split(">")) == advanced_position_path:
        ensure_client_sec_account_selected(page, module_name, path_label)

    try:
        save_button.click(force=True, timeout=4000)
        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Saving failed for %s", path_label)
        capture_failure(page, module_name, path_label)
        close_work_window(page, path_label)
        return

    # After save: click any OK button found, take a screenshot before click, then close window.
    ok_candidates = [
        page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first,
        page.locator("//button[normalize-space()='OK']").first,
        page.get_by_role("button", name="OK"),
    ]
    ok_clicked = False
    for ok_button in ok_candidates:
        if not ok_button.count():
            continue
        try:
            capture_save_ok_screenshot(page, module_name, path_label)
            ok_button.click(force=True, timeout=4000)
            page.wait_for_timeout(600)
            ok_clicked = True
            break
        except PlaywrightTimeoutError:
            logging.info("OK button click timed out for %s", path_label)

    if not ok_clicked:
        logging.warning("No clickable OK button detected after save for %s", path_label)
        capture_failure(page, module_name, path_label)

    close_work_window(page, path_label)


def _find_first_visible(page, selectors: List[str]):
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() and locator.is_visible():
            return locator
    return None


def _submit_credentials(page) -> bool:
    username_input = _find_first_visible(
        page,
        ["#username", "input[name='username']", "input[name='j_username']"],
    )
    password_input = _find_first_visible(
        page,
        ["#password", "input[name='password']", "input[name='j_password']"],
    )

    if username_input is None or password_input is None:
        logging.error("Unable to find username/password inputs on login page.")
        return False

    username_input.fill(AUTH_USERNAME)
    password_input.fill(AUTH_PASSWORD)

    domain_field = _find_first_visible(
        page,
        [
            "input[name='j_asp']",
            "#domain",
            "select[name='domain']",
            "form select",
            "xpath=/html/body/div[1]/div[2]/div/div/form/div[4]/select",
            "input[name='domain']",
            "input[id*='domain']",
        ],
    )
    if domain_field is not None and AUTH_DOMAIN:
        domain_key = AUTH_DOMAIN.strip().lower()
        domain_key_alt = domain_key.replace("_", " ")
        domain_candidates = [
            AUTH_DOMAIN,
            AUTH_DOMAIN.replace("_", " "),
            "CDG_CAPITAL",
            "CDG CAPITAL",
            "CDG",
        ]
        # Keep order, remove empty and duplicates
        seen_candidates = set()
        domain_candidates = [
            c for c in domain_candidates if c and not (c in seen_candidates or seen_candidates.add(c))
        ]
        selected = False

        try:
            tag_name = (domain_field.evaluate("el => el.tagName") or "").lower()
        except Exception:
            tag_name = ""

        if tag_name == "select":
            try:
                # Always force click to open the select dropdown
                domain_field.click(force=True, timeout=3000)
            except Exception:
                pass
            try:
                # Always try to select 'CDG CAPITAL' by value if present
                domain_field.select_option(value="CDG CAPITAL")
                selected = True
            except Exception:
                # Fallback to previous candidate logic if needed
                for candidate in domain_candidates:
                    if selected:
                        break
                    try:
                        domain_field.select_option(label=candidate)
                        selected = True
                        break
                    except Exception:
                        pass
                    try:
                        domain_field.select_option(value=candidate)
                        selected = True
                        break
                    except Exception:
                        pass
            if not selected:
                try:
                    options = domain_field.locator("option")
                    for idx in range(options.count()):
                        option = options.nth(idx)
                        option_label = (option.inner_text() or "").strip()
                        option_value = (option.get_attribute("value") or "").strip()
                        if option_value == "CDG CAPITAL":
                            domain_field.select_option(value=option_value)
                            selected = True
                            break
                        if option_label == "CDG CAPITAL":
                            domain_field.select_option(label=option_label)
                            selected = True
                            break
                except PlaywrightTimeoutError:
                    logging.debug("Domain options loading timed out for %s", AUTH_DOMAIN)
        else:
            try:
                domain_field.click(force=True, timeout=4000)
                domain_field.fill(AUTH_DOMAIN)
                page.wait_for_timeout(200)

                # AWB login uses a plain input (j_asp), so a simple fill + tab is expected.
                if domain_field.get_attribute("name") == "j_asp":
                    page.keyboard.press("Tab")
                    selected = True
                else:
                    suggestion = (
                        page.locator("//div[contains(@class,'x-boundlist-item') or contains(@class,'x-combo-list-item')]")
                        .filter(has_text=re.compile(re.escape(AUTH_DOMAIN), re.IGNORECASE))
                        .first
                    )
                    if suggestion.count():
                        suggestion.click(force=True, timeout=3000)
                    else:
                        page.keyboard.press("Tab")
                    selected = True
            except PlaywrightTimeoutError:
                logging.debug("Domain input interaction timed out for %s", AUTH_DOMAIN)

        if selected:
            logging.info("Selected domain using candidates: %s", ", ".join(domain_candidates))
        else:
            logging.warning("Domain %s not found in login form options", AUTH_DOMAIN)

    # Priority path for your Keycloak page submit control.
    submit_exact = page.locator("xpath=/html/body/div[1]/div[2]/div/div/form/input").first
    if submit_exact.count():
        try:
            submit_exact.click(force=True, timeout=15000)
            return True
        except PlaywrightTimeoutError:
            logging.warning("Exact submit XPath found but not clickable.")

    submit = page.locator(
        "#kc-login, "
        "button[name='login'], "
        "input[name='login'], "
        "button[type=submit], "
        "input[type=submit], "
        "input.pf-c-button.pf-m-primary.btn-lg[type='submit'][value='Submit'], "
        "button:has-text('Log in'), "
        "button:has-text('Sign in'), "
        "button:has-text('Connexion'), "
        "button:has-text('Se connecter')"
    )
    if submit.count():
        try:
            submit.first.wait_for(state="visible", timeout=15000)
            try:
                enabled = submit.first.is_enabled()
            except Exception:
                enabled = True
            if not enabled:
                logging.warning("Submit button is visible but reported disabled; trying force click.")
                submit.first.click(force=True)
            else:
                submit.first.click()
            return True
        except PlaywrightTimeoutError:
            logging.error("Submit button found but not clickable after waiting.")
            return False

    role_candidates = [
        page.get_by_role("button", name=re.compile(r"submit", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"log\s*in|sign\s*in", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"connexion|se\s*connecter", re.IGNORECASE)),
    ]
    for submit_by_role in role_candidates:
        if submit_by_role.count():
            try:
                target = submit_by_role.first
                target.wait_for(state="visible", timeout=15000)
                if not target.is_enabled():
                    continue
                target.click()
                return True
            except PlaywrightTimeoutError:
                continue

    # Final fallback for forms without explicit submit button selectors
    try:
        password_input.press("Enter")
        page.wait_for_timeout(700)
        return True
    except Exception:
        pass

    # Try to double-click any visible submit button forcibly as a last resort
    try:
        submit_any = page.locator("button[type=submit], input[type=submit]").filter(has="visible").first
        if submit_any.count():
            submit_any.dblclick(force=True, timeout=5000)
            page.wait_for_timeout(700)
            logging.warning("Double-clicked submit button forcibly as last resort.")
            return True
    except Exception:
        pass

    logging.error("No submit button found on login page.")
    return False


def get_alive_page(page):
    """Return the current page if alive, otherwise the latest alive page in the same context."""
    try:
        if page and not page.is_closed():
            return page
    except Exception:
        pass

    try:
        context = page.context
        for candidate in reversed(context.pages):
            try:
                if not candidate.is_closed():
                    return candidate
            except Exception:
                continue
    except Exception:
        pass

    return page


def is_target_closed_error(exc: Exception) -> bool:
    return "Target page, context or browser has been closed" in str(exc)


def ensure_alive_page(page):
    alive_page = get_alive_page(page)
    try:
        if alive_page and not alive_page.is_closed():
            return alive_page
    except Exception:
        pass
    return None


def find_megacommon_page(context, fallback_page=None):
    pages = []
    try:
        pages = list(context.pages)
    except Exception:
        pages = []

    for candidate in reversed(pages):
        try:
            if candidate.is_closed():
                continue
            url = (candidate.url or "").lower()
            if "megacommon" in url:
                return candidate
        except Exception:
            continue

    return ensure_alive_page(fallback_page)


def app_shell_visible(page) -> bool:
    app_ready = (
        "div[role='treeitem'], "
        "button:has-text('Position'), "
        "button:has-text('Referentiel'), "
        "a.x-tab-strip-text"
    )
    try:
        return page.locator(app_ready).count() > 0
    except PlaywrightError:
        return False


def refresh_and_relogin_if_needed(page, entry_url: str) -> Optional[object]:
    page = ensure_alive_page(page)
    if page is None:
        return None

    logging.info("Refreshing custody page after Saisie Instruction Client")
    try:
        page.reload(wait_until="domcontentloaded", timeout=45000)
    except (PlaywrightTimeoutError, PlaywrightError) as exc:
        logging.warning("Custody refresh failed or timed out, trying conditional relogin: %s", exc)

    page = ensure_alive_page(page)
    if page is None:
        return None

    if app_shell_visible(page):
        logging.info("Custody app shell still visible after refresh; relogin not required")
        return page

    logging.info("Custody app shell not visible after refresh; attempting relogin")
    if login(page, entry_url):
        return ensure_alive_page(page)

    logging.error("Conditional relogin failed after custody refresh")
    return None


def login(page, entry_url: Optional[str] = None) -> bool:
    login_url = entry_url or LOGIN_ENTRY
    logging.info("Navigating to login entry point")
    page.goto(login_url, wait_until="domcontentloaded")

    app_ready = (
        "div[role='treeitem'], "
        "button:has-text('Position'), "
        "button:has-text('Referentiel'), "
        "a.x-tab-strip-text"
    )

    def detect_login_or_app(timeout_ms: int = 30000) -> str:
        deadline = time.time() + (timeout_ms / 1000.0)
        while time.time() < deadline:
            try:
                if page.locator(app_ready).count():
                    return "app"
            except Exception as exc:
                if is_target_closed_error(exc):
                    return "none"
                pass
            try:
                if page.locator("#username, input[name='username'], input[name='j_username']").count():
                    return "login"
            except Exception as exc:
                if is_target_closed_error(exc):
                    return "none"
                pass
            try:
                page.wait_for_timeout(300)
            except Exception as exc:
                if is_target_closed_error(exc):
                    return "none"
                return "none"
        return "none"

    if AUTH_TYPE == "keycloak":
        keycloak_link = page.locator("a#social-internal-keycloak-oidc-link").first
        if keycloak_link.count():
            try:
                keycloak_link.click(timeout=15000)
            except PlaywrightTimeoutError:
                logging.error("Keycloak entry link is present but not clickable.")
                return False
        else:
            logging.warning("Keycloak link not found, trying direct credential form.")

    login_state = detect_login_or_app(timeout_ms=35000)
    if login_state == "app":
        logging.info("App shell detected without login form (already authenticated or SSO handoff complete).")
        return True
    if login_state != "login":
        logging.error("Login form was not displayed in time for auth type %s.", AUTH_TYPE)
        return False

    transform_checkbox = page.locator("#userTransform")
    if transform_checkbox.count() and transform_checkbox.is_visible():
        try:
            if transform_checkbox.is_checked():
                transform_checkbox.uncheck()
                logging.info("Unchecked userTransform checkbox")
        except PlaywrightTimeoutError:
            logging.debug("userTransform checkbox not ready for interaction")

    if not _submit_credentials(page):
        return False

    # Keycloak can close the original tab/page and continue on a new one.
    page = get_alive_page(page)

    # Some environments keep background network traffic alive, so `networkidle`
    # is unreliable for login success detection.
    try:
        page.wait_for_selector(app_ready, timeout=45000)
    except PlaywrightTimeoutError:
        # Fallback: if login form disappeared, continue and let menu traversal validate.
        login_still_visible = page.locator("#username, input[name='username'], input[name='j_username']").count()
        if login_still_visible:
            logging.error("Login form is still visible after submit.")
            return False
    except Exception as exc:
        # Avoid hard failure when Playwright raises TargetClosedError after auth redirect.
        if "Target page, context or browser has been closed" in str(exc):
            page = get_alive_page(page)
            try:
                page.wait_for_selector(app_ready, timeout=45000)
            except Exception as retry_exc:
                logging.error("Login page handoff failed after redirect: %s", retry_exc)
                return False
        else:
            logging.error("Unexpected login error: %s", exc)
            return False

    logging.info("Login submitted (auth=%s, module=%s)", AUTH_TYPE, login_url)
    return True


def traverse_tree(page, module_name: str) -> None:
    logging.info("Traversing module %s", module_name)
    nodes = page.locator("div[role=treeitem][aria-level=\"2\"]")
    count = nodes.count()
    logging.info("Found %d tree nodes", count)

    for idx in range(count):
        node = nodes.nth(idx)
        label = node.locator(".x-tree3-node-text")
        node_text = label.inner_text().strip()
        if not node_text:
            continue

        logging.info("Opening node %s", node_text)
        try:
            node.dblclick(timeout=5000)
        except PlaywrightTimeoutError:
            logging.info("Double click timed out for %s, falling back to single click", node_text)
            node.click()

        page.wait_for_timeout(1500)
        table = page.locator("table.x-form-search")

        if table.count():
            logging.info("Detected expected search table for %s", node_text)
        else:
            capture_failure(page, module_name, node_text)

        close_button = page.locator("a.x-tab-strip-close")
        if close_button.count():
            close_button.first.click()
            page.wait_for_timeout(600)


def process_menu(page) -> None:
    for menu_label in MENU_TABS:
        button = page.get_by_role("button", name=menu_label)
        if not button.count():
            logging.warning("Menu button %s not found", menu_label)
            continue

        button.click()
        logging.info("Clicked %s", menu_label)
        page.wait_for_timeout(1200)
        traverse_tree(page, menu_label)


def build_parent_prefixes(paths: List[List[str]]) -> set[tuple[str, ...]]:
    prefixes: set[tuple[str, ...]] = set()
    for path in paths:
        for depth in range(1, len(path)):
            prefixes.add(tuple(path[:depth]))
    return prefixes


def has_future_path_with_prefix(
    menu_paths: List[List[str]], current_index: int, prefix: tuple[str, ...]
) -> bool:
    for future_path in menu_paths[current_index + 1 :]:
        if len(future_path) < len(prefix):
            continue
        if tuple(future_path[: len(prefix)]) == prefix:
            return True
    return False


def collapse_unused_ancestors(
    page,
    menu_paths: List[List[str]],
    current_index: int,
    path: List[str],
    expanded_nodes: set[tuple[str, ...]],
) -> None:
    for depth in range(len(path) - 1, 1, -1):
        prefix = tuple(path[:depth])
        if prefix not in expanded_nodes:
            continue
        if has_future_path_with_prefix(menu_paths, current_index, prefix):
            continue

        ancestor_label = path[depth - 1]
        ancestor_node = find_tree_node(page, ancestor_label, depth)
        if not ancestor_node.count():
            continue

        try:
            ancestor_node.dblclick(force=True, timeout=4000)
            page.wait_for_timeout(800)
            expanded_nodes.discard(prefix)
        except PlaywrightTimeoutError:
            logging.info("Could not collapse ancestor %s", ancestor_label)


def traverse_menu_paths(page, menu_paths: List[List[str]]) -> None:
    if not menu_paths:
        logging.warning("No menu paths supplied")
        return

    parent_prefixes = build_parent_prefixes(menu_paths)
    expanded_nodes: set[tuple[str, ...]] = set()
    total_paths = len(menu_paths)
    for index, path in enumerate(menu_paths):
        page = ensure_alive_page(page)
        if page is None:
            logging.error("No alive page available during menu traversal; stopping.")
            return

        if len(path) < 2:
            logging.warning("Skipping short path %s", path)
            continue

        top_level = path[0]
        if not open_top_level_menu(page, top_level):
            logging.warning("Top level menu %s not opened", top_level)
            page = ensure_alive_page(page)
            if page is None:
                return
            continue

        path_label = " > ".join(path)
        normalized_path = tuple(segment.strip().lower() for segment in path)
        is_saisie_path = is_saisie_instruction_client_path(normalized_path)
        logging.info("Traversing path %d/%d: %s", index + 1, total_paths, path_label)
        position_filter_mode = get_position_filter_mode(path)
        page.wait_for_timeout(1200)

        # --- Menu-specific workflows ---
        if normalized_path == MARCHE_TRANSFER_PATH or normalized_path == MARCHE_CONSULTATION_PATH:
            if position_filter_mode:
                apply_position_field_filters(
                    page,
                    apply_basis=position_filter_mode.get("basis", True),
                )
            handle_error_dialog(page, top_level, path_label)
        elif normalized_path == MARCHE_SUSPENS_PATH:
            fill_marche_suspens_date(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
        elif normalized_path == (
            "position",
            "titres",
            "gestion de la position marche",
            "position marche disponible",
        ):
            ensure_owner_selected(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
            ensure_tradable_asset_selected(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
            select_position_control_context(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
        elif normalized_path == (
            "position",
            "titres",
            "gestion de la position marche",
            "position marche detaillee par periode",
        ):
            ensure_periode_owner_selected(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
            ensure_periode_tradable_asset_selected(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
            fill_periode_date_from(page, top_level, path_label)
            handle_error_dialog(page, top_level, path_label)
        elif normalized_path == (
            "position",
            "titres",
            "gestion de la position marche",
            "position marche disponible par actif",
        ):
            input_field = page.locator("input[name='Component_PAGE_FORM_0_tradableAsset']").first
            if input_field.count():
                try:
                    input_field.click(force=True, timeout=4000)
                    input_field.fill("MA00020")
                    page.wait_for_timeout(400)
                    page.keyboard.press("F2")
                    try:
                        page.wait_for_selector("tr[id^='Component_PAGE_FORM_1_DataTable_']", timeout=6000)
                        grid_row = page.locator("tr[id^='Component_PAGE_FORM_1_DataTable_']").first
                        if grid_row.count():
                            try:
                                grid_row.dblclick(force=True, timeout=4000)
                            except PlaywrightTimeoutError:
                                grid_row.click(force=True, timeout=4000)
                            page.wait_for_timeout(600)
                    except PlaywrightTimeoutError:
                        logging.warning("Marche Disponible Par Actif Tradable Asset lookup grid missing for %s", path_label)
                        capture_failure(page, top_level, path_label, always=True)
                except PlaywrightTimeoutError:
                    logging.warning("Marche Disponible Par Actif Tradable Asset lookup interaction timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("Marche Disponible Par Actif Tradable Asset input not found for %s", path_label)
            dropdown = page.locator("#Component_PAGE_FORM_0_securityContext img.x-form-trigger-arrow").first
            if dropdown.count():
                try:
                    dropdown.click(force=True, timeout=4000)
                    page.wait_for_timeout(400)
                    option = page.locator("//div[contains(@class,'x-boundlist-item') and contains(text(),'PositionControlContext')]").first
                    if option.count():
                        option.click(force=True, timeout=4000)
                        page.wait_for_timeout(600)
                except PlaywrightTimeoutError:
                    logging.warning("PositionControlContext dropdown interaction timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("PositionControlContext dropdown not found for %s", path_label)
            handle_error_dialog(page, top_level, path_label)
        elif normalized_path == (
            "position",
            "titres",
            "impact manuel de la position",
        ):
            # 1. Client Sec Account: fill 14, F2, double click first row
            input_field = page.locator("input[name='Component_PAGE_FORM_0_clientSecAccount']").first
            if input_field.count():
                try:
                    input_field.click(force=True, timeout=4000)
                    input_field.fill("14")
                    page.wait_for_timeout(400)
                    page.keyboard.press("F2")
                    try:
                        page.wait_for_selector("td.x-grid3-col-client", timeout=6000)
                        grid_cell = page.locator("td.x-grid3-col-client").first
                        if grid_cell.count():
                            try:
                                grid_cell.dblclick(force=True, timeout=4000)
                            except PlaywrightTimeoutError:
                                grid_cell.click(force=True, timeout=4000)
                            page.wait_for_timeout(600)
                            page.keyboard.press("Tab")
                    except PlaywrightTimeoutError:
                        logging.warning("Impact Manuel Client Sec Account lookup grid missing for %s", path_label)
                        capture_failure(page, top_level, path_label, always=True)
                except PlaywrightTimeoutError:
                    logging.warning("Impact Manuel Client Sec Account lookup interaction timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("Impact Manuel Client Sec Account input not found for %s", path_label)
            # 2. Nostro Sec Account: F2, double click first row, tab
            nostro_input = page.locator("input[name='Component_PAGE_FORM_0_nostroSecAccount']").first
            if nostro_input.count():
                try:
                    nostro_input.click(force=True, timeout=4000)
                    page.keyboard.press("F2")
                    try:
                        page.wait_for_selector("tr[id^='Component_PAGE_FORM_1_DataTable_']", timeout=6000)
                        grid_row = page.locator("tr[id^='Component_PAGE_FORM_1_DataTable_']").first
                        if grid_row.count():
                            try:
                                grid_row.dblclick(force=True, timeout=4000)
                            except PlaywrightTimeoutError:
                                grid_row.click(force=True, timeout=4000)
                            page.wait_for_timeout(600)
                            page.keyboard.press("Tab")
                    except PlaywrightTimeoutError:
                        logging.warning("Impact Manuel Nostro Sec Account lookup grid missing for %s", path_label)
                        capture_failure(page, top_level, path_label, always=True)
                except PlaywrightTimeoutError:
                    logging.warning("Impact Manuel Nostro Sec Account lookup interaction timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("Impact Manuel Nostro Sec Account input not found for %s", path_label)
            # 3. Tradable Asset: fill MA0002, F2, double click first row, tab
            tradable_input = page.locator("input[name='Component_PAGE_FORM_0_tradableAsset']").first
            if tradable_input.count():
                try:
                    tradable_input.click(force=True, timeout=4000)
                    tradable_input.fill("MA0002")
                    page.wait_for_timeout(400)
                    page.keyboard.press("F2")
                    try:
                        page.wait_for_selector("tr[id^='Component_PAGE_FORM_1_DataTable_']", timeout=6000)
                        grid_row = page.locator("tr[id^='Component_PAGE_FORM_1_DataTable_']").first
                        if grid_row.count():
                            try:
                                grid_row.dblclick(force=True, timeout=4000)
                            except PlaywrightTimeoutError:
                                grid_row.click(force=True, timeout=4000)
                            page.wait_for_timeout(600)
                            page.keyboard.press("Tab")
                    except PlaywrightTimeoutError:
                        logging.warning("Impact Manuel Tradable Asset lookup grid missing for %s", path_label)
                        capture_failure(page, top_level, path_label, always=True)
                except PlaywrightTimeoutError:
                    logging.warning("Impact Manuel Tradable Asset lookup interaction timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("Impact Manuel Tradable Asset input not found for %s", path_label)
            # 4. Event: open dropdown, select Receive
            event_dropdown = page.locator("#Component_PAGE_FORM_0_event img.x-form-trigger-arrow").first
            if event_dropdown.count():
                try:
                    event_dropdown.click(force=True, timeout=4000)
                    page.wait_for_timeout(400)
                    option = page.locator("//div[contains(@class,'x-boundlist-item') and contains(text(),'Receive')]").first
                    if option.count():
                        option.click(force=True, timeout=4000)
                        page.wait_for_timeout(600)
                except PlaywrightTimeoutError:
                    logging.warning("Impact Manuel Event dropdown interaction timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("Impact Manuel Event dropdown not found for %s", path_label)
            # 5. Quantity: fill 1000
            quantity_input = page.locator("input[name='Component_PAGE_FORM_0_quantity']").first
            if quantity_input.count():
                try:
                    quantity_input.click(force=True, timeout=4000)
                    quantity_input.fill("1000")
                    page.wait_for_timeout(400)
                except PlaywrightTimeoutError:
                    logging.warning("Impact Manuel Quantity fill timed out for %s", path_label)
                    capture_failure(page, top_level, path_label, always=True)
            else:
                logging.info("Impact Manuel Quantity input not found for %s", path_label)
            # 6. Validate Impact: double click button
            validate_btn = page.locator("button.x-btn-text", has_text="Validate Impact").first
            if validate_btn.count():
                try:
                    validate_btn.dblclick(force=True, timeout=4000)
                except PlaywrightTimeoutError:
                    validate_btn.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
            else:
                logging.info("Impact Manuel Validate Impact button not found for %s", path_label)
            handle_error_dialog(page, top_level, path_label)
        elif is_saisie_path:
            pass
        # Always check for max screens popup after each node interaction
        handle_max_screens_popup(page)

        # Now traverse the tree nodes for this path
        for child_index, segment in enumerate(path[1:], start=1):
            page = ensure_alive_page(page)
            if page is None:
                logging.error("No alive page while traversing %s; aborting traversal.", path_label)
                return

            # Ensure menu area is in view before resolving every path segment.
            scroll_tree_area_into_view(page)

            level = child_index + 1
            prefix = tuple(path[: child_index + 1])
            node_is_leaf = prefix not in parent_prefixes
            node = find_tree_node(page, segment, level)
            try:
                if not node.count():
                    # Retry a few times because tree content can load lazily after tab click.
                    found = False
                    for _ in range(4):
                        page.wait_for_timeout(500)
                        node = find_tree_node(page, segment, level)
                        if node.count():
                            found = True
                            break
                    if not found:
                        logging.warning("Tree node %s at level %s not found", segment, level)
                        break
            except PlaywrightError as exc:
                if is_target_closed_error(exc):
                    logging.warning("Page closed while checking node %s at level %s", segment, level)
                    break
                raise

            try:
                node.scroll_into_view_if_needed()
            except PlaywrightError as exc:
                if is_target_closed_error(exc):
                    logging.warning("Page closed while scrolling node %s", segment)
                    break
                logging.warning("Could not scroll node %s into view: %s", segment, exc)
                node = find_tree_node(page, segment, level)
                try:
                    if not node.count():
                        logging.warning("Tree node %s at level %s became unavailable", segment, level)
                        break
                except PlaywrightError as retry_exc:
                    if is_target_closed_error(retry_exc):
                        logging.warning("Page closed while re-checking node %s", segment)
                        break
                    raise
            already_expanded = prefix in expanded_nodes
            try:
                scroll_tree_area_into_view(page)
                try:
                    node.scroll_into_view_if_needed()
                except PlaywrightError:
                    pass
                if node_is_leaf:
                    node.click(force=True, timeout=4000)
                else:
                    # Keep already-expanded ancestors open (ex: Instructions Marche between
                    # Appariement and Denouement) to avoid collapsing on a second double-click.
                    if already_expanded:
                        node.click(force=True, timeout=4000)
                    else:
                        node.dblclick(force=True, timeout=5000)
                        expanded_nodes.add(prefix)
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                logging.info("Failed to interact with %s, trying fallback click: %s", segment, exc)
                node = find_tree_node(page, segment, level)
                try:
                    if not node.count():
                        logging.warning("Tree node %s at level %s unavailable during fallback", segment, level)
                        break
                except PlaywrightError as retry_exc:
                    if is_target_closed_error(retry_exc):
                        logging.warning("Page closed during fallback re-check for node %s", segment)
                        break
                    raise
                try:
                    if node_is_leaf:
                        node.click(force=True, timeout=4000)
                    else:
                        if already_expanded:
                            node.click(force=True, timeout=4000)
                        else:
                            node.dblclick(force=True, timeout=5000)
                            expanded_nodes.add(prefix)
                except (PlaywrightTimeoutError, PlaywrightError) as fallback_exc:
                    logging.warning("Fallback interaction failed for %s: %s", segment, fallback_exc)
                    capture_failure(page, top_level, path_label, always=True)
                    break
            finally:
                handle_error_dialog(page, top_level, path_label)

            page.wait_for_timeout(1500)

            if node_is_leaf:
                table = page.locator("table.x-form-search")
                if table.count():
                    table_root = table.first
                    result_row = table_root.locator("tbody tr").first
                    if result_row.count():
                        try:
                            result_row.scroll_into_view_if_needed()
                            result_row.click(force=True, timeout=4000)
                            handle_error_dialog(page, top_level, path_label)

                            execute_button = page.locator(EXECUTE_CRITERIA_SELECTOR)
                            if execute_button.count():
                                if normalized_path == ADVANCED_POSITION_PATH:
                                    ensure_client_sec_account_selected(page, top_level, path_label)
                                    handle_error_dialog(page, top_level, path_label)
                                elif normalized_path == POSITION_DISPONIBLE_PATH:
                                    # 1. Owner selection
                                    ensure_owner_selected(page, top_level, path_label)
                                    handle_error_dialog(page, top_level, path_label)
                                    # 2. Tradable asset selection (fill MA0002, F2, double-click first row)
                                    tradable_input = page.locator("input[name='Component_PAGE_FORM_0_tradableAsset']").first
                                    if tradable_input.count():
                                        try:
                                            tradable_input.click(force=True, timeout=4000)
                                            tradable_input.fill("MA0002")
                                            page.wait_for_timeout(400)
                                            page.keyboard.press("F2")
                                            try:
                                                page.wait_for_selector("tr[id^='Component_PAGE_FORM_1_DataTable_']", timeout=6000)
                                                grid_row = page.locator("tr[id^='Component_PAGE_FORM_1_DataTable_']").first
                                                if grid_row.count():
                                                    try:
                                                        grid_row.dblclick(force=True, timeout=4000)
                                                    except PlaywrightTimeoutError:
                                                        grid_row.click(force=True, timeout=4000)
                                                    page.wait_for_timeout(600)
                                            except PlaywrightTimeoutError:
                                                logging.warning("Tradable Asset lookup grid missing for %s", path_label)
                                                capture_failure(page, top_level, path_label, always=True)
                                        except PlaywrightTimeoutError:
                                            logging.warning("Tradable Asset lookup interaction timed out for %s", path_label)
                                            capture_failure(page, top_level, path_label, always=True)
                                    else:
                                        logging.info("Tradable Asset input not found for %s", path_label)
                                    handle_error_dialog(page, top_level, path_label)
                                    # 3. Position control context (security context dropdown)
                                    dropdown_arrow = page.locator("#Component_PAGE_FORM_0_securityContext img.x-form-trigger-arrow").first
                                    if dropdown_arrow.count():
                                        try:
                                            dropdown_arrow.click(force=True, timeout=4000)
                                            page.wait_for_timeout(400)
                                            option = page.locator("//div[contains(@class,'x-boundlist-item') and contains(text(),'PositionControlContext')]").first
                                            if option.count():
                                                option.click(force=True, timeout=4000)
                                                page.wait_for_timeout(600)
                                        except PlaywrightTimeoutError:
                                            logging.warning("PositionControlContext dropdown interaction timed out for %s", path_label)
                                            capture_failure(page, top_level, path_label, always=True)
                                    else:
                                        logging.info("PositionControlContext dropdown not found for %s", path_label)
                                    handle_error_dialog(page, top_level, path_label)
                                elif normalized_path == POSITION_DETAILLEE_PERIODE_PATH:
                                    ensure_periode_owner_selected(page, top_level, path_label)
                                    handle_error_dialog(page, top_level, path_label)
                                if position_filter_mode:
                                    apply_position_field_filters(
                                        page,
                                        apply_basis=position_filter_mode.get("basis", True),
                                    )
                                try:
                                    execute_button.first.dblclick(force=True, timeout=4000)
                                except PlaywrightTimeoutError:
                                    execute_button.first.click(force=True, timeout=4000)
                                popup_handled = handle_execute_search_popup(page, top_level, path_label)
                                # Dismiss any informational popups that are not errors
                                dismiss_informational_popup(page)
                                if not popup_handled:
                                    handle_error_dialog(page, top_level, path_label)
                                if popup_handled:
                                    try:
                                        page.wait_for_selector(
                                            "div.x-grid3-row, [id^='Component_PAGE_FORM_1_DataTable_'][id$='PalmyraGrid_0'], [id$='PalmyraGrid_0']",
                                            timeout=600,
                                        )
                                    except PlaywrightTimeoutError:
                                        pass
                                    popup_result_row = find_first_result_row(page)
                                    if popup_result_row is not None:
                                        activate_row_checkbox(popup_result_row, path_label)
                                        run_view_edit_workflow(page, top_level, path_label)
                                        close_work_window(page, path_label)
                                        collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                        continue
                                page.wait_for_timeout(200)
                                try:
                                    page.wait_for_selector("div.x-grid3-row", timeout=2000)
                                except PlaywrightTimeoutError:
                                    logging.warning(
                                        "Grid rows did not appear after execute for %s",
                                        path_label,
                                    )
                                header_locator = (
                                    page.locator("div.x-panel-header-text")
                                    .filter(has_text="de la recherche")
                                    .last
                                )
                                if header_locator.count():
                                    header_locator.scroll_into_view_if_needed()
                                else:
                                    logging.warning(
                                        "Search header missing for %s", path_label
                                    )
                                viewport_locators = page.locator("div.x-grid3-viewport")
                                viewport_count = viewport_locators.count()
                                if viewport_count:
                                    target_index = max(viewport_count - 2, 0)
                                    viewport_locators.nth(target_index).scroll_into_view_if_needed()
                                else:
                                    logging.warning(
                                        "Grid viewport missing for %s", path_label
                                    )
                                if result_grid_is_empty(page):
                                    logging.info(
                                        "Execute search returned an empty grid for %s; closing window",
                                        path_label,
                                    )
                                    close_work_window(page, path_label)
                                    collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                    continue
                                if not page.locator(RESULT_ROW_PREFIX_SELECTOR).count():
                                    logging.info(
                                        "Component_PAGE_FORM_1 not found for %s; continuing with row-based selectors",
                                        path_label,
                                    )
                                table_root = page.locator("table.x-form-search").first
                                result_row = find_first_result_row(page)
                                if result_row is None:
                                    logging.info(
                                        "Execute search returned no usable row for %s; closing window",
                                        path_label,
                                    )
                                    close_work_window(page, path_label)
                                    collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                    continue
                                try:
                                    result_row.wait_for(timeout=1000)
                                except PlaywrightTimeoutError:
                                    logging.info(
                                        "First result row not ready for %s; closing window",
                                        path_label,
                                    )
                                    close_work_window(page, path_label)
                                    collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                    continue

                                if normalized_path == INSTRUCTIONS_MARCHE_APPARIEMENT_PATH:
                                    run_market_result_action_workflow(
                                        page,
                                        top_level,
                                        path_label,
                                        "Match",
                                        "/html/body/div[2]/div/div[3]/div[2]/div[3]/div[2]/div[1]/div/table/tbody/tr/td[4]/table/tbody/tr[2]/td[2]/em/button",
                                    )
                                    close_work_window(page, path_label)
                                    collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                    continue

                                if normalized_path == INSTRUCTIONS_MARCHE_DENOUEMENT_PATH:
                                    run_market_result_action_workflow(
                                        page,
                                        top_level,
                                        path_label,
                                        "Settle",
                                        "/html/body/div[2]/div/div[3]/div[2]/div[4]/div[2]/div[1]/div/table/tbody/tr/td[1]/table/tbody/tr[2]/td[2]/em/button",
                                    )
                                    close_work_window(page, path_label)
                                    collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                    continue
                            else:
                                # Si le menu est ouvert mais qu'il n'y a pas de bouton de recherche/execute, fermer proprement
                                logging.info("No execute button found for %s; closing tab", path_label)
                                close_active_tab_and_others(page)
                                close_button = page.locator("a.x-tab-strip-close")
                                if close_button.count():
                                    try:
                                        close_button.first.click(force=True, timeout=4000)
                                        page.wait_for_timeout(600)
                                    except PlaywrightTimeoutError:
                                        logging.warning("Failed to close tab for %s", path_label)
                                collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                                continue

                            activate_row_checkbox(result_row, path_label)
                            run_view_edit_workflow(page, top_level, path_label)
                        except (PlaywrightTimeoutError, PlaywrightError) as exc:
                            logging.warning("Context menu interaction failed for %s: %s", path_label, exc)
                            if is_target_closed_error(exc):
                                logging.warning("Page/context closed while handling %s; stopping traversal", path_label)
                                return
                            capture_failure(page, top_level, path_label, always=True)
                    else:
                        logging.warning("No result rows found for %s", path_label)
                        capture_failure(page, top_level, path_label)
                else:
                    capture_failure(page, top_level, path_label)

                if is_saisie_path:
                    fill_saisie_instruction_client_form(page, top_level, path_label)

                close_button = page.locator("a.x-tab-strip-close")
                try:
                    if close_button.count():
                        close_button.first.click(force=True, timeout=4000)
                        page.wait_for_timeout(600)
                except PlaywrightTimeoutError:
                    logging.warning("Timed out while closing tab for %s", path_label)
                except PlaywrightError as exc:
                    if is_target_closed_error(exc):
                        logging.info("Tab already closed for %s", path_label)
                    else:
                        logging.warning("Non-fatal tab close error for %s: %s", path_label, exc)

                if is_saisie_path:
                    page = refresh_and_relogin_if_needed(page, LOGIN_ENTRY)
                    if page is None:
                        logging.error("Custody page is not available after refresh/relogin step")
                        return

def main() -> None:
    menu_paths = load_menu_paths(MENU_PATH_FILE)
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
            pre_criteria = load_pre_consultation_values()

            # Step A (before process): MegaCommon consultation setup.
            if not login(common_page, MEGACOMMON_ENTRY):
                logging.error("MegaCommon login failed, stopping execution.")
                return
            common_page = get_alive_page(common_page)
            if common_page.is_closed():
                logging.error("No alive MegaCommon page available after login.")
                return
            if not execute_megacommon_consultation(common_page, pre_criteria):
                logging.error("MegaCommon pre-consultation execute search failed; stopping before custody process.")
                return
            view_first_result_and_screenshot_position(common_page, "pre_denouement")

            # Step B: open a new custody tab and run Process RL.
            custody_page = context.new_page()
            if not login(custody_page, LOGIN_ENTRY):
                logging.error("Custody login failed, stopping execution.")
                return
            custody_page = get_alive_page(custody_page)
            if custody_page.is_closed():
                logging.error("No alive custody page available after login.")
                return

            if menu_paths:
                traverse_menu_paths(custody_page, menu_paths)
                logging.info("Custody traversal completed; returning to MegaCommon for final execute")
            else:
                logging.error("No menu paths loaded from %s; strict ordered execution requires the txt file.", MENU_PATH_FILE)
                return

            # Step C (after process): return to MegaCommon and execute final search.
            common_page = find_megacommon_page(context, common_page)
            if common_page and not common_page.is_closed():
                try:
                    common_page.bring_to_front()
                except Exception:
                    pass

                try:
                    logging.info("Refreshing MegaCommon page before post-denouement consultation")
                    common_page.reload(wait_until="domcontentloaded", timeout=30000)
                    common_page.wait_for_timeout(1500)
                    try:
                        login_visible = common_page.locator(
                            "#username, input[name='username'], input[name='j_username']"
                        ).first.is_visible()
                    except (PlaywrightTimeoutError, PlaywrightError):
                        login_visible = False
                    if login_visible:
                        logging.info("Reload landed on login form; re-authenticating MegaCommon")
                        if not login(common_page, MEGACOMMON_ENTRY):
                            logging.error("Re-authentication after reload failed; aborting post-denouement flow")
                            return
                        common_page = ensure_alive_page(common_page)
                        if common_page is None:
                            logging.error("No alive MegaCommon page after reload re-authentication")
                            return
                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    logging.warning("MegaCommon page reload failed (%s); continuing", exc)

                if not app_shell_visible(common_page):
                    logging.info("MegaCommon app shell not visible at final step; attempting relogin")
                    if not login(common_page, MEGACOMMON_ENTRY):
                        logging.error("Final MegaCommon relogin failed; cannot execute final search")
                        return
                    common_page = ensure_alive_page(common_page)
                    if common_page is None:
                        logging.error("No alive MegaCommon page after final relogin")
                        return

                execute_ok = execute_megacommon_consultation(common_page, pre_criteria)
                if execute_ok:
                    logging.info("Final MegaCommon execute completed")
                    view_first_result_and_screenshot_position(common_page, "post_denouement")
                else:
                    logging.error("Final MegaCommon execute failed")
            else:
                logging.warning("MegaCommon tab not available for final consultation execution")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
