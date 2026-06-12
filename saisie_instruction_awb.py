# Imports
import logging
import os
import random
import re
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import playwright
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

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
MARCHE_SUSPENS_DATE_INPUT_SELECTOR = "input#x-auto-46301-input"
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


def dismiss_help_description_popup_if_present(page) -> bool:
    popup_candidates = [
        page.locator("div.x-window-plain.x-window-dlg.x-window.x-component").filter(has_text=re.compile(r"Help Description|EditClientInstruction", re.IGNORECASE)).first,
        page.locator("span.x-window-header-text").filter(has_text=re.compile(r"Help Description", re.IGNORECASE)).first,
        page.locator("div.x-window-header-text").filter(has_text=re.compile(r"Help Description", re.IGNORECASE)).first,
    ]

    for popup in popup_candidates:
        if not popup.count():
            continue

        close_targets = [
            popup.locator("div.x-tool-close").first,
            popup.locator("button[aria-label='Close']").first,
            popup.locator("button.x-btn-text", has_text=re.compile(r"^Close$|^Fermer$", re.IGNORECASE)).first,
        ]
        for target in close_targets:
            if not target.count():
                continue
            try:
                target.click(force=True, timeout=2000)
                page.wait_for_timeout(200)
                logging.info("Closed Help Description popup.")
                return True
            except PlaywrightTimeoutError:
                continue

        try:
            popup.evaluate("node => node.remove()")
            logging.info("Removed Help Description popup from DOM.")
            return True
        except Exception:
            continue

    return False


def _retry_after_help_popup(page, module_name: str, path_label: str, reason: str) -> bool:
    dismissed = dismiss_help_description_popup_if_present(page)
    if dismissed:
        logging.info("Retrying %s after closing Help Description popup for %s", reason, path_label)
        page.wait_for_timeout(400)
        return True
    return False
# --- Position Detaillée Par Période Tradable Asset and Date From selectors/workflow ---
PERIODE_TRADABLE_ASSET_FIELD_SELECTOR = "#Field_ComponenttradableAsset"
PERIODE_TRADABLE_ASSET_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_tradableAsset']"
PERIODE_TRADABLE_ASSET_GRID_ROW_SELECTOR = "tr[id^='Component_PAGE_FORM_1_DataTable_']"
PERIODE_TRADABLE_ASSET_VALUE = "MA0002"
PERIODE_DATE_FROM_INPUT_SELECTOR = "input#x-auto-38291-input"
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
POSITION_CONTROL_CONTEXT_DROPDOWN_SELECTOR = "#x-auto-31499"
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

LOGIN_ENTRY = os.getenv("MODULE_URL", "http://10.1.140.244:9082/MegaCustody/login.jsp")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/AWB/common/saisie.txt"))
SAISIE_VARIABLES_FILE = Path(os.getenv("SAISIE_VARIABLES_FILE", "variable_saisies/Instruction_Client_awb.txt"))
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "migration")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Vermeg+123")
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "awb")
AUTH_TYPE = os.getenv("AUTH_TYPE", "standard").strip().lower()

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
EDIT_OPTION_PATTERN = re.compile(r"(?:edit|editer)", re.IGNORECASE)
TOO_MUCH_DATA_PATTERN = re.compile(r"toomuchdatafound", re.IGNORECASE)
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
AWB_SEARCH_BUTTON_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[1]/div[1]/div/table/tbody/tr/td[3]/div"
AWB_SEARCH_VIEW_CONTAINER_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[2]/div[2]/div[1]/div/div/div[2]/div[1]/div"
AWB_FIRST_ROW_JS_CSS = "#Component_PAGE_FORM_1_DataTable_138_PalmyraGrid_x-auto-815"
AWB_RESULT_ROW_DYNAMIC_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div[15]/div[2]/div[2]/div[1]/div/div/div[2]/div[1]/div/div[1]/div[1]/div[2]/div/div[1]"
AWB_RESULT_ROW_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[2]/div[2]/div[1]/div/div/div[2]/div[1]/div/div[1]/div[1]/div[2]/div/div[1]/table/tbody/tr"
AWB_RESULT_ROW_AFTER_EXECUTE_XPATH = "//*[@id='Component_PAGE_FORM_1_DataTable_138_PalmyraGrid_0']"
AWB_FIRST_CELL_XPATH = "//*[@id='x-auto-817']/div"
AWB_VIEW_OPTION_XPATH = "/html/body/div[10]/div/div/a"
AWB_EDIT_OPTION_XPATH = "/html/body/div[10]/div/div[2]/a"
AWB_TOO_MUCH_DATA_XPATH = "/html/body/div[10]/div[2]/div[1]/div/div/div/div[2]/span"
AWB_RETURN_AFTER_VIEW_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[3]/div[1]/div/table/tbody/tr/td[2]/div"
AWB_CLOSE_TAB_AFTER_VIEW_XPATH = "/html/body/div[2]/div/div[3]/div[1]/div[1]/ul/li[1]/a[1]"
VIEW_RETURN_SELECTOR = "#Component_PAGE_FORM_2_return_null"
SAVE_BUTTON_SELECTOR = "#Component_PAGE_FORM_2_save_null"
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
LOGIN_NAVIGATION_MAX_ATTEMPTS = int(os.getenv("LOGIN_NAVIGATION_MAX_ATTEMPTS", "3"))
LOGIN_NAVIGATION_TIMEOUT_MS = int(os.getenv("LOGIN_NAVIGATION_TIMEOUT_MS", "30000"))
LOGIN_NAVIGATION_RETRY_DELAY_MS = int(os.getenv("LOGIN_NAVIGATION_RETRY_DELAY_MS", "2500"))

SAISIE_INSTRUCTION_CLIENT_PATH = (
    "règlement/livraison",
    "instructions clients",
    "saisie instruction client",
)
SAISIE_FIELD_SPECS: List[Dict[str, str]] = [
    {
        "key": "otc_traded",
        "label": "OTC TRADED",
        "selector": "input[name='Component_PAGE_FORM_0_oTCTraded'], #x-auto-638-input, #x-auto-4095-input",
    },
    {
        "key": "client_reference",
        "label": "Client Reference",
        "selector": "input[name='Component_PAGE_FORM_0_clientReference'], #x-auto-4099-input",
    },
    {
        "key": "transaction_type",
        "label": "Transaction Type",
        "selector": "#Component_PAGE_FORM_0_transactionType input[id^='x-auto-'][id$='-input'], #Component_PAGE_FORM_0_transactionType input, input[name='Component_PAGE_FORM_0_transactionType'], input[name='transactionType'], xpath=//div[contains(@id,'transactionType')]//input",
    },
    {
        "key": "tradable_asset",
        "label": "Tradable Asset",
        "selector": "input[name='Component_PAGE_FORM_0_tradableAsset'], #x-auto-5204-input, xpath=//div[contains(@id,'tradableAsset')]//input",
    },
    {
        "key": "incoming_quantity",
        "label": "Incoming Quantity",
        "selector": "input[name='Component_PAGE_FORM_0_incomingQuantity'], #x-auto-5027-input",
    },
    {
        "key": "devise_denouement",
        "label": "Devise Denouement",
        "selector": "input[name='Component_PAGE_FORM_0_settlementCurrency'], input[name='settlementCurrency']",
    },
    {
        "key": "client_sec_account",
        "label": "Client Sec Account",
        "selector": "input[name='Component_PAGE_FORM_0_clientSecAccount'], #x-auto-5829-input",
    },
    {
        "key": "nostro_sec_account",
        "label": "Nostro Sec Account",
        "selector": "input[name='Component_PAGE_FORM_0_nostroSecAccount'], #x-auto-3296-input, #x-auto-2314-input",
    },
    {
        "key": "counterpart",
        "label": "Counterpart",
        "selector": "input[name='Component_PAGE_FORM_0_counterpart'], #x-auto-6356-input",
    },
    {
        "key": "beneficiary",
        "label": "Beneficiary",
        "selector": "input[name='Component_PAGE_FORM_0_beneficiary'], #x-auto-9807-input",
    },
    {
        "key": "compte_titres_beneficiaire",
        "label": "Compte Titres Bénéficiaire",
        "selector": "input[name='Component_PAGE_FORM_0_beneficiarySecAccount'], #x-auto-701-input, xpath=//*[@id='x-auto-701-input'], xpath=//*[@id='Component_PAGE_FORM_0_beneficiarySecAccount']//input",
    },
    {
        "key": "trade_date",
        "label": "Trade Date",
        "selector": "#x-auto-706-input, xpath=//*[@id='x-auto-706-input'], xpath=//*[@id='Component_PAGE_FORM_0_tradeDate']//input, input[name='Component_PAGE_FORM_0_tradeDate']",
    },
    {
        "key": "settlement_date",
        "label": "Settlement Date",
        "selector": "input[name='Component_PAGE_FORM_0_settlementDate'], input[name='settlementDate'], #x-auto-710-input, #x-auto-711-input, xpath=//*[@id='Component_PAGE_FORM_0_settlementDate']//input",
    },
    {
        "key": "price",
        "label": "Price",
        "selector": "#x-auto-715-input, xpath=//*[@id='x-auto-715-input'], xpath=//*[@id='Component_PAGE_FORM_0_price']//input, input[name='Component_PAGE_FORM_0_price']",
    },
    {
        "key": "negociated_rate",
        "label": "Negociated Rate",
        "selector": "#x-auto-826-input, xpath=//*[@id='x-auto-826-input'], xpath=//*[@id='Component_PAGE_FORM_0_negociatedRate']//input, input[name='Component_PAGE_FORM_0_negociatedRate']",
    },
]

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def ensure_playwright_node_path() -> None:
    """Avoid Windows cmd parsing issues when workspace path contains '&'."""
    if os.name != "nt":
        return

    if os.getenv("PLAYWRIGHT_NODEJS_PATH"):
        return

    driver_node = Path(playwright.__file__).resolve().parent / "driver" / "node.exe"
    if not driver_node.exists():
        logging.warning("Playwright node executable not found at %s", driver_node)
        return

    os.environ["PLAYWRIGHT_NODEJS_PATH"] = str(driver_node)
    logging.info("Configured PLAYWRIGHT_NODEJS_PATH for Playwright startup.")


def slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    return cleaned.strip("_").lower() or "node"


def _normalize_menu_segments(path: List[str]) -> Tuple[str, ...]:
    return tuple(segment.strip().lower() for segment in path)


def _normalize_lookup_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("/", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().lower()


def _tree_label_candidates(label: str) -> List[str]:
    candidates = [label]
    normalized = _normalize_lookup_text(label)
    if normalized == "instructions clients marche local":
        candidates.append("Instructions Clients")
    return candidates


def _first_words(value: str, count: int = 3) -> str:
    words = _normalize_lookup_text(value).split()
    return " ".join(words[:count])


def _is_current_module(module_name: str) -> bool:
    current_module_name = _normalize_lookup_text(os.getenv("MENU_CATEGORY_SLUG", ""))
    return current_module_name == _normalize_lookup_text(module_name)


def load_or_initialize_saisie_variables(file_path: Path) -> Dict[str, str]:
    defaults = {spec["key"]: "" for spec in SAISIE_FIELD_SPECS}
    values = defaults.copy()

    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                cleaned = line.strip()
                if not cleaned or cleaned.startswith("#") or "=" not in cleaned:
                    continue
                key, raw_value = cleaned.split("=", 1)
                key = key.strip()
                if key in values:
                    values[key] = raw_value.strip()
    else:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as fh:
        fh.write("# Valeurs modifiables pour le menu Saisie Instruction Client\n")
        for spec in SAISIE_FIELD_SPECS:
            key = spec["key"]
            fh.write(f"{key}={values.get(key, '')}\n")

    logging.info("Loaded saisie variables from %s", file_path)
    return values


def logout_to_login_page(page, module_name: str, path_label: str) -> bool:
    logout_candidates = [
        page.locator("#x-auto-57").first,
        page.locator("xpath=//*[@id='x-auto-57']").first,
        page.locator("xpath=/html/body/div[2]/div/div[1]/div[2]/div[1]/table/tbody/tr[1]/td/div/table/tbody/tr/td[4]/div").first,
    ]

    for target in logout_candidates:
        if not target.count():
            continue
        try:
            target.click(force=True, timeout=4000)
            page.wait_for_timeout(1200)
            try:
                page.wait_for_selector("#username, input[name='username'], input[name='j_username']", timeout=15000)
            except PlaywrightTimeoutError:
                logging.warning("Login form did not reappear after logout for %s", path_label)
            logging.info("Clicked logout before switching credentials for %s", path_label)
            return True
        except PlaywrightTimeoutError:
            logging.warning("Logout button present but not clickable for %s", path_label)
            return False

    logging.info("Logout button not found for %s", path_label)
    return False


def fill_saisie_instruction_client_form(page, module_name: str, path_label: str) -> bool:
    values = load_or_initialize_saisie_variables(SAISIE_VARIABLES_FILE)

    if not values.get("settlement_date", "").strip() and values.get("trade_date", "").strip():
        values["settlement_date"] = values.get("trade_date", "").strip()
        logging.info(
            "Settlement Date not provided; using Trade Date value '%s'",
            values["settlement_date"],
        )

    def _split_selectors(selector: str) -> List[str]:
        return [part.strip() for part in re.split(r",\s*", selector) if part.strip()]

    def _find_field(label: str, selector: str):
        normalized_label = re.sub(r"\s+", " ", label.strip().lower())
        selectors = _split_selectors(selector)
        if normalized_label in {"otc traded", "o tc traded"}:
            selectors = [
                "input[id^='x-auto-'][id$='-input'][name='Component_PAGE_FORM_0_oTCTraded']",
                "#Component_PAGE_FORM_0_oTCTraded input[id^='x-auto-'][id$='-input']",
                "#Component_PAGE_FORM_0_oTCTraded input",
                "input[name='Component_PAGE_FORM_0_oTCTraded']",
                "#x-auto-638-input",
                "#x-auto-4095-input",
            ] + selectors
        if normalized_label == "transaction type":
            selectors = [
                "#Component_PAGE_FORM_0_transactionType input[id^='x-auto-'][id$='-input']",
                "#Component_PAGE_FORM_0_transactionType input",
                "#x-auto-855-input",
                "input[name='Component_PAGE_FORM_0_transactionType']",
                "input[name='transactionType']",
                "input#x-auto-6227-input",
                "div#x-auto-6227 input",
                "xpath=/html/body/div[2]/div/div[3]/div[2]/div[5]/div/div[2]/div[1]/table/tbody/tr[1]/td/fieldset/div/div/table/tbody/tr[1]/td[4]/div/div[2]/div/div/input",
            ]
        if normalized_label == "settlement date":
            selectors = [
                "input[name='Component_PAGE_FORM_0_settlementDate']",
                "input[name='settlementDate']",
                "#Component_PAGE_FORM_0_settlementDate input[id^='x-auto-'][id$='-input']",
                "#Component_PAGE_FORM_0_settlementDate input",
                "#x-auto-710-input",
                "#x-auto-711-input",
            ] + selectors
        for _ in range(12):
            for sel in selectors:
                try:
                    field = page.locator(sel).first
                except Exception:
                    continue
                if field.count():
                    return field
            page.wait_for_timeout(250)
        return None

    def _safe_tab_to_target(
        target_selector: str,
        max_tabs: int = 12,
        current_field = None,
        expected_value: Optional[str] = None,
        label: Optional[str] = None,
        previous_fields: Optional[list[dict]] = None,
    ) -> bool:
        if not target_selector:
            return False

        selectors = _split_selectors(target_selector)
        target = None
        for sel in selectors:
            try:
                candidate = page.locator(sel).first
            except Exception:
                continue
            if candidate.count():
                target = candidate
                break

        def _restore_field_value(target_field, value_to_set: str) -> None:
            try:
                target_field.evaluate(
                    "(el, value) => { el.focus(); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); el.dispatchEvent(new Event('blur', { bubbles: true })); }",
                    value_to_set,
                )
                return
            except Exception:
                pass
            try:
                target_field.click(force=True, timeout=3000)
                target_field.fill(value_to_set)
                target_field.evaluate(
                    "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); el.dispatchEvent(new Event('blur', { bubbles: true })); }"
                )
                return
            except Exception:
                pass

        previous_fields = previous_fields or []
        restore_attempts = {
            "current": 0,
            "previous": [0] * len(previous_fields),
        }

        if target and target.count():
            try:
                target.scroll_into_view_if_needed()
                target.click(force=True, timeout=3000)
                page.wait_for_timeout(180)
                try:
                    if target.evaluate("el => el === document.activeElement"):
                        return True
                except Exception:
                    pass
            except Exception:
                pass

        if current_field is not None and current_field.count():
            try:
                current_field.focus()
            except Exception:
                pass

        def _validate_and_restore(target_field, expected, field_label, attempt_key):
            if expected is None or target_field is None or not target_field.count():
                return
            try:
                current_value = target_field.input_value().strip()
            except Exception:
                try:
                    current_value = target_field.evaluate("el => el.value").strip()
                except Exception:
                    current_value = None
            if current_value != expected and restore_attempts[attempt_key] < 2:
                logging.warning(
                    "Tabbing cleared value '%s' on field '%s'; restoring before continuing",
                    expected,
                    field_label or "current field",
                )
                try:
                    _restore_field_value(target_field, expected)
                except Exception:
                    pass
                restore_attempts[attempt_key] += 1

        def _validate_and_restore_previous():
            for idx, prev in enumerate(previous_fields):
                target_field = prev.get("field")
                expected = prev.get("expected")
                field_label = prev.get("label")
                if expected is None or target_field is None or not target_field.count():
                    continue
                try:
                    current_value = target_field.input_value().strip()
                except Exception:
                    try:
                        current_value = target_field.evaluate("el => el.value").strip()
                    except Exception:
                        current_value = None
                if current_value != expected and restore_attempts["previous"][idx] < 2:
                    logging.warning(
                        "Tabbing cleared value '%s' on field '%s'; restoring before continuing",
                        expected,
                        field_label or f"previous field {idx}",
                    )
                    try:
                        _restore_field_value(target_field, expected)
                    except Exception:
                        pass
                    restore_attempts["previous"][idx] += 1

        for _ in range(max_tabs):
            _validate_and_restore(current_field, expected_value, label, "current")
            _validate_and_restore_previous()

            if target and target.count():
                try:
                    if target.evaluate("el => el === document.activeElement"):
                        return True
                except Exception:
                    pass
            if current_field is not None and current_field.count():
                try:
                    current_field.focus()
                except Exception:
                    pass
            try:
                page.keyboard.press("Tab")
            except Exception:
                pass
            page.wait_for_timeout(180)

            _validate_and_restore(current_field, expected_value, label, "current")
            _validate_and_restore_previous()

            if target and target.count():
                try:
                    if target.evaluate("el => el === document.activeElement"):
                        return True
                except Exception:
                    pass
        if target and target.count():
            try:
                target.click(force=True, timeout=3000)
                return True
            except Exception:
                pass
        return False

    def _manual_type_field(
        field,
        value: str,
        label: str,
        next_target_selector: Optional[str] = None,
        previous_fields: Optional[list[dict]] = None,
    ) -> None:
        post_commit_wait_ms = 1200

        def _wait_field_idle(target_field, timeout_ms: int = 2200) -> None:
            deadline = time.time() + (timeout_ms / 1000)
            previous_value = None
            stable_reads = 0
            while time.time() < deadline:
                try:
                    current_value = target_field.input_value().strip()
                except Exception:
                    try:
                        current_value = target_field.evaluate("el => (el.value || '').trim()")
                    except Exception:
                        current_value = ""
                if current_value == previous_value:
                    stable_reads += 1
                else:
                    stable_reads = 0
                previous_value = current_value
                if stable_reads >= 2:
                    return
                page.wait_for_timeout(120)

        if label.strip().lower() == "price":
            _wait_field_idle(field)

        field.scroll_into_view_if_needed()
        field.click(force=True, timeout=4000)

        def _get_field_value(target_field):
            try:
                return target_field.input_value().strip()
            except Exception:
                try:
                    return target_field.evaluate("el => el.value").strip()
                except Exception:
                    return ""

        def _set_field_value(target_field, value_to_set: str) -> bool:
            try:
                target_field.evaluate(
                    "(el, value) => { el.focus(); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
                    value_to_set,
                )
                return True
            except Exception:
                pass
            try:
                target_field.fill(value_to_set)
                return True
            except Exception:
                pass
            try:
                target_field.fill("")
            except Exception:
                pass
            for char in value_to_set:
                try:
                    target_field.type(char, delay=80)
                except Exception:
                    pass
            return False

        def _commit_field(target_field):
            try:
                target_field.focus()
            except Exception:
                pass
            try:
                target_field.evaluate(
                    "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); el.blur(); }"
                )
                return True
            except Exception:
                try:
                    target_field.evaluate(
                        "el => { el.blur(); el.dispatchEvent(new Event('blur', { bubbles: true })); }"
                    )
                except Exception:
                    pass
                return False

        def _restore_transaction_type_if_needed():
            if label.strip().lower() not in {"tradable asset", "client sec account"} or not previous_fields:
                return
            for prev in previous_fields:
                if prev.get("label", "").strip().lower() == "transaction type":
                    expected = prev.get("expected")
                    tx_field = prev.get("field")
                    if not expected or tx_field is None or not tx_field.count():
                        return
                    try:
                        current_tx = _get_field_value(tx_field)
                    except Exception:
                        current_tx = ""
                    if current_tx != expected:
                        logging.warning(
                            "Transaction Type cleared after %s selection; re-entering '%s'",
                            label,
                            expected,
                        )
                        _set_field_value(tx_field, expected)
                        page.wait_for_timeout(400)
                        _commit_field(tx_field)
                        page.wait_for_timeout(1200)
                        current_tx = _get_field_value(tx_field)
                        logging.info("Transaction Type after reentry: '%s'", current_tx)
                        if current_tx != expected:
                            logging.warning(
                                "Transaction Type still incorrect after reentry: expected='%s' actual='%s'",
                                expected,
                                current_tx,
                            )
                    return

        def _handle_tradable_asset(target_field, value_to_set: str) -> bool:
            if label != "Tradable Asset" or not value_to_set:
                return False
            try:
                target_field.click(force=True, timeout=4000)
                target_field.fill(value_to_set)
                page.wait_for_timeout(400)
                target_field.evaluate(
                    "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); el.blur(); }"
                )
                page.wait_for_timeout(400)
                return True
            except Exception as exc:
                logging.info("Manual Tradable Asset selection failed for '%s': %s", label, exc)
            return False

        def _select_transaction_type_option(target_field, value_to_set: str) -> bool:
            if label.strip().lower() != "transaction type" or not value_to_set:
                return False

            trigger_selectors = [
                "xpath=ancestor::div[contains(@class,'x-form-field-wrap')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
                "xpath=ancestor::div[contains(@class,'x-form-element')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
                "xpath=../img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
            ]
            trigger = None
            for selector in trigger_selectors:
                try:
                    candidate = target_field.locator(selector).first
                except Exception:
                    continue
                if candidate.count():
                    trigger = candidate
                    break

            if trigger is None or not trigger.count():
                return False

            try:
                trigger.scroll_into_view_if_needed()
                trigger.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
            except Exception as exc:
                logging.info("Transaction Type dropdown trigger click failed: %s", exc)
                return False

            option = None
            option_selectors = [
                "div.x-boundlist div.x-boundlist-item",
                "div.x-boundlist-item",
                "li.x-boundlist-item",
                "div.x-combo-list-item",
                ".x-menu-item",
            ]
            text_pattern = re.compile(rf"^{re.escape(value_to_set.strip())}$", re.IGNORECASE)
            for selector in option_selectors:
                try:
                    candidate = page.locator(selector).filter(has_text=text_pattern).first
                except Exception:
                    continue
                if candidate.count():
                    option = candidate
                    break

            if option is None or not option.count():
                return False

            try:
                option.scroll_into_view_if_needed()
                option.click(force=True, timeout=4000)
                page.wait_for_timeout(500)
                page.keyboard.press("Tab")
                page.wait_for_timeout(400)
                return True
            except Exception as exc:
                logging.info("Transaction Type dropdown option selection failed: %s", exc)
                return False

        def _select_otc_traded_option(target_field, value_to_set: str) -> bool:
            if label.strip().lower() != "otc traded" or not value_to_set:
                return False

            trigger_selectors = [
                "xpath=ancestor::div[contains(@class,'x-form-field-wrap')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
                "xpath=ancestor::div[contains(@class,'x-form-element')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
                "xpath=../img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]",
            ]
            trigger = None
            for selector in trigger_selectors:
                try:
                    candidate = target_field.locator(selector).first
                except Exception:
                    continue
                if candidate.count():
                    trigger = candidate
                    break

            if trigger is None:
                try:
                    trigger = target_field.locator("xpath=ancestor::div[contains(@class,'x-form-field-wrap')][1]//img[contains(@class,'x-form-trigger-arrow') and contains(@id,'x-auto-')]" ).first
                except Exception:
                    trigger = None

            if trigger is None or not trigger.count():
                return False

            try:
                trigger.scroll_into_view_if_needed()
                trigger.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
            except Exception as exc:
                logging.info("OTC TRADED dropdown trigger click failed: %s", exc)
                return False

            option = None
            option_selectors = [
                "div.x-boundlist div.x-boundlist-item",
                "div.x-boundlist-item",
                "li.x-boundlist-item",
                "div.x-combo-list-item",
                ".x-menu-item",
            ]
            text_pattern = re.compile(rf"^{re.escape(value_to_set.strip())}$", re.IGNORECASE)
            for selector in option_selectors:
                try:
                    candidate = page.locator(selector).filter(has_text=text_pattern).first
                except Exception:
                    continue
                if candidate.count():
                    option = candidate
                    break

            if option is None or not option.count():
                return False

            try:
                option.scroll_into_view_if_needed()
                option.click(force=True, timeout=4000)
                page.wait_for_timeout(500)
                page.keyboard.press("Tab")
                page.wait_for_timeout(400)
                return True
            except Exception as exc:
                logging.info("OTC TRADED dropdown option selection failed: %s", exc)
                return False

        if label.strip().lower() == "transaction type" and value and _select_transaction_type_option(field, value):
            page.wait_for_timeout(400)
            try:
                current_value = field.input_value().strip()
            except Exception:
                try:
                    current_value = field.evaluate("el => el.value").strip()
                except Exception:
                    current_value = ""
            if current_value.lower() == value.strip().lower():
                return
            logging.info("Transaction Type option selected but field value still differs, falling back to manual typing")
            try:
                page.keyboard.press("Tab")
                page.wait_for_timeout(300)
            except Exception:
                pass

        if label.strip().lower() == "otc traded" and value and _select_otc_traded_option(field, value):
            page.wait_for_timeout(400)
            try:
                current_value = field.input_value().strip()
            except Exception:
                try:
                    current_value = field.evaluate("el => el.value").strip()
                except Exception:
                    current_value = ""
            if current_value.lower() == value.strip().lower():
                return
            logging.info("OTC TRADED option selected but field value still differs, falling back to manual typing")
            try:
                page.keyboard.press("Tab")
                page.wait_for_timeout(300)
            except Exception:
                pass

        if label == "Tradable Asset" and value and _handle_tradable_asset(field, value):
            _restore_transaction_type_if_needed()
            try:
                page.keyboard.press("Tab")
                page.wait_for_timeout(300)
            except Exception:
                pass
            return

        if value:
            if not _set_field_value(field, value):
                logging.warning("Field '%s' could not be set with direct DOM injection, fallback typing used", label)
        else:
            logging.info("No value provided for '%s'; preserving existing content", label)

        try:
            field.evaluate(
                "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }"
            )
        except Exception:
            pass

        before_commit = _get_field_value(field)
        logging.info("Field '%s' before commit: '%s'", label, before_commit)
        page.wait_for_timeout(400)
        _commit_field(field)
        page.wait_for_timeout(post_commit_wait_ms)

        if value:
            current_value = _get_field_value(field)
            logging.info("Field '%s' after commit: '%s'", label, current_value)
            if current_value != value.strip():
                logging.warning("Field '%s' did not commit expected value '%s', actual='%s'", label, value.strip(), current_value)
                logging.info("Retrying field '%s' once", label)
                try:
                    field.click(force=True, timeout=4000)
                    field.fill(value)
                    field.evaluate(
                        "el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }"
                    )
                except Exception:
                    pass
                page.wait_for_timeout(400)
                _commit_field(field)
                page.wait_for_timeout(post_commit_wait_ms)
                current_value = _get_field_value(field)
                logging.info("Field '%s' after retry: '%s'", label, current_value)
                if current_value != value.strip():
                    logging.warning("Field '%s' still not committed after retry: expected='%s', actual='%s'", label, value.strip(), current_value)

        try:
            page.keyboard.press("Tab")
            page.wait_for_timeout(300)
        except Exception:
            pass

        if label.strip().lower() == "settlement date":
            # Price can be reset by async recalculation right after settlement date commit.
            # Briefly wait for the form to stabilize before moving to the next field.
            page.wait_for_timeout(900)

        if label.strip().lower() == "client sec account":
            _restore_transaction_type_if_needed()

        if next_target_selector:
            selectors = _split_selectors(next_target_selector)
            clicked_target = False
            for sel in selectors:
                try:
                    candidate = page.locator(sel).first
                except Exception:
                    continue
                if not candidate.count():
                    continue
                try:
                    candidate.scroll_into_view_if_needed()
                    candidate.click(force=True, timeout=4000)
                    clicked_target = True
                    break
                except Exception:
                    pass

            if not clicked_target:
                if not _safe_tab_to_target(
                    next_target_selector,
                    current_field=field,
                    expected_value=value.strip() if value else None,
                    label=label,
                    previous_fields=previous_fields,
                ):
                    logging.info("Safe tab to next field failed for '%s'; clicking target directly", label)
                    for sel in selectors:
                        try:
                            candidate = page.locator(sel).first
                        except Exception:
                            continue
                        if candidate.count():
                            try:
                                candidate.scroll_into_view_if_needed()
                                candidate.click(force=True, timeout=4000)
                            except Exception:
                                pass
                            break

    ordered_specs: List[Dict[str, str]] = list(SAISIE_FIELD_SPECS)
    fillable_keys = {key for key, value in values.items() if value.strip()}
    logging.info("Fields to fill from saisie variables: %s", sorted(fillable_keys))

    for idx, spec in enumerate(ordered_specs):
        key = spec["key"]
        label = spec["label"]
        selector = spec["selector"]
        value = values.get(key, "")

        if key not in fillable_keys:
            logging.info("Skipping field '%s' because no value was provided", label)
            continue

        next_target_selector = None
        for later_spec in ordered_specs[idx + 1 :]:
            if later_spec["key"] in fillable_keys:
                next_target_selector = later_spec["selector"]
                break

        previous_fields = []
        for earlier_spec in reversed(ordered_specs[:idx]):
            if earlier_spec["key"] in fillable_keys:
                previous_label = earlier_spec["label"]
                previous_value = values.get(earlier_spec["key"], "")
                previous_field = _find_field(previous_label, earlier_spec["selector"])
                if not previous_field:
                    try:
                        if _retry_after_help_popup(page, module_name, path_label, f"field {previous_label}"):
                            previous_field = _find_field(previous_label, earlier_spec["selector"])
                    except Exception:
                        pass
                previous_fields.append(
                    {
                        "field": previous_field,
                        "expected": previous_value.strip() if previous_value else None,
                        "label": previous_label,
                    }
                )
        previous_fields.reverse()

        field = _find_field(label, selector)
        if not field:
            if _retry_after_help_popup(page, module_name, path_label, f"field {label}"):
                field = _find_field(label, selector)

        if not field:
            logging.warning("Saisie field '%s' not found for %s", label, path_label)
            capture_failure(page, module_name, f"{path_label} > missing:{label}", always=True)
            return False

        try:
            _manual_type_field(
                field,
                value,
                label,
                next_target_selector,
                previous_fields=previous_fields,
            )
            logging.info("Filled field '%s' with '%s'", label, value)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            logging.warning("Playwright error while filling field '%s' for %s: %s", label, path_label, exc)
            capture_failure(page, module_name, f"{path_label} > playwright_error:{label}", always=True)
            return False

    save_button = page.locator("#Component_PAGE_FORM_0_save_null").first
    if not save_button.count():
        _retry_after_help_popup(page, module_name, path_label, "save button")
        save_button = page.locator("#Component_PAGE_FORM_0_save_null").first

    if not save_button.count():
        logging.warning("Save button for saisie form not found for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False

    try:
        save_button.scroll_into_view_if_needed()
        save_button.click(force=True, timeout=4000)

        # MegaCustody only: wait (longer) for any popup/window to appear after
        # clicking Save, take a screenshot AS SOON AS it shows up, then
        # classify it as success/failure for the filename.
        is_megacustody = _normalize_lookup_text(os.getenv("MENU_CATEGORY_SLUG", "")) == "megacustody"
        if is_megacustody:
            # Selectors that match any kind of popup/window/message-box overlay.
            popup_selectors = [
                "div.x-window-plain.x-window-dlg.x-window.x-component",
                "div.x-window.x-window-dlg",
                "div.x-window:not(.x-hidden)",
                "div.ext-mb-content",
                "span.ext-mb-text",
            ]
            success_locator = page.locator("span.ext-mb-text").filter(has_text=SUCCESS_MESSAGE_PATTERN)

            popup_found = False
            popup_outcome = "no_popup"
            wait_deadline = time.time() + 30  # up to 30s for any popup
            while time.time() < wait_deadline:
                try:
                    # Any visible popup-like element triggers an immediate capture.
                    for sel in popup_selectors:
                        loc = page.locator(sel).first
                        if loc.count():
                            try:
                                if loc.is_visible():
                                    popup_found = True
                                    break
                            except (PlaywrightTimeoutError, PlaywrightError):
                                popup_found = True
                                break
                    if popup_found:
                        break
                except (PlaywrightTimeoutError, PlaywrightError):
                    pass
                page.wait_for_timeout(150)

            # Once a popup is detected, classify it (success vs failure) without
            # missing the moment.
            if popup_found:
                try:
                    if success_locator.count():
                        popup_outcome = "success"
                    elif failure_indicators_present(page):
                        popup_outcome = "failure"
                    else:
                        popup_outcome = "popup"
                except (PlaywrightTimeoutError, PlaywrightError):
                    popup_outcome = "popup"

            try:
                target_dir = SCREENSHOT_DIR / "AWB" / "saisie_instruction_unitaire"
                target_dir.mkdir(parents=True, exist_ok=True)
                filename = f"{slugify(path_label)}_{popup_outcome}_{int(time.time())}.png"
                screenshot_path = target_dir / filename
                page.screenshot(path=str(screenshot_path), full_page=True)
                logging.info(
                    "MegaCustody saisie popup outcome=%s, screenshot saved at %s",
                    popup_outcome,
                    screenshot_path,
                )
            except (PlaywrightTimeoutError, PlaywrightError, OSError) as exc:
                logging.warning("Could not capture MegaCustody saisie screenshot for %s: %s", path_label, exc)

        handle_error_dialog(page, module_name, path_label)
        dismiss_save_success_popup_if_present(page, path_label)
        page.wait_for_timeout(500)
        logging.info("Saisie form saved for %s", path_label)
        return True
    except PlaywrightTimeoutError:
        logging.warning("Saisie save click timed out for %s", path_label)
        capture_failure(page, module_name, path_label, always=True)
        return False


def too_much_data_popup_present(page) -> bool:
    popup_by_xpath = page.locator(f"xpath={AWB_TOO_MUCH_DATA_XPATH}")
    if popup_by_xpath.count() and popup_by_xpath.filter(has_text=TOO_MUCH_DATA_PATTERN).count():
        return True
    if page.locator("span.ext-mb-text").filter(has_text=TOO_MUCH_DATA_PATTERN).count():
        return True
    return False


def capture_failure(page, module_name: str, node_text: str, *, always: bool = False) -> None:
    if too_much_data_popup_present(page):
        logging.info("Skipping tooMuchDataFound popup for %s / %s", module_name, node_text)
        dismiss_error_dialog(page, node_text)
        return

    if not always and not failure_indicators_present(page):
        logging.info("Skipping screenshot for %s / %s because no error indicators were found", module_name, node_text)
        return

    # Derive project/module and top-level menu
    project_slug = "awb"
    module_match = re.search(r"/(Mega[^/]+)/", LOGIN_ENTRY, re.IGNORECASE)
    module_slug = slugify(module_match.group(1)) if module_match else "module"
    # node_text is usually a ' > ' joined path, so split and take the first part as top-level menu
    if '>' in node_text:
        top_level_menu = slugify(node_text.split('>')[0].strip())
    else:
        top_level_menu = slugify(node_text.strip())

    # Build directory path: screenshots/AWB/MODULE/TOP_LEVEL_MENU
    target_dir = SCREENSHOT_DIR / project_slug / module_slug / top_level_menu
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    filename = f"{slugify(node_text)}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.warning("Captured screenshot for %s / %s at %s", module_name, node_text, target)
    dismiss_error_dialog(page, node_text)


def failure_indicators_present(page) -> bool:
    if too_much_data_popup_present(page):
        return False

    warning_icon_locator = page.locator("div.ext-mb-icon.ext-mb-warning")
    warning_icon_count = warning_icon_locator.count()
    header_locator = page.locator("span.x-window-header-text")
    header_error_count = header_locator.filter(has_text="error").count()
    header_count = header_locator.count()

    if page.locator("#x-auto-607-label").filter(has_text=ERROR_HEADING_TEXT).count():
        return True
    if page.locator("#x-auto-607-label").filter(has_text=EMPTY_HEADING_PATTERN).count():
        return True
    if warning_icon_count:
        return True
    if page.locator("span.ext-mb-text#x-auto-610-content").filter(has_text="null").count():
        return True
    if page.locator("span.ext-mb-text#x-auto-887-content").filter(has_text=NO_VALIDATION_MESSAGE).count():
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
    if page.locator("label#x-auto-17050").filter(has_text=LOG_FILE_ERROR_MESSAGE).count():
        return True

    special_content = page.locator("//*[@id='x-auto-1667-content']")
    if special_content.count() and not warning_icon_count and not header_count:
        return True

    return False


def dismiss_error_dialog(page, path_label: str) -> None:
    try:
        # First, try pressing Escape to close context menus or dialogs
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        except Exception:
            pass

        # Try OK button targets for actual error dialogs
        ok_targets = [
            page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first,
            page.locator("//button[normalize-space()='OK']").first,
            page.get_by_role("button", name="OK"),
            page.locator("xpath=//*[@id='x-auto-2726']/tbody/tr[2]/td[2]/em/button").first,
            page.locator("//*[@id='x-auto-3458']/tbody/tr[2]/td[2]/em/button").first,
            page.locator("//*[@id='x-auto-3457']/table/tbody/tr/td[1]/table/tbody/tr/td").first,
            page.locator(f"xpath=/html/body/div[10]/div[2]/div[2]/div/div/div/div/div[1]/table/tbody/tr/td[1]/table/tbody/tr/td/table/tbody/tr[2]/td[2]/em/button").first,
        ]

        ok_found = False
        for ok_target in ok_targets:
            try:
                if ok_target.count():
                    ok_target.click(force=True, timeout=4000)
                    ok_target.click(force=True, timeout=4000)
                    page.wait_for_timeout(600)
                    ok_found = True
                    break
            except Exception:
                continue

        # If error popup and no OK button, click the close icon (but not tab close!)
        if not ok_found:
            try:
                error_header = page.locator("span.x-panel-header-text").filter(has_text="Error").first
                if error_header.count():
                    # Try to click the close icon for the error dialog only
                    close_icon = error_header.locator("xpath=ancestor::div[contains(@class,'x-panel-header')]/descendant::div[contains(@class,'x-tool-close')]").first
                    if close_icon.count():
                        try:
                            close_icon.click(force=True, timeout=4000)
                            page.wait_for_timeout(600)
                        except Exception:
                            logging.debug("Failed to click error dialog close icon for %s", path_label)
            except Exception:
                pass
    except Exception:
        logging.debug("Error in dismiss_error_dialog for %s", path_label)


def close_work_window(page, path_label: str) -> None:
    if page.is_closed():
        logging.info("Page already closed; skipping window close for %s", path_label)
        return

    close_candidates = [
        page.locator(f"xpath={AWB_CLOSE_TAB_AFTER_VIEW_XPATH}").first,
        page.locator("a.x-tab-strip-close").first,
        page.locator("div.x-tool-close").first,
        page.locator("button[aria-label='Close']").first,
    ]
    for target in close_candidates:
        try:
            if not target.count():
                continue
            target.click(force=True, timeout=3500)
            page.wait_for_timeout(500)
            return
        except PlaywrightTimeoutError:
            logging.info("Close candidate timed out for %s", path_label)
        except PlaywrightError:
            logging.info("Window close skipped because target/page is closed for %s", path_label)
            return


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


def find_tree_node(page, label: str, level: int):
    if page.is_closed():
        return page.locator("xpath=/*[false()]")

    exact_pattern = re.compile(rf"^\s*{re.escape(label)}\s*$", re.IGNORECASE)
    level_selector = f"div[role=\"treeitem\"][aria-level=\"{level}\"]"

    try:
        exact_node = page.locator(level_selector).filter(has_text=exact_pattern).first
        if exact_node.count():
            return exact_node
    except PlaywrightError:
        pass

    candidate_labels = _tree_label_candidates(label)
    normalized_candidates = [_normalize_lookup_text(candidate) for candidate in candidate_labels]
    target_prefix = _first_words(label, 3)
    selectors = [
        level_selector,
        "div[role=\"treeitem\"]",
    ]

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
                    candidate_text = _normalize_lookup_text(candidate.inner_text() or "")
                    if not candidate_text:
                        continue
                    if any(
                        candidate_text == normalized_label or normalized_label in candidate_text
                        for normalized_label in normalized_candidates
                    ):
                        return candidate
                    if level == 2 and target_prefix and _first_words(candidate_text, 3) == target_prefix:
                        return candidate
                except Exception:
                    continue

        try:
            node_texts = page.locator(".x-tree3-node-text")
            node_count = node_texts.count()
        except PlaywrightError:
            return page.locator("xpath=/*[false()]")

        for idx in range(node_count):
            candidate = node_texts.nth(idx)
            try:
                candidate_text = _normalize_lookup_text(candidate.inner_text() or "")
                if not candidate_text:
                    continue
                if any(
                    candidate_text == normalized_label or normalized_label in candidate_text
                    for normalized_label in normalized_candidates
                ):
                    ancestor = candidate.locator(
                        "xpath=ancestor::div[contains(@class,'x-tree3-node') or contains(@class,'x-tree-node')]"
                    ).first
                    if ancestor.count():
                        return ancestor
                    return candidate
                if level == 2 and target_prefix and _first_words(candidate_text, 3) == target_prefix:
                    ancestor = candidate.locator(
                        "xpath=ancestor::div[contains(@class,'x-tree3-node') or contains(@class,'x-tree-node')]"
                    ).first
                    if ancestor.count():
                        return ancestor
                    return candidate
            except Exception:
                continue
        page.wait_for_timeout(300)

    fallback = page.locator(".x-tree3-node-text").filter(has_text=label).first
    if fallback.count():
        try:
            ancestor = fallback.locator(
                "xpath=ancestor::div[contains(@class,'x-tree3-node') or contains(@class,'x-tree-node')]"
            ).first
            if ancestor.count():
                return ancestor
        except Exception:
            pass

    return page.locator(f"div[role=\"treeitem\"]").filter(has_text=label).first


def find_tree_node_with_aliases(page, label: str, level: int):
    for candidate_label in _tree_label_candidates(label):
        node = find_tree_node(page, candidate_label, level)
        if node.count():
            return node
    return find_tree_node(page, label, level)


def click_view_context_option(page, module_name: str, path_label: str) -> bool:
    return click_context_menu_option(page, VIEW_OPTION_PATTERN, module_name, path_label)


def click_edit_context_option(page, module_name: str, path_label: str) -> bool:
    return click_context_menu_option(page, EDIT_OPTION_PATTERN, module_name, path_label)


def click_editer_button_robust(page, module_name: str, path_label: str) -> bool:
    """Super-robust Editer button click using ALL possible strategies."""
    logging.info("🔍 SUPER ROBUST: Attempting to click Editer by ALL means for %s", path_label)
    start_time = time.time()
    max_wait = 8
    
    # All possible XPath/selector combinations for Editer
    selectors = {
        "ID XPath simple": "//*[@id='x-auto-7338']",
        "Full XPath": "/html/body/div[10]/div/div[2]/a",
        "querySelector ID": "#x-auto-7338",
        "class selector": "a.x-menu-item:has-text('Editer')",
        "contains text XPath": "//a[contains(text(), 'Editer')]",
        "menu item selector": ".x-menu-list .x-menu-item:has-text('Editer')",
    }
    
    while time.time() - start_time < max_wait:
        # Try each selector with multiple click methods
        for selector_name, selector in selectors.items():
            try:
                elem = page.locator(selector).first
                if elem.count():
                    # Method 1: Force click
                    try:
                        elem.click(force=True, timeout=2000)
                        page.wait_for_timeout(500)
                        logging.info("✅✅ Editer clicked via %s (force click)", selector_name)
                        return True
                    except Exception as e:
                        logging.debug("Force click via %s failed: %s", selector_name, str(e))
                    
                    # Method 2: Regular click
                    try:
                        elem.click(timeout=2000)
                        page.wait_for_timeout(500)
                        logging.info("✅✅ Editer clicked via %s (regular click)", selector_name)
                        return True
                    except Exception as e:
                        logging.debug("Regular click via %s failed: %s", selector_name, str(e))
                    
                    # Method 3: Scroll and click
                    try:
                        elem.scroll_into_view_if_needed()
                        elem.click(force=True, timeout=2000)
                        page.wait_for_timeout(500)
                        logging.info("✅✅ Editer clicked via %s (scroll+click)", selector_name)
                        return True
                    except Exception as e:
                        logging.debug("Scroll+click via %s failed: %s", selector_name, str(e))
            except Exception as e:
                logging.debug("Selector %s failed: %s", selector_name, str(e))
        
        # JavaScript methods - all approaches
        try:
            result = page.evaluate("""
                () => {
                    // Method 1: querySelector by ID
                    let elem = document.querySelector("#x-auto-7338");
                    if (elem) {
                        elem.click();
                        return true;
                    }
                    
                    // Method 2: Find by text content
                    const items = document.querySelectorAll('a.x-menu-item');
                    for (let item of items) {
                        if (item.textContent.trim().toUpperCase().includes('EDITER')) {
                            item.click();
                            return true;
                        }
                    }
                    
                    // Method 3: Search all menu items
                    const allMenuItems = document.querySelectorAll('.x-menu-list .x-menu-item');
                    for (let item of allMenuItems) {
                        if (item.textContent.trim().toUpperCase() === 'EDITER' || 
                            item.textContent.trim().toUpperCase() === 'EDIT') {
                            item.click();
                            return true;
                        }
                    }
                    
                    // Method 4: Find link with text Editer
                    const allLinks = document.querySelectorAll('a');
                    for (let link of allLinks) {
                        if (link.textContent.trim().toUpperCase() === 'EDITER') {
                            link.click();
                            return true;
                        }
                    }
                    
                    return false;
                }
            """)
            if result:
                page.wait_for_timeout(800)
                logging.info("✅✅ Editer clicked via JavaScript")
                return True
        except Exception as e:
            logging.debug("JavaScript methods failed: %s", str(e))
        
        page.wait_for_timeout(500)  # Retry pause
    
    # All strategies failed
    logging.warning("❌ Could not click Editer after %d seconds", max_wait)
    try:
        capture_failure(page, "Editer_super_robust_failed", path_label, always=True)
    except Exception as e:
        logging.debug("Failed to capture screenshot: %s", str(e))
    return False


def click_context_menu_option(page, pattern, module_name: str, path_label: str) -> bool:
    # For Edit/Editer options, use the super robust function
    if pattern.pattern and ('edit' in pattern.pattern.lower() or 'editer' in pattern.pattern.lower()):
        return click_editer_button_robust(page, module_name, path_label)
    
    option = (
        page.locator(".x-menu-list .x-menu-item")
        .filter(has_text=pattern)
        .first
    )
    if not option.count():
        logging.warning("No menu item matching pattern %s found for %s", pattern.pattern, path_label)
        return False

    # Robust retry mechanism - up to 6 seconds to click the Edit option
    logging.info("🔍 Attempting to click menu option for %s (retry for up to 6 seconds)", path_label)
    start_time = time.time()
    max_wait = 6
    
    while time.time() - start_time < max_wait:
        try:
            # Strategy 1: Force click with timeout
            option.click(force=True, timeout=2000)
            page.wait_for_timeout(500)
            logging.info("✅✅ Menu option clicked (force click) for %s", path_label)
            handle_error_dialog(page, module_name, path_label)
            return True
        except Exception as e:
            logging.debug("Force click failed: %s", str(e))
        
        try:
            # Strategy 2: JavaScript click
            result = page.evaluate("""
                () => {
                    const items = document.querySelectorAll('.x-menu-list .x-menu-item');
                    for (let item of items) {
                        const text = item.textContent.trim().toUpperCase();
                        if (text.includes('EDIT') || text.includes('EDITER')) {
                            item.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if result:
                page.wait_for_timeout(500)
                logging.info("✅✅ Menu option clicked (JavaScript) for %s", path_label)
                handle_error_dialog(page, module_name, path_label)
                return True
        except Exception as e:
            logging.debug("JavaScript click failed: %s", str(e))
        
        try:
            # Strategy 3: Regular click
            option.click(timeout=2000)
            page.wait_for_timeout(500)
            logging.info("✅✅ Menu option clicked (regular click) for %s", path_label)
            handle_error_dialog(page, module_name, path_label)
            return True
        except Exception as e:
            logging.debug("Regular click failed: %s", str(e))
        
        page.wait_for_timeout(400)  # Retry pause
    
    # All strategies failed
    logging.warning("❌ Could not click menu option for %s after 6 seconds", path_label)
    try:
        capture_failure(page, "Menu_option_not_clicked", path_label, always=True)
    except Exception as e:
        logging.debug("Failed to capture screenshot: %s", str(e))
    return False


def activate_row_checkbox(result_row, path_label: str):
    checkbox = result_row.locator("td.x-grid3-td-rowOperations input[type=checkbox]").first
    if not checkbox.count():
        return None

    try:
        # Keep row selection stable: do not toggle off an already-selected row.
        if not checkbox.is_checked():
            checkbox.click(force=True, timeout=4000)
    except PlaywrightTimeoutError:
        logging.info("Inline checkbox click timed out for %s", path_label)
    return checkbox


def get_row_operations_target(result_row):
    cell = result_row.locator("td.x-grid3-td-rowOperations").first
    return cell if cell.count() else result_row


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
            #target.click(button="right", force=True, timeout=4000)
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

    # Robust Edit click (SAME PATTERN AS VIEW)
    logging.info("🔍 Attempting to click Editer for %s", path_label)
    edit_option = page.locator(f"xpath={AWB_EDIT_OPTION_XPATH}").first
    if edit_option.count():
        try:
            edit_option.click(force=True, timeout=4000)
            page.wait_for_timeout(500)
            logging.info("✅✅ Editer clicked (direct XPath) for %s", path_label)
            handle_edit_panel(page, module_name, path_label)
        except Exception as e:
            logging.debug("Direct XPath click failed: %s", str(e))
            # Fallback to robust function
            if click_editer_button_robust(page, module_name, path_label):
                handle_edit_panel(page, module_name, path_label)
            else:
                logging.warning("❌ Editer option not clicked for %s", path_label)
                page.wait_for_timeout(800)
    else:
        logging.info("Direct XPath not found, trying robust methods for %s", path_label)
        if click_editer_button_robust(page, module_name, path_label):
            handle_edit_panel(page, module_name, path_label)
        else:
            logging.warning("❌ Editer option not found for %s", path_label)
            page.wait_for_timeout(800)


def handle_error_dialog(page, module_name: str, path_label: str) -> bool:
    page.wait_for_timeout(600)
    if not failure_indicators_present(page):
        return False

    logging.warning("Detected error dialog for %s", path_label)
    capture_failure(page, module_name, path_label)
    return True


def click_search_button_if_available(page, module_name: str, path_label: str) -> bool:
    candidates = [
        page.locator(f"xpath={AWB_SEARCH_BUTTON_XPATH}").first,
        page.locator(EXECUTE_CRITERIA_SELECTOR).first,
        page.locator("[id*='executeCriteria']").first,
    ]

    for target in candidates:
        if not target.count():
            continue
        try:
            target.scroll_into_view_if_needed()
            try:
                target.dblclick(force=True, timeout=4000)
            except PlaywrightTimeoutError:
                target.click(force=True, timeout=4000)
            logging.info("Search clicked for %s", path_label)
            handle_error_dialog(page, module_name, path_label)
            page.wait_for_timeout(500)
            return True
        except PlaywrightTimeoutError:
            logging.info("Search candidate present but not clickable for %s", path_label)

    return False


def dismiss_ok_popup_if_present(page, path_label: str) -> bool:
    """Quickly dismiss visible OK popup without introducing startup delay."""
    try:
        if _fast_dismiss_ok_popup_if_present(page, path_label):
            return True

        # Single lightweight fallback pass only; do not block traversal.
        selectors = [
            "button.x-btn-text:has-text('OK')",
            "button:has-text('OK')",
            "div.ext-mb-buttons button",
        ]
        for selector in selectors:
            try:
                btn = page.locator(selector).first
            except Exception:
                continue
            if not btn.count():
                continue
            try:
                btn.click(force=True, timeout=800)
                page.wait_for_timeout(120)
                logging.info("OK popup dismissed quickly for %s", path_label)
                return True
            except Exception:
                continue
        return False

    except Exception as e:
        logging.debug("Quick OK popup check failed for %s: %s", path_label, str(e))
        return False


def _fast_dismiss_ok_popup_if_present(page, path_label: str) -> bool:
    """Instantly dismiss any visible warning/OK popup via direct JS click.

    Targets the ExtJS warning dialog: a div.x-window* container with a
    <button class="x-btn-text">OK</button> inside.  Pure JS — no Python DOM
    overhead.  Retries up to 3 times with 200 ms pauses (600 ms max).
    """
    _JS = """
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
    for attempt in range(3):
        try:
            if page.is_closed():
                return False
            if page.evaluate(_JS):
                logging.info("Warning/OK popup dismissed instantly (attempt %d) for %s", attempt + 1, path_label)
                page.wait_for_timeout(300)
                return True
        except Exception:
            pass
        if attempt < 2:
            page.wait_for_timeout(200)
    return False


def dismiss_save_success_popup_if_present(page, path_label: str) -> bool:
    """Dismiss the save success popup that appears after clicking Save."""
    try:
        success_text = re.compile(
            r"(?:entit[ée]\s*)?sauv(?:e)?gard[ée]e?\s+avec\s+succ[eè]s",
            re.IGNORECASE,
        )
        popup_roots = page.locator("div.x-window, div.x-window-plain, div.x-window-dlg")
        if not popup_roots.count():
            return False

        popup_root = None
        for idx in range(popup_roots.count()):
            candidate = popup_roots.nth(idx)
            info_icon = candidate.locator("div.ext-mb-icon.ext-mb-info")
            notification_header = candidate.locator("span.x-window-header-text, span.x-window-header-text-default").filter(
                has_text=re.compile(r"notification", re.IGNORECASE)
            )
            success_message = candidate.locator("span.ext-mb-text").filter(has_text=success_text)
            if success_message.count() and (info_icon.count() or notification_header.count()):
                popup_root = candidate
                break

        if popup_root is None:
            return False

        ok_button_candidates = [
            popup_root.locator("button.x-btn-text").filter(has_text=re.compile(r"^OK$", re.IGNORECASE)).first,
            popup_root.locator("xpath=.//button[normalize-space()='OK']").first,
            popup_root.get_by_role("button", name=re.compile(r"^OK$", re.IGNORECASE)).first,
            page.locator("xpath=/html/body/div[10]/div[2]/div[2]/div/div/div/div/div[1]/table/tbody/tr/td[1]/table/tbody/tr/td/table/tbody/tr[2]/td[2]/em/button").first,
            page.locator("xpath=//*[@id='x-auto-2211']/tbody/tr[2]/td[2]/em/button").first,
            page.locator("#x-auto-2211 > tbody > tr:nth-child(2) > td.x-btn-mc > em > button").first,
        ]

        for ok_button in ok_button_candidates:
            try:
                if not ok_button.count():
                    continue
                ok_button.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
                logging.info("✅✅ Save success popup dismissed for %s", path_label)
                return True
            except Exception as exc:
                logging.debug("Save popup OK click failed for %s: %s", path_label, str(exc))

        logging.warning("Save success popup detected but OK button could not be clicked for %s", path_label)
        return False
    except Exception as exc:
        logging.error("Exception in dismiss_save_success_popup_if_present for %s: %s", path_label, str(exc))
        return False


def wait_for_and_dismiss_success_popup(page, path_label: str, timeout_ms: int = 10000) -> bool:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        if dismiss_save_success_popup_if_present(page, path_label):
            return True
        page.wait_for_timeout(300)
    return False



def right_click_row_after_execute(page, module_name: str, path_label: str):
    # Give extra time for any popups to appear after execute search
    page.wait_for_timeout(1000)
    
    # First check if an OK popup appeared and dismiss it
    dismiss_ok_popup_if_present(page, path_label)
    page.wait_for_timeout(800)
    
    # Now ensure we right-click on the first data row in the grid
    logging.info("Searching for first row to right-click for %s", path_label)
    row_selectors = [
        f"xpath={AWB_RESULT_ROW_XPATH}",
        f"xpath={AWB_RESULT_ROW_AFTER_EXECUTE_XPATH}",
        "[id$=PalmyraGrid_0]",
    ]

    for selector in row_selectors:
        try:
            page.wait_for_selector(selector, timeout=6000)
        except PlaywrightTimeoutError:
            continue

        row = page.locator(selector).first
        if not row.count():
            continue

        for attempt in range(2):
            try:
                row.scroll_into_view_if_needed()
                row.click(force=True, timeout=4000)
                page.wait_for_timeout(250)
                row.click(button="right", force=True, timeout=4000)
                logging.info("Right-click done after execute for %s (selector=%s, attempt=%d)", path_label, selector, attempt + 1)
                handle_error_dialog(page, module_name, path_label)
                page.wait_for_timeout(400)
                return row
            except PlaywrightTimeoutError:
                logging.info("Right-click after execute timed out for %s (selector=%s, attempt=%d)", path_label, selector, attempt + 1)

    logging.warning("No row available for right-click after execute for %s", path_label)
    return None


def get_first_visible_search_row(page):
    candidates = [
        page.locator("tr[id*='PalmyraGrid_'][id$='_0']").first,
        page.locator("[id$='PalmyraGrid_0']").first,
        page.locator(f"xpath={AWB_RESULT_ROW_DYNAMIC_XPATH}").first,
        page.locator(f"xpath={AWB_RESULT_ROW_XPATH}").first,
        page.locator(AWB_FIRST_ROW_JS_CSS).first,
        page.locator("div.x-grid3-row").first,
    ]

    for row in candidates:
        if not row.count():
            continue
        try:
            if row.is_visible():
                return row
        except Exception:
            return row
    return None


def awb_view_then_edit_flow(page, module_name: str, path_label: str) -> None:
    """Workflow: Check for Edit first. If it exists, do View+Return+Edit. If not, just View+Close."""
    container_selector = f"xpath={AWB_SEARCH_VIEW_CONTAINER_XPATH}"
    dynamic_row_selector = f"xpath={AWB_RESULT_ROW_DYNAMIC_XPATH}"
    row_selector = f"xpath={AWB_RESULT_ROW_XPATH}"
    
    try:
        page.wait_for_selector(container_selector, timeout=8000)
    except PlaywrightTimeoutError:
        logging.warning("Search view container did not appear for %s", path_label)
        capture_failure(page, module_name, path_label)
        return

    first_row_ready = False
    for selector in [dynamic_row_selector, row_selector, AWB_FIRST_ROW_JS_CSS]:
        try:
            page.wait_for_selector(selector, timeout=4000)
            first_row_ready = True
            break
        except PlaywrightTimeoutError:
            continue

    if not first_row_ready:
        logging.warning("No first row selector appeared for %s", path_label)
        capture_failure(page, module_name, path_label)
        return

    container = page.locator(container_selector).first
    if not container.count():
        logging.warning("Container/first row missing for %s", path_label)
        capture_failure(page, module_name, path_label)
        return

    # Step 1: Right-click on the first visible row to open context menu
    try:
        container.scroll_into_view_if_needed()
        container.click(force=True, timeout=4000)
        row = get_first_visible_search_row(page)
        if row is None:
            raise PlaywrightTimeoutError("First visible search row not found")
        row.scroll_into_view_if_needed()
        row.click(force=True, timeout=4000)
        page.wait_for_timeout(200)
        row.click(button="right", force=True, timeout=4000)
        logging.info("First visible row selected and right-clicked for %s", path_label)
    except PlaywrightTimeoutError:
        logging.warning("Failed to right-click first element for %s", path_label)
        capture_failure(page, module_name, path_label)
        return

    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(400)

    # Step 2: Check if Edit option exists in the context menu
    edit_option_xpath = page.locator(f"xpath={AWB_EDIT_OPTION_XPATH}").first
    edit_option_context = (
        page.locator(".x-menu-list .x-menu-item").filter(has_text=EDIT_OPTION_PATTERN).first
    )
    
    edit_exists = (edit_option_xpath.count() > 0) or (edit_option_context.count() > 0)
    logging.info("Edit option exists: %s for %s", edit_exists, path_label)

    if not edit_exists:
        # WORKFLOW A: No Edit available → Just View and Close
        logging.info("No Edit available. Using simplified workflow (View only) for %s", path_label)
        
        # Click View
        view_option = page.locator(f"xpath={AWB_VIEW_OPTION_XPATH}").first
        if view_option.count():
            view_option.click(force=True, timeout=4000)
        elif not click_view_context_option(page, module_name, path_label):
            logging.warning("View option not available for %s", path_label)
            try:
                page.keyboard.press("Escape")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except:
                pass
            capture_failure(page, module_name, path_label)
            return

        logging.info("View clicked (no Edit) for %s", path_label)
        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(800)
        
        # Close the window directly
        close_tab = page.locator(f"xpath={AWB_CLOSE_TAB_AFTER_VIEW_XPATH}").first
        if close_tab.count():
            try:
                close_tab.click(force=True, timeout=4000)
                page.wait_for_timeout(500)
                logging.info("Tab closed for %s", path_label)
            except PlaywrightTimeoutError:
                logging.warning("Close tab click timed out for %s", path_label)
        else:
            close_button = page.locator("a.x-tab-strip-close").first
            if close_button.count():
                try:
                    close_button.click(force=True, timeout=4000)
                    page.wait_for_timeout(500)
                    logging.info("Tab closed for %s", path_label)
                except PlaywrightTimeoutError:
                    logging.warning("Close button click timed out for %s", path_label)
    else:
        # WORKFLOW B: Edit exists → Do View → Return → Edit → Close
        logging.info("Edit available. Using full workflow (View+Edit) for %s", path_label)
        
        # Click View
        view_option = page.locator(f"xpath={AWB_VIEW_OPTION_XPATH}").first
        if view_option.count():
            view_option.click(force=True, timeout=4000)
        elif not click_view_context_option(page, module_name, path_label):
            logging.warning("View option not available for %s", path_label)
            try:
                page.keyboard.press("Escape")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except:
                pass
            capture_failure(page, module_name, path_label)
            return

        logging.info("View clicked for %s", path_label)
        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(600)

        # Click Return button
        return_btn = page.locator(f"xpath={AWB_RETURN_AFTER_VIEW_XPATH}").first
        if return_btn.count():
            try:
                return_btn.click(force=True, timeout=4000)
                logging.info("Return clicked for %s", path_label)
            except PlaywrightTimeoutError:
                logging.warning("Return click timed out for %s", path_label)
                capture_failure(page, module_name, path_label)
                return
        else:
            logging.warning("Return button not found for %s", path_label)
            capture_failure(page, module_name, path_label)
            return

        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(500)

        # Right-click again on the first visible row
        try:
            container.scroll_into_view_if_needed()
            container.click(force=True, timeout=4000)
            row = get_first_visible_search_row(page)
            if row is None:
                raise PlaywrightTimeoutError("First visible search row not found after return")
            row.scroll_into_view_if_needed()
            row.click(force=True, timeout=4000)
            page.wait_for_timeout(200)
            row.click(button="right", force=True, timeout=4000)
            logging.info("Right-click after return done for %s", path_label)
        except PlaywrightTimeoutError:
            logging.warning("Right-click after return failed for %s", path_label)
            capture_failure(page, module_name, path_label)
            return

        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(600)

        # Wait for context menu to appear
        try:
            page.wait_for_selector(".x-menu-list", timeout=3500)
            logging.info("Context menu appeared after return for %s", path_label)
        except PlaywrightTimeoutError:
            logging.warning("Context menu did not appear after return for %s", path_label)
            capture_failure(page, module_name, path_label)
            return

        # Click Edit option (SAME PATTERN AS VIEW)
        logging.info("🔍 Attempting to click Editer for %s", path_label)
        edit_option = page.locator(f"xpath={AWB_EDIT_OPTION_XPATH}").first
        if edit_option.count():
            try:
                edit_option.click(force=True, timeout=4000)
                page.wait_for_timeout(500)
                logging.info("✅✅ Editer clicked (direct XPath) for %s", path_label)
            except Exception as e:
                logging.debug("Direct XPath click failed: %s", str(e))
                # Fallback to robust function
                if not click_editer_button_robust(page, module_name, path_label):
                    logging.warning("❌ Editer option not clicked for %s", path_label)
                    capture_failure(page, module_name, path_label)
                    return
        else:
            logging.info("Direct XPath not found, trying robust methods for %s", path_label)
            if not click_editer_button_robust(page, module_name, path_label):
                logging.warning("❌ Editer option not found for %s", path_label)
                capture_failure(page, module_name, path_label)
                return
        handle_edit_panel(page, module_name, path_label)
        
        # Close the tab
        close_tab = page.locator(f"xpath={AWB_CLOSE_TAB_AFTER_VIEW_XPATH}").first
        if close_tab.count():
            try:
                close_tab.click(force=True, timeout=4000)
                page.wait_for_timeout(500)
                logging.info("Tab closed after Edit for %s", path_label)
            except PlaywrightTimeoutError:
                logging.warning("Close tab click timed out for %s", path_label)
        else:
            close_button = page.locator("a.x-tab-strip-close").first
            if close_button.count():
                try:
                    close_button.click(force=True, timeout=4000)
                    page.wait_for_timeout(500)
                    logging.info("Tab closed after Edit for %s", path_label)
                except PlaywrightTimeoutError:
                    logging.warning("Close button click timed out for %s", path_label)


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
        dismiss_save_success_popup_if_present(page, path_label)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Saving failed for %s", path_label)
        capture_failure(page, module_name, path_label)
        close_work_window(page, path_label)
        return

    success_message = page.locator("span.ext-mb-text").filter(has_text=SUCCESS_MESSAGE_PATTERN)
    if success_message.count():
        ok_button = (
            page.locator("button.x-btn-text")
            .filter(has_text=OK_BUTTON_PATTERN)
            .first
        )
        if ok_button.count():
            try:
                ok_button.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
            except PlaywrightTimeoutError:
                logging.warning("Unable to dismiss success dialog for %s", path_label)
    else:
        logging.warning("Save confirmation missing for %s", path_label)
        capture_failure(page, module_name, path_label)

    dismiss_save_success_popup_if_present(page, path_label)

    close_work_window(page, path_label)


def _find_first_visible(page, selectors: List[str]):
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() and locator.is_visible():
            return locator
    return None


def _submit_credentials(
    page,
    auth_username: str = AUTH_USERNAME,
    auth_password: str = AUTH_PASSWORD,
    auth_domain: str = AUTH_DOMAIN,
) -> bool:
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

    username_input.fill(auth_username)
    password_input.fill(auth_password)

    domain_field = _find_first_visible(
        page,
        [
            "input[name='j_asp']",
            "#domain",
            "select[name='domain']",
            "input[name='domain']",
            "input[id*='domain']",
        ],
    )
    if domain_field is not None and auth_domain:
        domain_key = auth_domain.strip().lower()
        selected = False

        try:
            tag_name = (domain_field.evaluate("el => el.tagName") or "").lower()
        except Exception:
            tag_name = ""

        if tag_name == "select":
            try:
                domain_field.select_option(label=auth_domain)
                selected = True
            except Exception:
                selected = False

            if not selected:
                try:
                    options = domain_field.locator("option")
                    for idx in range(options.count()):
                        option = options.nth(idx)
                        option_label = (option.inner_text() or "").strip()
                        option_value = (option.get_attribute("value") or "").strip()
                        label_key = option_label.lower()
                        value_key = option_value.lower()
                        if (
                            domain_key == label_key
                            or domain_key == value_key
                            or domain_key in label_key
                            or domain_key in value_key
                            or label_key in domain_key
                            or value_key in domain_key
                            or domain_key.split()[0] == label_key
                            or domain_key.split()[0] == value_key
                        ):
                            if option_value:
                                domain_field.select_option(value=option_value)
                            else:
                                domain_field.select_option(label=option_label)
                            selected = True
                            break
                except PlaywrightTimeoutError:
                    logging.debug("Domain options loading timed out for %s", auth_domain)

            # Some Keycloak themes require opening the select then choosing by visible text.
            if not selected:
                try:
                    domain_field.click(force=True, timeout=3000)
                    option_locator = domain_field.locator("option").filter(
                        has_text=re.compile(re.escape(domain_key.split()[0]), re.IGNORECASE)
                    ).first
                    if option_locator.count():
                        option_value = (option_locator.get_attribute("value") or "").strip()
                        option_label = (option_locator.inner_text() or "").strip()
                        if option_value:
                            domain_field.select_option(value=option_value)
                        elif option_label:
                            domain_field.select_option(label=option_label)
                        selected = True
                except PlaywrightTimeoutError:
                    logging.debug("Domain explicit option-click path timed out for %s", auth_domain)
        else:
            try:
                domain_field.click(force=True, timeout=4000)
                domain_field.fill(auth_domain)
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
                    logging.debug("Domain input interaction timed out for %s", auth_domain)

        if selected:
            logging.info("Selected domain %s", auth_domain)
        else:
            logging.warning("Domain %s not found in login form options", auth_domain)

    submit = page.locator("#kc-login, button[name='login'], input[name='login'], button[type=submit], input[type=submit]")
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

    submit_by_role = page.get_by_role("button", name="Submit")
    if submit_by_role.count():
        try:
            submit_by_role.wait_for(state="visible", timeout=15000)
            if not submit_by_role.is_enabled():
                logging.error("Submit button by role is visible but not enabled.")
                return False
            submit_by_role.click()
            return True
        except PlaywrightTimeoutError:
            logging.error("Submit button by role not clickable after waiting.")
            return False

    logging.error("No submit button found on login page.")
    return False


def login(
    page,
    auth_username: str = AUTH_USERNAME,
    auth_password: str = AUTH_PASSWORD,
    auth_domain: str = AUTH_DOMAIN,
) -> bool:
    logging.info("Navigating to login entry point")
    def _is_retryable_navigation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        retryable_tokens = (
            "net::err_network_changed",
            "net::err_connection_timed_out",
            "net::err_connection_closed",
            "net::err_connection_reset",
            "net::err_internet_disconnected",
            "net::err_address_unreachable",
            "net::err_timed_out",
            "timeout",
        )
        return any(token in message for token in retryable_tokens)

    login_page_opened = False
    for attempt in range(1, LOGIN_NAVIGATION_MAX_ATTEMPTS + 1):
        try:
            page.goto(
                LOGIN_ENTRY,
                wait_until="domcontentloaded",
                timeout=LOGIN_NAVIGATION_TIMEOUT_MS,
            )
            login_page_opened = True
            break
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            if attempt >= LOGIN_NAVIGATION_MAX_ATTEMPTS or not _is_retryable_navigation_error(exc):
                logging.error("Failed to open login page %s: %s", LOGIN_ENTRY, exc)
                return False

            logging.warning(
                "Attempt %d/%d failed to open %s (%s). Retrying in %.1fs...",
                attempt,
                LOGIN_NAVIGATION_MAX_ATTEMPTS,
                LOGIN_ENTRY,
                exc,
                LOGIN_NAVIGATION_RETRY_DELAY_MS / 1000,
            )
            page.wait_for_timeout(LOGIN_NAVIGATION_RETRY_DELAY_MS)

    if not login_page_opened:
        logging.error("Failed to open login page %s after retries.", LOGIN_ENTRY)
        return False

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

    try:
        page.wait_for_selector("#username, input[name='username'], input[name='j_username']", timeout=15000)
    except PlaywrightTimeoutError:
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

    if not _submit_credentials(page, auth_username, auth_password, auth_domain):
        return False

    # Some environments keep background network traffic alive, so `networkidle`
    # is unreliable for login success detection.
    app_ready = (
        "div[role='treeitem'], "
        "button:has-text('Position'), "
        "button:has-text('Referentiel'), "
        "a.x-tab-strip-text"
    )
    try:
        page.wait_for_selector(app_ready, timeout=45000)
    except PlaywrightTimeoutError:
        # Fallback: if login form disappeared, continue and let menu traversal validate.
        login_still_visible = page.locator("#username, input[name='username'], input[name='j_username']").count()
        if login_still_visible:
            logging.error("Login form is still visible after submit.")
            return False
    except PlaywrightError as exc:
        if "Target page, context or browser has been closed" in str(exc):
            logging.error("Browser page closed during login readiness wait.")
            return False
        raise

    logging.info("Login submitted (auth=%s, domain=%s, module=%s)", AUTH_TYPE, auth_domain, LOGIN_ENTRY)
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
    if page.is_closed():
        logging.info("Page already closed; skipping ancestor collapse")
        return

    for depth in range(len(path) - 1, 1, -1):
        if page.is_closed():
            logging.info("Page closed during ancestor collapse; stopping")
            return

        prefix = tuple(path[:depth])
        if prefix not in expanded_nodes:
            continue
        if has_future_path_with_prefix(menu_paths, current_index, prefix):
            continue

        ancestor_label = path[depth - 1]
        try:
            ancestor_node = find_tree_node_with_aliases(page, ancestor_label, depth)
            if not ancestor_node.count():
                continue
        except PlaywrightError:
            logging.info("Skipping ancestor lookup because page/target is closed for %s", ancestor_label)
            return

        try:
            ancestor_node.dblclick(force=True, timeout=4000)
            page.wait_for_timeout(800)
            expanded_nodes.discard(prefix)
        except PlaywrightTimeoutError:
            logging.info("Could not collapse ancestor %s", ancestor_label)
        except PlaywrightError:
            logging.info("Stopping ancestor collapse because page/target is closed")
            return


def traverse_menu_paths(page, menu_paths: List[List[str]]) -> None:
    if not menu_paths:
        logging.warning("No menu paths supplied")
        return

    parent_prefixes = build_parent_prefixes(menu_paths)
    expanded_nodes: set[tuple[str, ...]] = set()

    for index, path in enumerate(menu_paths):
        if page.is_closed():
            logging.warning("Page already closed before path traversal; stopping remaining paths.")
            return

        if len(path) < 2:
            logging.warning("Skipping short path %s", path)
            continue

        top_level = path[0]
        button = page.get_by_role("button", name=top_level)
        try:
            button_count = button.count()
        except Exception as exc:
            logging.warning("Could not inspect top level tab %s because page is closed/unavailable: %s", top_level, exc)
            return

        if not button_count:
            logging.warning("Top level tab %s not found", top_level)
            continue

        path_label = " > ".join(path)
        wait_for_and_dismiss_success_popup(page, path_label, timeout_ms=120)
        dismiss_ok_popup_if_present(page, path_label)
        try:
            button.click()
        except Exception as exc:
            logging.warning(f"[SAFE] Could not click top level tab {top_level} for path {path_label}: {exc}")
            try:
                capture_failure(page, top_level, path_label, always=True)
            except Exception:
                logging.warning(f"[SAFE] Could not capture failure for {path_label}")
            continue

        normalized_path = _normalize_menu_segments(path)
        logging.info("Traversing path %s", path_label)
        position_filter_mode = get_position_filter_mode(path)
        page.wait_for_timeout(200)
        start_tree_wait = time.perf_counter()
        try:
            page.wait_for_selector("div[role='treeitem']", timeout=6000)
            elapsed = time.perf_counter() - start_tree_wait
            logging.info("Top-level tab '%s' tree loaded in %.3fs for %s", top_level, elapsed, path_label)
        except PlaywrightTimeoutError:
            elapsed = time.perf_counter() - start_tree_wait
            logging.warning("Tree items did not appear after %.3fs for top level tab %s for %s", elapsed, top_level, path_label)

        # --- Menu-specific workflows ---
        if (normalized_path == MARCHE_TRANSFER_PATH or normalized_path == MARCHE_CONSULTATION_PATH):
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
        # Always check for max screens popup after each node interaction
        handle_max_screens_popup(page)
        dismiss_help_description_popup_if_present(page)

        # Now traverse the tree nodes for this path

        for child_index, segment in enumerate(path[1:], start=1):
            level = child_index + 1
            prefix = tuple(path[: child_index + 1])
            node_is_leaf = prefix not in parent_prefixes
            segment_start = time.perf_counter()
            node = find_tree_node_with_aliases(page, segment, level)
            node_elapsed = time.perf_counter() - segment_start
            found = node.count() > 0 and node.is_visible()
            logging.info("Lookup segment '%s' level %d took %.3fs, found=%s for %s", segment, level, node_elapsed, found, path_label)
            if not found:
                logging.warning("[SKIP] Tree node '%s' at level %d not found or not visible for path: %s. Skipping this path.", segment, level, path_label)
                break

            try:
                node.scroll_into_view_if_needed()
            except PlaywrightTimeoutError:
                logging.warning("[EXPAND] Timeout on scroll_into_view_if_needed for '%s' at level %d for path: %s. Skipping this path.", segment, level, path_label)
                break

            already_expanded = prefix in expanded_nodes
            try:
                if node_is_leaf:
                    node.click(force=True, timeout=4000)
                else:
                    if already_expanded:
                        logging.info(
                            "Keeping ancestor %s at level %d open for %s",
                            segment,
                            level,
                            path_label,
                        )
                        node.click(force=True, timeout=4000)
                    else:
                        node.dblclick(force=True, timeout=5000)
                        expanded_nodes.add(prefix)
            except PlaywrightTimeoutError:
                logging.warning("Failed to interact with %s at level %d (leaf=%s). Skipping this path.", segment, level, node_is_leaf)
                break
            finally:
                handle_error_dialog(page, top_level, path_label)

            page.wait_for_timeout(50)

            if node_is_leaf:
                if _is_current_module("MegaCustody") and normalized_path == SAISIE_INSTRUCTION_CLIENT_PATH:
                    if fill_saisie_instruction_client_form(page, top_level, path_label):
                        close_work_window(page, path_label)
                    else:
                        close_work_window(page, path_label)
                    collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                    break

                click_search_button_if_available(page, top_level, path_label)

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
                                handle_error_dialog(page, top_level, path_label)
                                
                                # Dismiss warning/OK popup instantly if present after execute search
                                _fast_dismiss_ok_popup_if_present(page, path_label)
                                
                                page.wait_for_timeout(800)
                                try:
                                    page.wait_for_selector("div.x-grid3-row", timeout=6000)
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
                                table_root = page.locator("table.x-form-search").first
                                grid_row_locator = page.locator("[id$=PalmyraGrid_0]").first
                                try:
                                    grid_row_locator.wait_for(timeout=6000)
                                except PlaywrightTimeoutError:
                                    logging.warning(
                                        "First grid row not rendered after execute for %s",
                                        path_label,
                                    )
                                    capture_failure(page, top_level, path_label)
                                    raise
                                result_row = grid_row_locator
                                if not result_row.count():
                                    logging.warning(
                                        "Unable to locate first grid row after execute for %s",
                                        path_label,
                                    )
                                    capture_failure(page, top_level, path_label)
                                    raise PlaywrightTimeoutError("First result row missing after execute search")

                                # AWB requirement: right-click the selected row right after execute.
                                right_clicked_row = right_click_row_after_execute(page, top_level, path_label)
                                if right_clicked_row is not None:
                                    result_row = right_clicked_row
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
                            awb_view_then_edit_flow(page, top_level, path_label)
                        except PlaywrightTimeoutError as exc:
                            logging.warning("Context menu interaction failed for %s: %s", path_label, exc)
                            capture_failure(page, top_level, path_label, always=True)
                    else:
                        logging.warning("No result rows found for %s", path_label)
                        capture_failure(page, top_level, path_label)
                else:
                    # Check for grid-based results (PalmyraGrid)
                    grid_row_locator = page.locator("[id$=PalmyraGrid_0]").first
                    if grid_row_locator.count():
                        # Grid results present - perform right-click
                        right_clicked_row = right_click_row_after_execute(page, top_level, path_label)
                        if right_clicked_row is not None:
                            result_row = right_clicked_row
                        else:
                            result_row = grid_row_locator
                        
                        activate_row_checkbox(result_row, path_label)
                        awb_view_then_edit_flow(page, top_level, path_label)
                    else:
                        capture_failure(page, top_level, path_label)

                close_button = page.locator("a.x-tab-strip-close")
                if close_button.count():
                    close_button.first.click()
                    page.wait_for_timeout(600)
                collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)

def main() -> None:
    os.environ.setdefault("MENU_CATEGORY_SLUG", "megacustody")
    ensure_playwright_node_path()
    menu_paths = [
        ["Règlement/Livraison", "Instructions Clients", "Saisie Instruction Client"],
    ]

    def _safe_close_resource(name: str, close_action) -> None:
        if close_action is None:
            return
        try:
            close_action()
        except KeyboardInterrupt:
            logging.warning("Interrupted while closing %s", name)
        except Exception as exc:
            logging.debug("Ignoring %s close error: %s", name, exc)

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
        page = context.new_page()
        page.add_init_script("window.addEventListener('contextmenu', event => event.preventDefault(), { capture: true });")
        page.add_init_script("""
            (() => {
                const suppressHelpPopup = () => {
                    const windows = document.querySelectorAll('div.x-window, div.x-window-plain, div.x-window-dlg');
                    for (const win of windows) {
                        const text = (win.textContent || '').replace(/\s+/g, ' ').trim();
                        if (/Help Description/i.test(text) || /EditClientInstruction/i.test(text)) {
                            const closeButton = win.querySelector('.x-tool-close, button[aria-label="Close"], button[aria-label="Fermer"]');
                            if (closeButton) {
                                closeButton.click();
                            } else {
                                win.remove();
                            }
                            return true;
                        }
                    }
                    return false;
                };

                const patchExtWindow = () => {
                    const ExtWindow = window.Ext && ((window.Ext.window && window.Ext.window.Window) || window.Ext.Window);
                    if (!ExtWindow || ExtWindow.prototype.__helpPopupSuppressed) {
                        return false;
                    }

                    const originalShow = ExtWindow.prototype.show;
                    ExtWindow.prototype.show = function() {
                        try {
                            const title = String(this.title || '');
                            const body = String(this.html || this.body || this.message || '');
                            if (/Help Description/i.test(title) || /EditClientInstruction/i.test(body)) {
                                try {
                                    this.close();
                                } catch (error) {
                                    this.hide();
                                }
                                return this;
                            }
                        } catch (error) {
                            // Ignore and fall back to the original behaviour.
                        }
                        return originalShow.apply(this, arguments);
                    };

                    ExtWindow.prototype.__helpPopupSuppressed = true;
                    return true;
                };

                const startedAt = Date.now();
                const timer = window.setInterval(() => {
                    try {
                        patchExtWindow();
                        suppressHelpPopup();
                        if (Date.now() - startedAt > 15000) {
                            window.clearInterval(timer);
                        }
                    } catch (error) {
                        // Ignore transient DOM timing issues.
                    }
                }, 100);
            })();
        """)
        try:
            if not login(page):
                logging.error("Login failed for %s. Aborting menu traversal.", LOGIN_ENTRY)
                return
            if menu_paths:
                traverse_menu_paths(page, menu_paths)
            else:
                process_menu(page)
        finally:
            _safe_close_resource("page", lambda: (not page.is_closed()) and page.close())
            _safe_close_resource("context", context.close)
            _safe_close_resource("browser", browser.close)


if __name__ == "__main__":
    main()
