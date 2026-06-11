# Imports
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

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
            capture_failure(page, module_name, path_label)
            return
        grid_row = page.locator(PERIODE_TRADABLE_ASSET_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Periode Tradable Asset lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Periode Tradable Asset row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Periode Tradable Asset lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label)

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
            capture_failure(page, module_name, path_label)
            return
        grid_row = page.locator(PERIODE_OWNER_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Periode Owner lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Periode Owner row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Periode Owner lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label)
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
            capture_failure(page, module_name, path_label)
            return
        grid_row = page.locator(TRADABLE_ASSET_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Tradable Asset lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Tradable Asset row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Tradable Asset lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label)
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
            capture_failure(page, module_name, path_label)
            return
        grid_row = page.locator(OWNER_GRID_ROW_SELECTOR).first
        if not grid_row.count():
            logging.warning("Owner lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label)
            return
        try:
            grid_row.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Owner row double-click timed out for %s", path_label)
            grid_row.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Owner lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label)
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)

LOGIN_ENTRY = os.getenv("MODULE_URL", "http://10.1.146.163:9080/MegaCommon/WebApp.html")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/BMCE/Common/bmce_common.txt"))
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "ADMINBMCE")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "1234")
AUTH_DOMAIN = os.getenv("AUTH_DOMAIN", "BMCE BANK")
AUTH_TYPE = os.getenv("AUTH_TYPE", "standard").strip().lower()
PROJECT_SLUG = os.getenv("PROJECT_SLUG", "bmce")
MENU_CATEGORY_SLUG = os.getenv("MENU_CATEGORY_SLUG", "")

MENU_TABS = [
    "Referentiel",
    "Position",
    "Facturation",
    "Fiscalite",
    "Parametrage",
    "Rapport",
    "Report",
]

VIEW_OPTION_PATTERN = re.compile(r"(?:Voir|View|Consulter)", re.IGNORECASE)
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
SUCCESS_MESSAGE_PATTERN = re.compile(r"(saved|sauvegard)", re.IGNORECASE)
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
BMCE_RESULT_ZONE_SELECTOR = "div[id*='Component_PAGE_FORM_1_DataTable_'][id$='_PalmyraGrid']:visible"
BMCE_RESULT_ZONE_FIRST_ROW_SELECTOR = "div[id*='Component_PAGE_FORM_1_DataTable_'][id$='_PalmyraGrid']:visible tr[id*='_PalmyraGrid_0']:visible"
BMCE_SEARCH_VIEW_CONTAINER_SELECTOR = "div.x-grid3-viewport"
BMCE_EXECUTE_FIRST_ROW_SELECTOR = "tr[id*='Component_PAGE_FORM_1_DataTable_'][id*='_PalmyraGrid_0']"
BMCE_RESULT_ROW_DYNAMIC_SELECTOR = "tr[id*='PalmyraGrid_'][id$='_0']"
BMCE_RESULT_ROW_SELECTOR = "[id$='PalmyraGrid_0']"
BMCE_FIRST_ROW_FALLBACK_SELECTOR = "div.x-grid3-row"
AWB_SEARCH_BUTTON_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[1]/div[1]/div/table/tbody/tr/td[3]/div"
AWB_SEARCH_VIEW_CONTAINER_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[2]/div[2]/div[1]/div/div/div[2]/div[1]/div"
AWB_FIRST_ROW_JS_CSS = "#Component_PAGE_FORM_1_DataTable_138_PalmyraGrid_x-auto-815"
AWB_RESULT_ROW_DYNAMIC_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div[15]/div[2]/div[2]/div[1]/div/div/div[2]/div[1]/div/div[1]/div[1]/div[2]/div/div[1]"
AWB_RESULT_ROW_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[2]/div[2]/div[1]/div/div/div[2]/div[1]/div/div[1]/div[1]/div[2]/div/div[1]/table/tbody/tr"
AWB_RESULT_ROW_AFTER_EXECUTE_XPATH = "//*[@id='Component_PAGE_FORM_1_DataTable_138_PalmyraGrid_0']"
AWB_VIEW_OPTION_XPATH = "/html/body/div[10]/div/div/a"
AWB_RETURN_AFTER_VIEW_XPATH = "/html/body/div[2]/div/div[3]/div[2]/div/div[3]/div[1]/div/table/tbody/tr/td[2]/div"
AWB_CLOSE_TAB_AFTER_VIEW_XPATH = "/html/body/div[2]/div/div[3]/div[1]/div[1]/ul/li[1]/a[1]"
VIEW_RETURN_SELECTOR = "#Component_PAGE_FORM_2_return_null"
SAVE_BUTTON_SELECTOR = "#Component_PAGE_FORM_2_save_null"
DEFAULT_VIEWPORT = {"width": 1366, "height": 768}

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    return cleaned.strip("_").lower() or "node"


def build_screenshot_filename(node_text: str, timestamp: int) -> str:
    # Keep file names short to stay under Windows path-length limits.
    slug = slugify(node_text)
    max_slug_len = 90
    return f"{slug[:max_slug_len]}_{timestamp}.png"


def capture_failure(page, module_name: str, node_text: str, *, always: bool = False) -> None:
    if not always and not failure_indicators_present(page):
        logging.info("Skipping screenshot for %s / %s because no error indicators were found", module_name, node_text)
        return

    # Use environment variables set by PowerShell launcher
    # PROJECT: AWB, BMCE, CDG (uppercase)
    # MODULE: MegaCommon, MegaCor, etc. (title case -> lowercase)
    project_slug = os.getenv("PROJECT_SLUG", "bmce")
    module_slug = slugify(os.getenv("MENU_CATEGORY_SLUG", "module"))

    # node_text is usually a ' > ' joined path, so split and take the first part as top-level menu
    if '>' in node_text:
        top_level_menu = slugify(node_text.split('>')[0].strip())
    else:
        top_level_menu = slugify(node_text.strip())

    # Build directory path: screenshots/PROJECT/module/top_level_menu
    # Example: screenshots/BMCE/megacommon/accounting
    target_dir = SCREENSHOT_DIR / project_slug / module_slug / top_level_menu
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    filename = build_screenshot_filename(node_text, timestamp)
    target = target_dir / filename
    page.screenshot(path=str(target), full_page=True)
    logging.warning("Captured screenshot for %s / %s at %s", module_name, node_text, target)
    dismiss_error_dialog(page, node_text)


def failure_indicators_present(page) -> bool:
    try:
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
    except PlaywrightError:
        return False

    return False


def dismiss_error_dialog(page, path_label: str) -> None:
    def click_force(target):
        try:
            target.click(force=True, timeout=4000)
            target.click(force=True, timeout=4000)
            page.wait_for_timeout(600)
        except PlaywrightTimeoutError:
            logging.warning("Unable to dismiss error dialog for %s", path_label)

    ok_targets = [
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
    clean_label = re.sub(r"\s+", " ", label.strip()).lower()
    target_words = clean_label.split()
    target_prefix_len = min(3, len(target_words))
    target_prefix = " ".join(target_words[:target_prefix_len])

    def _node_label(node) -> str:
        text_node = node.locator(".x-tree3-node-text").first
        if text_node.count():
            return re.sub(r"\s+", " ", (text_node.inner_text() or "").strip()).lower()
        return re.sub(r"\s+", " ", (node.inner_text() or "").strip()).lower()

    all_nodes = page.locator(f"div[role=\"treeitem\"][aria-level=\"{level}\"]")

    # Contains + restriction: first 3 words must match exactly.
    for idx in range(all_nodes.count()):
        node = all_nodes.nth(idx)
        try:
            node_text = _node_label(node)
            node_words = node_text.split()
            if len(node_words) < target_prefix_len:
                continue
            node_prefix = " ".join(node_words[:target_prefix_len])
            if node_prefix != target_prefix:
                continue
            if clean_label in node_text:
                return node
        except Exception:
            continue

    return page.locator("__no_such_tree_node__")


def _is_target_closed_error(exc: Exception) -> bool:
    return "Target page, context or browser has been closed" in str(exc)


def reset_tree_scroll_to_top(page) -> None:
    scroll_candidates = [
        page.locator("div[role='tree']:visible").first,
        page.locator("div.x-tree3:visible").first,
        page.locator("div.x-panel-body:has(div.x-tree3-root-node):visible").first,
    ]
    for target in scroll_candidates:
        try:
            if not target.count():
                continue
            target.evaluate("el => { el.scrollTop = 0; }")
            page.wait_for_timeout(80)
            return
        except PlaywrightError:
            continue


def find_tree_node_with_scroll(page, label: str, level: int, max_scroll_attempts: int = 14):
    try:
        node = find_tree_node(page, label, level)
        if node.count():
            return node
    except PlaywrightError as exc:
        if _is_target_closed_error(exc):
            logging.error("Page/context closed while searching tree node '%s' at level %s", label, level)
            return page.locator("__no_such_tree_node__")
        raise

    scroll_candidates = [
        page.locator("div[role='tree']:visible").first,
        page.locator("div.x-tree3:visible").first,
        page.locator("div.x-panel-body:has(div.x-tree3-root-node):visible").first,
    ]

    for scroll_target in scroll_candidates:
        try:
            if not scroll_target.count():
                continue
        except PlaywrightError as exc:
            if _is_target_closed_error(exc):
                logging.error("Page/context closed while reading tree container for '%s'", label)
                return page.locator("__no_such_tree_node__")
            continue

        # First pass: from top to bottom.
        try:
            scroll_target.evaluate("el => { el.scrollTop = 0; }")
        except PlaywrightError:
            pass
        for _ in range(max_scroll_attempts):
            try:
                node = find_tree_node(page, label, level)
                if node.count():
                    return node
                scroll_target.hover(timeout=1200)
                page.mouse.wheel(0, 520)
                page.wait_for_timeout(120)
            except PlaywrightError as exc:
                if _is_target_closed_error(exc):
                    logging.error("Page/context closed while scrolling to find '%s'", label)
                    return page.locator("__no_such_tree_node__")
                break

        # Second pass: from bottom to top.
        for _ in range(max_scroll_attempts):
            try:
                node = find_tree_node(page, label, level)
                if node.count():
                    return node
                scroll_target.hover(timeout=1200)
                page.mouse.wheel(0, -520)
                page.wait_for_timeout(120)
            except PlaywrightError as exc:
                if _is_target_closed_error(exc):
                    logging.error("Page/context closed while reverse-scrolling to find '%s'", label)
                    return page.locator("__no_such_tree_node__")
                break

    return node


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
        # Keep row selection stable: do not toggle off an already-selected row.
        if not checkbox.is_checked():
            checkbox.click(force=True, timeout=4000)
    except PlaywrightTimeoutError:
        logging.info("Inline checkbox click timed out for %s", path_label)
    return checkbox


def get_row_operations_target(result_row):
    cell = result_row.locator("td.x-grid3-td-rowOperations").first
    return cell if cell.count() else result_row


def close_work_window(page, path_label: str) -> None:
    close_candidates = [
        page.locator(f"xpath={AWB_CLOSE_TAB_AFTER_VIEW_XPATH}").first,
        page.locator("a.x-tab-strip-close").first,
        page.locator("div.x-tool-close").first,
        page.locator("button[aria-label='Close']").first,
    ]
    for target in close_candidates:
        if not target.count():
            continue
        try:
            target.click(force=True, timeout=3500)
            page.wait_for_timeout(500)
            return
        except PlaywrightTimeoutError:
            logging.info("Close candidate timed out for %s", path_label)


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

    if click_edit_context_option(page, module_name, path_label):
        handle_edit_panel(page, module_name, path_label)
    else:
        logging.info("Edit option not available for %s", path_label)
        page.wait_for_timeout(800)


def handle_error_dialog(page, module_name: str, path_label: str) -> bool:
    try:
        page.wait_for_timeout(600)
        if not failure_indicators_present(page):
            return False
    except PlaywrightError:
        return False

    logging.warning("Detected error dialog for %s", path_label)
    try:
        capture_failure(page, module_name, path_label)
    except PlaywrightError:
        return False
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


def get_first_visible_search_row(page):
    candidates = [
        page.locator(BMCE_RESULT_ZONE_FIRST_ROW_SELECTOR).first,
        page.locator(BMCE_EXECUTE_FIRST_ROW_SELECTOR).first,
        page.locator("tr[id*='PalmyraGrid_'][id$='_0']").first,
        page.locator("[id$='PalmyraGrid_0']").first,
        page.locator(f"xpath={AWB_RESULT_ROW_DYNAMIC_XPATH}").first,
        page.locator(f"xpath={AWB_RESULT_ROW_XPATH}").first,
        page.locator(AWB_FIRST_ROW_JS_CSS).first,
        page.locator(BMCE_RESULT_ROW_DYNAMIC_SELECTOR).first,
        page.locator(BMCE_RESULT_ROW_SELECTOR).first,
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


def right_click_row_after_execute(page, module_name: str, path_label: str):
    # Mirror AWB timing: allow execute popups to surface, then dismiss if present.
    page.wait_for_timeout(1000)
    dismiss_error_dialog(page, path_label)
    page.wait_for_timeout(800)

    try:
        page.wait_for_selector(BMCE_RESULT_ZONE_SELECTOR, state="visible", timeout=6000)
    except PlaywrightTimeoutError:
        logging.warning("Result zone container did not appear after execute for %s", path_label)

    row_selectors = [
        BMCE_RESULT_ZONE_FIRST_ROW_SELECTOR,
        BMCE_EXECUTE_FIRST_ROW_SELECTOR,
        f"xpath={AWB_RESULT_ROW_XPATH}",
        f"xpath={AWB_RESULT_ROW_AFTER_EXECUTE_XPATH}",
        "[id$=PalmyraGrid_0]",
        BMCE_RESULT_ROW_DYNAMIC_SELECTOR,
        BMCE_RESULT_ROW_SELECTOR,
        BMCE_FIRST_ROW_FALLBACK_SELECTOR,
    ]

    for selector in row_selectors:
        try:
            page.wait_for_selector(selector, state="visible", timeout=6000)
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


def bmce_view_then_edit_flow(page, module_name: str, path_label: str) -> bool:
    container = page.locator(BMCE_RESULT_ZONE_SELECTOR).last
    if not container.count():
        container = page.locator(BMCE_SEARCH_VIEW_CONTAINER_SELECTOR).first
    if container.count():
        try:
            container.wait_for(timeout=8000)
        except PlaywrightTimeoutError:
            logging.warning("Search view container did not appear for %s", path_label)
            capture_failure(page, module_name, path_label)
            return False

    if not container.count():
        awb_container = page.locator(f"xpath={AWB_SEARCH_VIEW_CONTAINER_XPATH}").first
        if awb_container.count():
            container = awb_container

    first_row_ready = False
    for selector in [
        BMCE_RESULT_ZONE_FIRST_ROW_SELECTOR,
        BMCE_EXECUTE_FIRST_ROW_SELECTOR,
        BMCE_RESULT_ROW_DYNAMIC_SELECTOR,
        BMCE_RESULT_ROW_SELECTOR,
        BMCE_FIRST_ROW_FALLBACK_SELECTOR,
    ]:
        try:
            page.wait_for_selector(selector, timeout=4000)
            first_row_ready = True
            break
        except PlaywrightTimeoutError:
            continue

    if not first_row_ready:
        logging.warning("No first row selector appeared for %s", path_label)
        capture_failure(page, module_name, path_label)
        return False

    for attempt in range(2):
        try:
            if container.count():
                container.scroll_into_view_if_needed()
                container.click(force=True, timeout=4000)

            row = get_first_visible_search_row(page)
            if row is None:
                raise PlaywrightTimeoutError("First visible search row not found")

            row.scroll_into_view_if_needed()
            row.click(force=True, timeout=4000)
            page.wait_for_timeout(200)
            row.click(button="right", force=True, timeout=4000)
            logging.info("First visible row selected and right-clicked for %s (attempt=%d)", path_label, attempt + 1)
            break
        except PlaywrightTimeoutError:
            if attempt == 1:
                logging.warning("Failed right-click on first row for %s", path_label)
                capture_failure(page, module_name, path_label)
                return False
            page.wait_for_timeout(400)

    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(400)

    # Requirement: after first right-click, require View; Edit is optional.
    has_view = page.locator(f"xpath={AWB_VIEW_OPTION_XPATH}").first.count() > 0 or (
        page.locator(".x-menu-list .x-menu-item").filter(has_text=VIEW_OPTION_PATTERN).first.count() > 0
    )
    has_edit = page.locator(".x-menu-list .x-menu-item").filter(has_text=EDIT_OPTION_PATTERN).first.count() > 0
    if not has_view:
        logging.warning("View option missing after first right-click for %s (view=%s, edit=%s)", path_label, has_view, has_edit)
        capture_failure(page, module_name, path_label)
        close_work_window(page, path_label)
        return False

    if not has_edit:
        logging.info("Edit option absent for %s; continuing with View-only workflow", path_label)

    view_option = page.locator(f"xpath={AWB_VIEW_OPTION_XPATH}").first
    if view_option.count():
        try:
            view_option.click(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.warning("View click timed out for %s", path_label)
            capture_failure(page, module_name, path_label)
            return False
    elif not click_view_context_option(page, module_name, path_label):
        logging.warning("View option not available for %s", path_label)
        capture_failure(page, module_name, path_label)
        return False

    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(600)

    return_btn = page.locator(f"xpath={AWB_RETURN_AFTER_VIEW_XPATH}").first
    if not return_btn.count():
        return_btn = page.locator(VIEW_RETURN_SELECTOR).first
    if return_btn.count():
        try:
            return_btn.click(force=True, timeout=4000)
            logging.info("Return clicked for %s", path_label)
        except PlaywrightTimeoutError:
            logging.warning("Return click timed out for %s", path_label)
            capture_failure(page, module_name, path_label)
            return False
    else:
        logging.warning("Return button not found for %s", path_label)
        capture_failure(page, module_name, path_label)
        return False

    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(500)

    row = get_first_visible_search_row(page)
    if row is None:
        logging.warning("No first row after return for %s", path_label)
        return False

    for attempt in range(2):
        try:
            if container.count():
                container.scroll_into_view_if_needed()
                container.click(force=True, timeout=4000)
            row = get_first_visible_search_row(page)
            if row is None:
                raise PlaywrightTimeoutError("First visible search row not found after return")
            row.scroll_into_view_if_needed()
            row.click(force=True, timeout=4000)
            page.wait_for_timeout(200)
            row.click(button="right", force=True, timeout=4000)
            logging.info("Second right-click done for %s (attempt=%d)", path_label, attempt + 1)
            break
        except PlaywrightTimeoutError:
            if attempt == 1:
                logging.warning("Second right-click failed for %s", path_label)
                capture_failure(page, module_name, path_label)
                return False
            page.wait_for_timeout(400)

    handle_error_dialog(page, module_name, path_label)
    page.wait_for_timeout(400)

    if click_edit_context_option(page, module_name, path_label):
        handle_edit_panel(page, module_name, path_label)
        return True

    logging.info("Edit option absent after second right-click for %s; treated as non-error", path_label)
    close_work_window(page, path_label)
    return True


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
            capture_failure(page, module_name, path_label)
            return

        grid_cell = page.locator(CLIENT_SEC_ACCOUNT_GRID_CELL_SELECTOR).first
        if not grid_cell.count():
            logging.warning("Client Sec Account lookup row missing for %s", path_label)
            capture_failure(page, module_name, path_label)
            return

        try:
            grid_cell.dblclick(force=True, timeout=4000)
        except PlaywrightTimeoutError:
            logging.info("Client Sec Account row double-click timed out for %s", path_label)
            grid_cell.click(force=True, timeout=4000)
        page.wait_for_timeout(600)
    except PlaywrightTimeoutError:
        logging.warning("Client Sec Account lookup interaction timed out for %s", path_label)
        capture_failure(page, module_name, path_label)


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

    success_popup = page.locator("div.x-window-plain.x-window-dlg.x-window.x-component")
    success_message = page.locator("span.ext-mb-text").filter(has_text=SUCCESS_MESSAGE_PATTERN)
    if success_popup.count() and success_message.count():
        popup_ok_button = success_popup.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first
        if not popup_ok_button.count():
            popup_ok_button = page.locator("//*[@id='x-auto-1299']/tbody/tr[2]/td[2]/em/button").first
        try:
            popup_ok_button.click(force=True, timeout=4000)
            logging.info("Save notification OK clicked for %s", path_label)
            page.wait_for_timeout(600)
        except PlaywrightTimeoutError:
            logging.warning("Unable to click OK on save notification for %s", path_label)
            capture_failure(page, module_name, path_label)
    elif success_message.count():
        ok_button = page.locator("button.x-btn-text").filter(has_text=OK_BUTTON_PATTERN).first
        if ok_button.count():
            try:
                ok_button.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
            except PlaywrightTimeoutError:
                logging.warning("Unable to dismiss success dialog for %s", path_label)
                capture_failure(page, module_name, path_label)
    else:
        logging.warning("Save confirmation missing for %s", path_label)
        capture_failure(page, module_name, path_label)

    # Requirement: after Save -> OK, close the window.
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
            "input[name='domain']",
            "input[id*='domain']",
        ],
    )
    if domain_field is not None and AUTH_DOMAIN:
        domain_key = AUTH_DOMAIN.strip().lower()
        selected = False

        try:
            tag_name = (domain_field.evaluate("el => el.tagName") or "").lower()
        except Exception:
            tag_name = ""

        if tag_name == "select":
            try:
                domain_field.select_option(label=AUTH_DOMAIN)
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
                    logging.debug("Domain options loading timed out for %s", AUTH_DOMAIN)

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
                    logging.debug("Domain explicit option-click path timed out for %s", AUTH_DOMAIN)
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
            logging.info("Selected domain %s", AUTH_DOMAIN)
        else:
            logging.warning("Domain %s not found in login form options", AUTH_DOMAIN)

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


def login(page) -> bool:
    logging.info("Navigating to login entry point")
    try:
        page.goto(LOGIN_ENTRY, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        logging.error("Unable to reach login entry %s: %s", LOGIN_ENTRY, exc)
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

    if not _submit_credentials(page):
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
        if not path:
            logging.warning("Skipping empty path at index %d", index + 1)
            continue

        top_level = path[0].strip()
        button = _find_top_level_button(page, top_level)
        if button is not None:
            button.click()
            reset_tree_scroll_to_top(page)
        else:
            logging.warning("Top level tab %s not found; continuing with current context", top_level)

        path_label = " > ".join(path)
        normalized_path = tuple(segment.strip().lower() for segment in path)
        logging.info("Traversing path %d/%d: %s", index + 1, total_paths, path_label)
        position_filter_mode = get_position_filter_mode(path)
        page.wait_for_timeout(1200)

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

        # Now traverse the tree nodes for this path
        for child_index, segment in enumerate(path[1:], start=1):
            level = child_index + 1
            prefix = tuple(path[: child_index + 1])
            node_is_leaf = prefix not in parent_prefixes

            # --- Always expand parent nodes to make children visible ---
            # Expand all ancestors up to this node
            for ancestor_level in range(2, level):
                ancestor_label = path[ancestor_level - 1]
                ancestor_prefix = tuple(path[:ancestor_level])
                if ancestor_prefix not in expanded_nodes:
                    ancestor_node = find_tree_node_with_scroll(page, ancestor_label, ancestor_level)
                    if ancestor_node.count():
                        try:
                            ancestor_node.scroll_into_view_if_needed(timeout=4000)
                            ancestor_node.dblclick(timeout=4000)
                            expanded_nodes.add(ancestor_prefix)
                            page.wait_for_timeout(400)
                        except PlaywrightTimeoutError:
                            logging.warning("Could not expand ancestor %s at level %s", ancestor_label, ancestor_level)

            # Now scroll and click the target node
            node = find_tree_node_with_scroll(page, segment, level)
            if not node.count():
                logging.warning("Tree node %s at level %s not found", segment, level)
                break

            try:
                node.scroll_into_view_if_needed(timeout=5000)
            except PlaywrightTimeoutError:
                logging.warning("Tree node %s at level %s could not be scrolled into view", segment, level)
            already_expanded = prefix in expanded_nodes
            try:
                if node_is_leaf:
                    node.click(timeout=4000)
                else:
                    if not already_expanded:
                        node.dblclick(timeout=5000)
                        expanded_nodes.add(prefix)
                    else:
                        node.click(timeout=4000)
            except (PlaywrightTimeoutError, PlaywrightError):
                logging.info("Failed to interact with %s, falling back to visible click", segment)
                fallback_node = page.locator(
                    f"div[role=\"treeitem\"][aria-level=\"{level}\"]:visible"
                ).filter(has_text=segment).first
                if fallback_node.count():
                    try:
                        fallback_node.scroll_into_view_if_needed(timeout=3000)
                    except PlaywrightTimeoutError:
                        logging.warning("Fallback tree node %s at level %s could not be scrolled into view", segment, level)
                    fallback_node.click(timeout=4000)
                else:
                    node.click(timeout=4000)
            finally:
                handle_error_dialog(page, top_level, path_label)

            try:
                page.wait_for_timeout(1500)
            except PlaywrightError as exc:
                if "Target page, context or browser has been closed" in str(exc):
                    logging.error("Page/context closed while traversing %s; stopping traversal cleanly.", path_label)
                    return
                raise

            if node_is_leaf:
                click_search_button_if_available(page, top_level, path_label)

            if node_is_leaf:
                table = page.locator("table.x-form-search")
                if table.count():
                    table_root = table.first
                    result_row = table_root.locator("tbody tr").first
                    if result_row.count():
                        try:
                            result_row.scroll_into_view_if_needed()
                            result_row.click(timeout=4000)
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
                                page.wait_for_timeout(800)
                                try:
                                    page.wait_for_selector(BMCE_RESULT_ZONE_SELECTOR, state="visible", timeout=8000)
                                except PlaywrightTimeoutError:
                                    logging.warning(
                                        "Result zone container did not appear after execute for %s",
                                        path_label,
                                    )
                                try:
                                    page.wait_for_selector("div.x-grid3-row", timeout=8000)
                                except PlaywrightTimeoutError:
                                    logging.warning(
                                        "Grid rows did not appear after execute for %s",
                                        path_label,
                                    )
                                handle_error_dialog(page, top_level, path_label)
                                page.wait_for_timeout(800)
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
                                grid_row_locator = page.locator(BMCE_RESULT_ZONE_FIRST_ROW_SELECTOR).first
                                if not grid_row_locator.count():
                                    grid_row_locator = page.locator(BMCE_EXECUTE_FIRST_ROW_SELECTOR).first
                                if not grid_row_locator.count():
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
                            right_clicked_row = right_click_row_after_execute(page, top_level, path_label)
                            if right_clicked_row is not None:
                                result_row = right_clicked_row
                            if not bmce_view_then_edit_flow(page, top_level, path_label):
                                capture_failure(page, top_level, path_label)
                                continue
                        except PlaywrightTimeoutError as exc:
                            logging.warning("Context menu interaction failed for %s: %s", path_label, exc)
                            capture_failure(page, top_level, path_label, always=True)
                    else:
                        logging.warning("No result rows found for %s", path_label)
                        capture_failure(page, top_level, path_label)
                else:
                    # Fallback path: some BMCE screens render results directly in PalmyraGrid without table.x-form-search.
                    result_zone = page.locator(BMCE_RESULT_ZONE_SELECTOR).last
                    if result_zone.count():
                        try:
                            result_zone.wait_for(state="visible", timeout=6000)
                            try:
                                zone_id = result_zone.get_attribute("id")
                            except Exception:
                                zone_id = None
                            if zone_id:
                                logging.info("Detected result zone %s for %s", zone_id, path_label)

                            grid_row_locator = result_zone.locator("tr[id*='_PalmyraGrid_0']").first
                            if not grid_row_locator.count():
                                grid_row_locator = page.locator(BMCE_RESULT_ZONE_FIRST_ROW_SELECTOR).first
                            if not grid_row_locator.count():
                                grid_row_locator = page.locator(BMCE_EXECUTE_FIRST_ROW_SELECTOR).first

                            if not grid_row_locator.count():
                                logging.warning("No first result row found inside result zone for %s", path_label)
                                capture_failure(page, top_level, path_label)
                            else:
                                result_row = grid_row_locator
                                activate_row_checkbox(result_row, path_label)
                                right_clicked_row = right_click_row_after_execute(page, top_level, path_label)
                                if right_clicked_row is not None:
                                    result_row = right_clicked_row
                                if not bmce_view_then_edit_flow(page, top_level, path_label):
                                    capture_failure(page, top_level, path_label)
                        except PlaywrightTimeoutError:
                            logging.warning("Result zone exists but is not visible/ready for %s", path_label)
                            capture_failure(page, top_level, path_label)
                    else:
                        capture_failure(page, top_level, path_label)

                close_button = page.locator("a.x-tab-strip-close")
                if close_button.count():
                    close_button.first.click()
                    page.wait_for_timeout(600)

            # Collapse only after this path has been fully processed, and only if
            # no remaining future path needs the expanded ancestors.
            collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)


def _find_top_level_button(page, label: str):
    exact_button = page.get_by_role("button", name=label)
    if exact_button.count():
        return exact_button.first

    trimmed_label = label.strip()
    for candidate in page.get_by_role("button").all():
        try:
            candidate_text = candidate.inner_text().strip()
        except PlaywrightError:
            continue
        if candidate_text == trimmed_label or candidate_text.lower() == trimmed_label.lower():
            return candidate

    return None

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
                logging.error("Login failed for %s. Aborting menu traversal.", LOGIN_ENTRY)
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
