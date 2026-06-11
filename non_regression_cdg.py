RESULT_ROW_PREFIX_SELECTOR = "[id^='Component_PAGE_FORM_1_']"
RESULT_ROW_TABLE_SELECTOR = "[id^='Component_PAGE_FORM_1_DataTable_']"
# Imports
import logging
import os
import re
import time
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

LOGIN_ENTRY = os.getenv("MODULE_URL", "https://10.1.140.42/MegaCor/")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/CDG/common menu/cdg_common.txt"))
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

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    return cleaned.strip("_").lower() or "node"


def capture_failure(page, module_name: str, node_text: str, *, always: bool = False) -> None:
    if not always and not failure_indicators_present(page):
        logging.info("Skipping screenshot for %s / %s because no error indicators were found", module_name, node_text)
        return

    # Use environment variables set by PowerShell launcher
    # PROJECT: AWB, BMCE, CDG (uppercase)
    # MODULE: MegaCommon, MegaCor, etc. (title case -> lowercase)
    project = os.getenv("PROJECT_SLUG", "cdg")
    module_folder = slugify(os.getenv("MENU_CATEGORY_SLUG", "module"))

    # Menu principal
    if '>' in node_text:
        top_level_menu = slugify(node_text.split('>')[0].strip())
    else:
        top_level_menu = slugify(node_text.strip())

    # Nom de l'écran (tout le chemin du menu)
    screen_name = slugify(node_text)

    # Construction du chemin
    target_dir = SCREENSHOT_DIR / project / module_folder / top_level_menu
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    filename = f"{screen_name}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.warning("Captured screenshot for %s / %s at %s", module_name, node_text, target)
    dismiss_error_dialog(page, node_text)


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
    action_not_found_icon = page.locator("#x-auto-1525 > img")
    action_not_found_label = page.locator("#x-auto-1530").filter(
        has_text=re.compile(r"Action\s+Not\s+Found", re.IGNORECASE)
    )

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
    action_not_found_label = page.locator("#x-auto-1530").filter(
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
        page.locator("#x-auto-3806 button.x-btn-text").first,
        page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first,
        page.locator("//button[normalize-space()='OK']").first,
        page.get_by_role("button", name="OK"),
        page.locator("//*[@id='x-auto-3458']/tbody/tr[2]/td[2]/em/button").first,
        page.locator("//*[@id='x-auto-3457']/table/tbody/tr/td[1]/table/tbody/tr/td").first,
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


def find_tree_node(page, label: str, level: int):
    target_label = re.sub(r"\s+", " ", label.strip()).lower()
    target_words = target_label.split()
    prefix_len = min(3, len(target_words))
    target_prefix = " ".join(target_words[:prefix_len])
    treeitems = page.locator(f"div[role=\"treeitem\"][aria-level=\"{level}\"]")

    def _node_label(node) -> str:
        text_node = node.locator(".x-tree3-node-text").first
        if text_node.count():
            return re.sub(r"\s+", " ", (text_node.inner_text() or "").strip()).lower()
        return re.sub(r"\s+", " ", (node.inner_text() or "").strip()).lower()

    # Contains + restriction: first 3 words must match exactly.
    for idx in range(treeitems.count()):
        candidate = treeitems.nth(idx)
        try:
            node_text = _node_label(candidate)
            node_words = node_text.split()
            if len(node_words) < prefix_len:
                continue
            node_prefix = " ".join(node_words[:prefix_len])
            if node_prefix != target_prefix:
                continue
            if target_label in node_text:
                return candidate
        except Exception:
            continue

    return page.locator("__no_such_tree_node__")


def find_tree_node_with_scroll(page, label: str, level: int, max_scroll_attempts: int = 12):
    node = find_tree_node(page, label, level)
    if node.count():
        return node

    scroll_candidates = [
        page.locator("div[role='tree']:visible").first,
        page.locator("div.x-tree3:visible").first,
        page.locator("div.x-panel-body:has(div.x-tree3-root-node):visible").first,
    ]

    for scroll_target in scroll_candidates:
        if not scroll_target.count():
            continue
        for _ in range(max_scroll_attempts):
            try:
                scroll_target.evaluate(
                    """
                    (el) => {
                        const step = Math.max(120, Math.floor(el.clientHeight * 0.7));
                        el.scrollTop = Math.max(0, el.scrollTop + step);
                    }
                    """
                )
            except PlaywrightError:
                break
            page.wait_for_timeout(120)
            node = find_tree_node(page, label, level)
            if node.count():
                return node

    return page.locator("__no_such_tree_node__")


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
            if candidate.count():
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
    # Keep the same screenshot folder convention as other captures.
    script_name = os.path.basename(sys.argv[0]).lower()
    if script_name.endswith(".py"):
        script_name = script_name[:-3]
    if script_name.startswith("non_regression_"):
        project = script_name.replace("non_regression_", "").upper()
    else:
        project = "Other"

    module_folder = slugify(module_name)
    top_level_menu = slugify(path_label.split(">")[0].strip()) if ">" in path_label else slugify(path_label)
    target_dir = SCREENSHOT_DIR / project / module_folder / top_level_menu
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    filename = f"save_ok_{slugify(path_label)}_{timestamp}.png"
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.info("Captured save OK screenshot for %s at %s", path_label, target)


def capture_execute_search_popup_screenshot(page, module_name: str, path_label: str) -> None:
    script_name = os.path.basename(sys.argv[0]).lower()
    if script_name.endswith(".py"):
        script_name = script_name[:-3]
    if script_name.startswith("non_regression_"):
        project = script_name.replace("non_regression_", "").upper()
    else:
        project = "Other"

    module_folder = slugify(module_name)
    top_level_menu = slugify(path_label.split(">")[0].strip()) if ">" in path_label else slugify(path_label)
    target_dir = SCREENSHOT_DIR / project / module_folder / top_level_menu
    target_dir.mkdir(parents=True, exist_ok=True)

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
        ("#x-auto-3806 button.x-btn-text", "exact"),
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
    # Wait for edit panel controls to be rendered; some screens are slower after Edit click.
    save_button = None
    save_candidates = [
        page.locator(SAVE_BUTTON_SELECTOR).first,
        page.locator("#Component_PAGE_FORM_0_save_null").first,
        page.locator("button.x-btn-text").filter(has_text=re.compile(r"save|sauveg", re.IGNORECASE)).first,
    ]
    for _ in range(20):
        for candidate in save_candidates:
            try:
                if candidate.count() and candidate.is_visible():
                    save_button = candidate
                    break
            except PlaywrightError:
                continue
        if save_button is not None:
            break
        page.wait_for_timeout(300)

    if save_button is None:
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


def login(page) -> bool:
    logging.info("Navigating to login entry point")
    page.goto(LOGIN_ENTRY, wait_until="domcontentloaded")

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

    if not _submit_credentials(page):
        return False

    # Keycloak can close the original tab/page and continue on a new one.
    page = get_alive_page(page)

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

    logging.info("Login submitted (auth=%s, module=%s)", AUTH_TYPE, LOGIN_ENTRY)
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
        # Always check for max screens popup after each node interaction
        handle_max_screens_popup(page)

        # Now traverse the tree nodes for this path
        for child_index, segment in enumerate(path[1:], start=1):
            page = ensure_alive_page(page)
            if page is None:
                logging.error("No alive page while traversing %s; aborting traversal.", path_label)
                return

            level = child_index + 1
            prefix = tuple(path[: child_index + 1])
            node_is_leaf = prefix not in parent_prefixes
            node = find_tree_node_with_scroll(page, segment, level)
            try:
                if not node.count():
                    # Retry a few times because tree content can load lazily after tab click.
                    found = False
                    for _ in range(4):
                        page.wait_for_timeout(500)
                        node = find_tree_node_with_scroll(page, segment, level)
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
                node = find_tree_node_with_scroll(page, segment, level)
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
                if node_is_leaf:
                    node.click(force=True, timeout=4000)
                else:
                    if not already_expanded:
                        node.dblclick(force=True, timeout=5000)
                        expanded_nodes.add(prefix)
                    else:
                        node.click(force=True, timeout=4000)
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                logging.info("Failed to interact with %s, trying fallback click: %s", segment, exc)
                node = find_tree_node_with_scroll(page, segment, level)
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
                    node.click(force=True, timeout=4000)
                    if not node_is_leaf and not already_expanded:
                        page.keyboard.press("ArrowRight")
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
                                    execute_button.first.click(timeout=4000)
                                    logging.info("Execute Search clicked for %s", path_label)
                                except PlaywrightTimeoutError:
                                    try:
                                        execute_button.first.click(force=True, timeout=4000)
                                        logging.info("Execute Search clicked (force fallback) for %s", path_label)
                                    except PlaywrightTimeoutError:
                                        logging.warning("Execute Search click timed out for %s", path_label)
                                        capture_failure(page, top_level, path_label, always=True)
                                        raise PlaywrightTimeoutError("Execute Search could not be clicked")
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
        page = context.new_page()
        try:
            if not login(page):
                logging.error("Login failed, stopping execution.")
                return
            page = get_alive_page(page)
            if page.is_closed():
                logging.error("No alive page available after login.")
                return
            if menu_paths:
                traverse_menu_paths(page, menu_paths)
            else:
                logging.error("No menu paths loaded from %s; strict ordered execution requires the txt file.", MENU_PATH_FILE)
                return
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
