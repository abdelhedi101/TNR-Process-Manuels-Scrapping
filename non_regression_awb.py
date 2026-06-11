# Imports
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

LOGIN_ENTRY = os.getenv("MODULE_URL", "http://10.1.140.244:9080/MegaCommon/login.jsp")
MENU_PATH_FILE = Path(os.getenv("MENU_PATH_FILE", "Projects/AWB/common/awb_common.txt"))
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
RECYCLER_REPROCESS_PATHS = {
    (
        "notification",
        "reprocess",
        "recycler aoe",
    ),
    (
        "notification",
        "reprocess",
        "recycler arc",
    ),
    (
        "notification",
        "reprocess",
        "recycler arr",
    ),
    (
        "notification",
        "reprocess",
        "recycler mrb",
    ),
    (
        "notification",
        "reprocess",
        "recycler mrl",
    ),
    (
        "notification",
        "reprocess",
        "recycler mt54x",
    ),
    (
        "notification",
        "reprocess",
        "recycler rcq",
    ),
    (
        "notification",
        "reprocess",
        "recycler rmq",
    ),
    (
        "notification",
        "reprocess",
        "recycler rsm",
    ),
}

RECYCLER_CLASSES_POPUP_SELECTOR = "div.x-window-plain.x-window-dlg.x-window.x-component"
CLIENT_SEC_ACCOUNT_FIELD_SELECTOR = "#Field_ComponentclientSecAccount"
CLIENT_SEC_ACCOUNT_INPUT_SELECTOR = "input[name='Component_PAGE_FORM_0_clientSecAccount']"
CLIENT_SEC_ACCOUNT_GRID_CELL_SELECTOR = "td.x-grid3-col-client"
CLOSE_ONLY_MENU_PATHS = {
    ("paramètrage", "configuration technique", "simulation ebanking"),
    ("parametrage", "configuration technique", "simulation ebanking"),
}
SAVE_ONLY_MENU_PATHS = {
    ("paramètrage", "configuration générale"),
    ("parametrage", "configuration generale"),
}


def get_position_filter_mode(path: List[str]) -> Optional[Dict[str, bool]]:
    if not path:
        return None
    normalized = tuple(segment.strip().lower() for segment in path)
    return POSITION_FILTER_PATHS.get(normalized)


def should_skip_recycler_auto_search(path: List[str]) -> bool:
    normalized = tuple(segment.strip().lower() for segment in path)
    return normalized in RECYCLER_REPROCESS_PATHS


def should_force_close_only(path: List[str]) -> bool:
    normalized = tuple(segment.strip().lower() for segment in path)
    return normalized in CLOSE_ONLY_MENU_PATHS


def should_force_save_only(path: List[str]) -> bool:
    normalized = tuple(segment.strip().lower() for segment in path)
    return normalized in SAVE_ONLY_MENU_PATHS


def run_close_only_menu_workflow(page, path_label: str) -> None:
    logging.info("Applying close-only workflow for %s", path_label)
    close_work_window(page, path_label)


def run_save_only_menu_workflow(page, module_name: str, path_label: str) -> None:
    save_button = page.locator("#Component_PAGE_FORM_0_save_null").first
    if not save_button.count():
        save_button = page.locator(SAVE_BUTTON_SELECTOR).first
    if not save_button.count():
        logging.warning("Save button not found for save-only menu %s", path_label)
        close_work_window(page, path_label)
        return
    try:
        save_button.click(force=True, timeout=4000)
        page.wait_for_timeout(500)
    except PlaywrightTimeoutError:
        logging.warning("Save click timed out for save-only menu %s", path_label)
        close_work_window(page, path_label)
        return
    error_found = handle_error_dialog(page, module_name, path_label)
    if not error_found:
        dismiss_save_success_popup_if_present(page, path_label)
    close_work_window(page, path_label)


def prepare_recycler_execute(page, path_label: str) -> None:
    try:
        page.evaluate(
            """
            () => {
                const activeElement = document.activeElement;
                if (activeElement && typeof activeElement.blur === 'function') {
                    activeElement.blur();
                }
            }
            """
        )
        page.wait_for_timeout(150)
    except PlaywrightError:
        logging.debug("Unable to blur active element before execute for %s", path_label)


def click_locator_like_manual(page, target, path_label: str, *, timeout: int = 4000) -> bool:
    try:
        box = target.bounding_box()
    except PlaywrightError:
        box = None

    if not box:
        logging.debug("No bounding box found for manual click on %s", path_label)
        return False

    try:
        click_x = box["x"] + (box["width"] / 2)
        click_y = box["y"] + (box["height"] / 2)
        page.mouse.move(click_x, click_y)
        page.wait_for_timeout(80)
        page.mouse.down()
        page.wait_for_timeout(80)
        page.mouse.up()
        page.wait_for_timeout(250)
        return True
    except PlaywrightError as exc:
        logging.debug("Manual mouse click failed for %s: %s", path_label, exc)
        return False


def find_execute_button(page):
    candidates = [
        page.locator(EXECUTE_CRITERIA_SELECTOR).first,
        page.locator("[id*='executeCriteria']").first,
        page.locator("button.x-btn-text").filter(has_text=re.compile(r"execute", re.IGNORECASE)).first,
        page.locator(".x-btn-text").filter(has_text=re.compile(r"execute", re.IGNORECASE)).first,
    ]
    for target in candidates:
        try:
            if target.count():
                return target
        except PlaywrightError:
            continue
    return None


def click_execute_search(page, path_label: str, recycler_mode: bool) -> bool:
    execute_target = find_execute_button(page)
    if execute_target is None:
        # Some screens render Execute Search late; retry briefly before failing.
        for _ in range(8):
            page.wait_for_timeout(250)
            execute_target = find_execute_button(page)
            if execute_target is not None:
                break

    if execute_target is None:
        logging.warning("Execute Search button not found for %s", path_label)
        return False

    if recycler_mode:
        prepare_recycler_execute(page, path_label)
        try:
            execute_target.evaluate("el => el.click()")
            page.wait_for_timeout(150)
            logging.info("Execute Search clicked (manual recycler mode) for %s", path_label)
            return True
        except PlaywrightError:
            pass

    try:
        # Direct DOM click avoids Playwright's auto-scrolling and keeps the page stable.
        execute_target.evaluate("el => el.click()")
        page.wait_for_timeout(150)
        logging.info("Execute Search clicked for %s", path_label)
        return True
    except PlaywrightError:
        try:
            execute_target.dispatch_event("click")
            page.wait_for_timeout(150)
            logging.info("Execute Search clicked (dispatch fallback) for %s", path_label)
            return True
        except PlaywrightError:
            logging.warning("Execute Search click timed out for %s", path_label)
            return False


def click_return_button_like_manual(page, path_label: str) -> bool:
    """Click Return using manual-like behavior to avoid automation-only popup side effects."""
    candidates = [
        page.locator(VIEW_RETURN_SELECTOR).first,
        page.locator(f"xpath={AWB_RETURN_AFTER_VIEW_XPATH}").first,
    ]

    for target in candidates:
        try:
            if not target.count():
                continue
        except PlaywrightError:
            continue

        try:
            target.scroll_into_view_if_needed(timeout=3000)
        except PlaywrightError:
            pass

        # Prefer plain click first (closest to manual process).
        try:
            target.click(timeout=3500)
            page.wait_for_timeout(350)
            return True
        except PlaywrightError:
            pass

        # Fallback to manual mouse sequence.
        if click_locator_like_manual(page, target, path_label, timeout=3500):
            return True

    return False

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

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)


def slugify(value: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    return cleaned.strip("_").lower() or "node"


def too_much_data_popup_present(page) -> bool:
    try:
        popup_by_xpath = page.locator(f"xpath={AWB_TOO_MUCH_DATA_XPATH}")
        if popup_by_xpath.count() and popup_by_xpath.filter(has_text=TOO_MUCH_DATA_PATTERN).count():
            return True
        if page.locator("span.ext-mb-text").filter(has_text=TOO_MUCH_DATA_PATTERN).count():
            return True
        return False
    except PlaywrightError:
        return False


def capture_failure(page, module_name: str, node_text: str, *, always: bool = False) -> None:
    try:
        if too_much_data_popup_present(page):
            logging.info("Skipping tooMuchDataFound popup for %s / %s", module_name, node_text)
            dismiss_error_dialog(page, node_text)
            return

        if not always and not failure_indicators_present(page):
            logging.info("Skipping screenshot for %s / %s because no error indicators were found", module_name, node_text)
            return

        # Use environment variables set by PowerShell launcher
        # PROJECT: AWB, BMCE, CDG (uppercase)
        # MODULE: MegaCommon, MegaCor, etc. (title case -> lowercase)
        project_slug = os.getenv("PROJECT_SLUG", "awb")
        module_slug = slugify(os.getenv("MENU_CATEGORY_SLUG", "module"))

        # node_text is usually a ' > ' joined path, so split and take the first part as top-level menu
        if '>' in node_text:
            top_level_menu = slugify(node_text.split('>')[0].strip())
        else:
            top_level_menu = slugify(node_text.strip())

        # Build directory path: screenshots/PROJECT/module/top_level_menu
        # Example: screenshots/AWB/megacommon/facturation
        target_dir = SCREENSHOT_DIR / project_slug / module_slug / top_level_menu
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        filename = f"{slugify(node_text)}_{timestamp}.png"
        target = target_dir / filename
        page.screenshot(path=str(target), full_page=True)
        logging.warning("Captured screenshot for %s / %s at %s", module_name, node_text, target)
        dismiss_error_dialog(page, node_text)
    except PlaywrightError:
        logging.debug("Page closed; skipping capture_failure for %s / %s", module_name, node_text)


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
    try:
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
    except PlaywrightError:
        logging.debug("Page closed before close_work_window for %s", path_label)


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


def find_tree_node_with_scroll(page, label: str, level: int, max_scroll_attempts: int = 25):
    """
    Look for a tree node, scrolling the tree panel both UP (to top first) and
    then DOWN progressively. This is required because after navigating deep
    into the tree, ancestor nodes (e.g. 'Entités' at level 2) can be scrolled
    out of view ABOVE the visible area — the previous "scroll down only" logic
    would mark them as SKIP even though they exist.
    """
    # 1) Quick check at current scroll position.
    node = find_tree_node(page, label, level)
    if node.count():
        try:
            node.scroll_into_view_if_needed(timeout=1500)
        except PlaywrightError:
            pass
        return node

    scroll_candidates_locators = [
        page.locator("div[role='tree']:visible").first,
        page.locator("div.x-tree3:visible").first,
        page.locator("div.x-panel-body:has(div.x-tree3-root-node):visible").first,
        page.locator("div.x-panel-body.x-panel-body-noheader:visible").first,
    ]

    scroll_targets = []
    seen = set()
    for cand in scroll_candidates_locators:
        try:
            if not cand.count():
                continue
            handle = cand.element_handle()
            if handle is None:
                continue
            key = id(handle)
            if key in seen:
                continue
            seen.add(key)
            scroll_targets.append(cand)
        except PlaywrightError:
            continue

    if not scroll_targets:
        return page.locator("__no_such_tree_node__")

    for scroll_target in scroll_targets:
        # 2) Reset scroll to TOP, then probe at every step downwards.
        try:
            scroll_target.evaluate("(el) => { el.scrollTop = 0; }")
        except PlaywrightError:
            continue
        page.wait_for_timeout(150)

        node = find_tree_node(page, label, level)
        if node.count():
            try:
                node.scroll_into_view_if_needed(timeout=1500)
            except PlaywrightError:
                pass
            return node

        # 3) Progressive downward scroll.
        last_scroll_top = -1
        for _ in range(max_scroll_attempts):
            try:
                current_top = scroll_target.evaluate(
                    """
                    (el) => {
                        const step = Math.max(80, Math.floor(el.clientHeight * 0.5));
                        el.scrollTop = el.scrollTop + step;
                        return el.scrollTop;
                    }
                    """
                )
            except PlaywrightError:
                break

            page.wait_for_timeout(120)
            node = find_tree_node(page, label, level)
            if node.count():
                try:
                    node.scroll_into_view_if_needed(timeout=1500)
                except PlaywrightError:
                    pass
                return node

            # Reached the bottom — stop scrolling this target.
            if current_top == last_scroll_top:
                break
            last_scroll_top = current_top

    return page.locator("__no_such_tree_node__")


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
    try:
        page.wait_for_timeout(600)
    except PlaywrightError:
        return False
    try:
        if not failure_indicators_present(page):
            return False
    except PlaywrightError:
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
                target.click(force=True, timeout=4000)
            except PlaywrightTimeoutError:
                target.click(timeout=4000)
            logging.info("Search clicked for %s", path_label)
            handle_error_dialog(page, module_name, path_label)
            page.wait_for_timeout(500)
            return True
        except PlaywrightTimeoutError:
            logging.info("Search candidate present but not clickable for %s", path_label)

    return False


def dismiss_ok_popup_if_present(page, path_label: str) -> bool:
    """Check if an OK popup is present and click it. Returns True if clicked, False otherwise."""
    try:
        logging.info("🔍 Searching for OK popup for %s (will retry for up to 6 seconds)", path_label)
        
        # Try for up to 6 seconds total
        start_time = time.time()
        max_wait = 6
        
        while time.time() - start_time < max_wait:
            # Strategy 1: Try the exact XPath provided by user
            exact_xpath = "/html/body/div[10]/div[2]/div[2]/div/div/div/div/div[1]/table/tbody/tr/td[1]/table/tbody/tr/td/table/tbody/tr[2]/td[2]/em/button"
            try:
                ok_button = page.locator(f"xpath={exact_xpath}").first
                if ok_button.count():
                    logging.info("✓ Found OK button via exact XPath")
                    try:
                        ok_button.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        logging.info("✅✅ OK popup dismissed (exact XPath) for %s", path_label)
                        return True
                    except Exception as e:
                        logging.debug("Failed to click exact XPath: %s", str(e))
            except Exception as e:
                logging.debug("Exact XPath lookup failed: %s", str(e))
            
            # Strategy 2: Aggressive JavaScript - find ANY button with OK text
            try:
                result = page.evaluate("""
                    () => {
                        const allButtons = document.querySelectorAll('button, em button, [role="button"], .x-btn');
                        for (let btn of allButtons) {
                            const text = btn.textContent.trim().toUpperCase();
                            if (text === 'OK' || text === 'OK ') {
                                console.log('Found OK button via aggressive scan');
                                btn.click();
                                return true;
                            }
                        }
                        const allEms = document.querySelectorAll('em');
                        for (let em of allEms) {
                            if (em.textContent.trim().toUpperCase() === 'OK') {
                                console.log('Found OK in EM element');
                                found_any_button = True;
                                if (em.closest('button')) {
                                    em.closest('button').click();
                                } else {
                                    em.click();
                                }
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if result:
                    page.wait_for_timeout(1000)
                    logging.info("✅✅ OK popup dismissed (JavaScript scan) for %s", path_label)
                    return True
            except Exception as e:
                logging.debug("JavaScript aggressive scan failed: %s", str(e))
            
            # Strategy 3: Try simple selectors
            selectors = [
                "button:has-text('OK')",
                ".x-btn-text:has-text('OK')",
                "//button[text()='OK']",
                "div.ext-mb-buttons button",
            ]
            for selector in selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.count():
                        logging.info("✓ Found OK button via selector: %s", selector)
                        try:
                            btn.click(force=True, timeout=2000)
                            page.wait_for_timeout(1000)
                            logging.info("✅✅ OK popup dismissed (selector: %s) for %s", selector, path_label)
                            return True
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # Small wait before retry
            page.wait_for_timeout(300)
        
        # Optional popup: if not present, continue normal flow
        logging.info("No OK popup shown for %s; continuing", path_label)

        return False
        
    except Exception as e:
        logging.error("Exception in dismiss_ok_popup_if_present: %s", str(e))
        return False


def _fast_dismiss_ok_popup_if_present(page, path_label: str) -> bool:
    """Instantly dismiss any visible warning/OK popup via direct JS click.

    Targets the ExtJS warning dialog the user identified: a div.x-window* container
    with a <button class="x-btn-text">OK</button> inside.  Uses pure JS so no
    Python-level DOM overhead.  Retries up to 3 times with 200 ms pauses (600 ms max).
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
    try:
        if page.is_closed():
            return False
        # Immediate check — dismiss if popup is already visible
        if page.evaluate(_JS):
            logging.info("Warning/OK popup dismissed immediately for %s", path_label)
            return True
        # One quiet retry after 10 ms — no continuous DOM polling, page stays stable
        page.wait_for_timeout(10)
        if not page.is_closed() and page.evaluate(_JS):
            logging.info("Warning/OK popup dismissed (50ms retry) for %s", path_label)
            return True
        return False
    except PlaywrightError:
        return False


def _install_ok_popup_guard(page) -> None:
    """Inject a MutationObserver that dismisses OK popup windows before the browser paints them.
    The observer fires in the browser's JS engine synchronously on DOM/style changes,
    so the popup is clicked before any frame is rendered — zero visual flash.
    Safe to call multiple times (guarded by window.__megaOkGuard).
    """
    _GUARD_JS = """
    () => {
        if (window.__megaOkGuard) return false;
        const _run = function() {
            const wins = document.querySelectorAll(
                'div.x-window, div.x-window-plain, div.x-window-dlg'
            );
            for (const win of wins) {
                const s = window.getComputedStyle(win);
                if (s.display === 'none' || s.visibility === 'hidden') continue;
                for (const btn of win.querySelectorAll('button')) {
                    if ((btn.textContent || '').trim().toUpperCase() === 'OK') {
                        btn.click();
                        return;
                    }
                }
            }
        };
        window.__megaOkGuard = new MutationObserver(_run);
        window.__megaOkGuard.observe(document.body, {
            childList: true, subtree: true,
            attributes: true, attributeFilter: ['style', 'class']
        });
        return true;
    }
    """
    try:
        if not page.is_closed():
            page.evaluate(_GUARD_JS)
    except PlaywrightError:
        pass


def dismiss_auto_popup_if_present(page, path_label: str) -> bool:
    """Aggressively close generic modal popups that appear only during automated traversal."""
    try:
        popup = page.locator(
            "div.x-window-plain.x-window-dlg.x-window.x-component, div.x-window-plain.x-window.x-component"
        ).first
        if not popup.count():
            return False

        button_patterns = [
            re.compile(r"^ok$", re.IGNORECASE),
            re.compile(r"^close$", re.IGNORECASE),
            re.compile(r"^fermer$", re.IGNORECASE),
            re.compile(r"^yes$", re.IGNORECASE),
            re.compile(r"^oui$", re.IGNORECASE),
            re.compile(r"^continue$", re.IGNORECASE),
        ]

        button_nodes = popup.locator("button, button.x-btn-text")
        for idx in range(button_nodes.count()):
            try:
                candidate = button_nodes.nth(idx)
                text = (candidate.inner_text() or candidate.text_content() or "").strip()
                if button_patterns and any(pattern.search(text) for pattern in button_patterns):
                    candidate.click(force=True, timeout=4000)
                    page.wait_for_timeout(600)
                    logging.info("Closed auto popup for %s", path_label)
                    return True
            except Exception:
                continue

        try:
            close_icon = popup.locator("div.x-tool-close").first
            if close_icon.count():
                close_icon.click(force=True, timeout=4000)
                page.wait_for_timeout(600)
                logging.info("Closed auto popup via close icon for %s", path_label)
                return True
        except Exception:
            pass

        return False
    except Exception as exc:
        logging.debug("Exception in dismiss_auto_popup_if_present for %s: %s", path_label, str(exc))
        return False


def dismiss_help_description_popup_if_present(page, path_label: str) -> bool:
    """Dismiss Help Description / ViewAndRun popup shown after Return in some AWB paths."""
    try:
        popup = page.locator(
            "div.x-window:has(span.x-window-header-text:has-text('Help Description')), "
            "div.x-window:has-text('ViewAndRun')"
        ).first
        if not popup.count():
            return False

        close_candidates = [
            popup.locator("button.x-btn-text").filter(has_text=re.compile(r"^fermer$", re.IGNORECASE)).first,
            popup.get_by_role("button", name=re.compile(r"^fermer$", re.IGNORECASE)).first,
            popup.locator("div.x-tool-close").first,
            popup.locator("div.x-tool-close img").first,
        ]

        for candidate in close_candidates:
            try:
                if not candidate.count():
                    continue
                candidate.click(force=True, timeout=4000)
                page.wait_for_timeout(500)
                logging.info("Closed Help Description popup for %s", path_label)
                return True
            except Exception:
                continue

        return False
    except Exception as exc:
        logging.debug("Exception while dismissing Help Description popup for %s: %s", path_label, str(exc))
        return False


def dismiss_save_success_popup_if_present(page, path_label: str) -> bool:
    """Dismiss the save success popup that appears after clicking Save."""
    try:
        success_text = re.compile(r"Sauvegard[ée]e? avec succès", re.IGNORECASE)
        popup_root = page.locator("div.x-window-plain.x-window-dlg.x-window.x-component").first
        if not popup_root.count():
            logging.info("No save success popup shown for %s; continuing", path_label)
            return False

        info_icon = popup_root.locator("div.ext-mb-icon.ext-mb-info")
        success_message = popup_root.locator("span.ext-mb-text").filter(has_text=success_text)
        if not info_icon.count() or not success_message.count():
            logging.info("No save success popup shown for %s; continuing", path_label)
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



def right_click_row_after_execute(page, module_name: str, path_label: str):
    # Give extra time for popups to appear and be briefly visible after execute search
    page.wait_for_timeout(1000)
    
    # First check if an OK popup appeared and dismiss it instantly
    _fast_dismiss_ok_popup_if_present(page, path_label)
    page.wait_for_timeout(500)
    # Dismiss any remaining popups (Error/NPE popup may coexist with tooMuchDataFound)
    _JS_DISMISS_REMAINING = """
    () => {
        let n = 0;
        const wins = document.querySelectorAll(
            'div.x-window, div.x-window-plain, div.x-window-dlg'
        );
        for (const win of wins) {
            const s = window.getComputedStyle(win);
            if (s.display === 'none' || s.visibility === 'hidden') continue;
            for (const btn of win.querySelectorAll('button')) {
                if ((btn.textContent || '').trim().toUpperCase() === 'OK') {
                    btn.click(); n++;
                }
            }
            for (const tool of win.querySelectorAll('.x-tool-close')) {
                tool.click(); n++;
            }
        }
        return n;
    }
    """
    for _dp in range(4):
        try:
            remaining = page.evaluate(_JS_DISMISS_REMAINING)
            if not remaining:
                break
            page.wait_for_timeout(300)
        except Exception:
            break
    page.wait_for_timeout(400)
    
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
        container.click(force=True, timeout=4000)
        row = get_first_visible_search_row(page)
        if row is None:
            raise PlaywrightTimeoutError("First visible search row not found")
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
            # Voir not available — try Editer directly from the still-open context menu
            logging.info(
                "Voir not available for %s; attempting direct Editer from open context menu",
                path_label,
            )
            edit_opt = page.locator(f"xpath={AWB_EDIT_OPTION_XPATH}").first
            if edit_opt.count():
                try:
                    edit_opt.click(force=True, timeout=4000)
                    logging.info("Direct Editer clicked (no Voir) for %s", path_label)
                    handle_edit_panel(page, module_name, path_label)
                    return
                except Exception:
                    pass
            if click_edit_context_option(page, module_name, path_label):
                logging.info("Editer clicked via context menu (no Voir) for %s", path_label)
                handle_edit_panel(page, module_name, path_label)
                return
            logging.warning("Neither Voir nor Editer available for %s", path_label)
            try:
                page.keyboard.press("Escape")
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass
            capture_failure(page, module_name, path_label)
            return

        logging.info("View clicked for %s", path_label)
        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(600)

        # Click Return button (manual-like to avoid automation-only virtual popup).
        return_btn = page.locator(VIEW_RETURN_SELECTOR).first
        if not return_btn.count():
            logging.warning("Return button not found for %s", path_label)
            capture_failure(page, module_name, path_label)
            return

        if click_return_button_like_manual(page, path_label):
            logging.info("Return clicked for %s", path_label)
        else:
            logging.warning("Return click failed for %s", path_label)
            capture_failure(page, module_name, path_label)
            return

        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(500)
        dismiss_help_description_popup_if_present(page, path_label)
        dismiss_auto_popup_if_present(page, path_label)

        # Right-click again on the first visible row
        try:
            container.click(force=True, timeout=4000)
            row = get_first_visible_search_row(page)
            if row is None:
                raise PlaywrightTimeoutError("First visible search row not found after return")
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
        if not click_return_button_like_manual(page, path_label):
            logging.warning("Unable to close view panel for %s", path_label)
            return
        handle_error_dialog(page, module_name, path_label)
        page.wait_for_timeout(600)
    except PlaywrightError:
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
        logging.error("Failed to open login page %s: %s", LOGIN_ENTRY, exc)
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
    except PlaywrightError as exc:
        if "Target page, context or browser has been closed" in str(exc):
            logging.error("Browser page closed during login readiness wait.")
            return False
        raise

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


def traverse_menu_paths(page, menu_paths: List[List[str]], context=None) -> None:
    if not menu_paths:
        logging.warning("No menu paths supplied")
        return

    parent_prefixes = build_parent_prefixes(menu_paths)
    expanded_nodes: set[tuple[str, ...]] = set()

    for index, path in enumerate(menu_paths):
        # If the previous path closed the page (e.g. user closed a tab), recover
        if context and page.is_closed():
            logging.warning("Page was closed; attempting recovery with a new page")
            try:
                page = context.new_page()
                page.emulate_media(reduced_motion="reduce")
                page.add_init_script("""
                    const _noAnim = document.createElement('style');
                    _noAnim.textContent = [
                        '*, *::before, *::after { animation-duration: 0ms !important; animation-delay: 0ms !important; transition-duration: 0ms !important; transition-delay: 0ms !important; }',
                        'html { overflow-y: scroll !important; scrollbar-gutter: stable both-edges !important; }',
                        'body { overflow-y: scroll !important; overflow-anchor: none !important; overscroll-behavior: none !important; }',
                        '.x-mask { position: fixed !important; width: 100vw !important; height: 100vh !important; margin: 0 !important; transform: none !important; }',
                        '.x-window, .x-window-plain, .x-window-dlg, .x-window-shadow { position: fixed !important; transform: none !important; }'
                    ].join(' ');
                    (document.head || document.documentElement).appendChild(_noAnim);
                """)
                page.add_init_script("window.addEventListener('contextmenu', event => event.preventDefault(), { capture: true });")
                if not login(page):
                    logging.error("Re-login failed after page closure; stopping traversal")
                    break
                expanded_nodes.clear()  # tree is fresh after re-login
                logging.info("Re-login successful; resuming from path %s", " > ".join(path))
            except Exception as exc:
                logging.error("Could not recover from closed page: %s; stopping traversal", exc)
                break

        if len(path) < 2:
            logging.warning("Skipping short path %s", path)
            continue

        top_level = path[0]
        button = page.get_by_role("button", name=top_level)
        if not button.count():
            logging.warning("Top level tab %s not found", top_level)
            continue

        path_label = " > ".join(path)
        try:
            button.click()
        except Exception as exc:
            logging.warning(f"[SAFE] Could not click top level tab {top_level} for path {path_label}: {exc}")
            try:
                capture_failure(page, top_level, path_label, always=True)
            except Exception:
                logging.warning(f"[SAFE] Could not capture failure for {path_label}")
            continue

        normalized_path = tuple(segment.strip().lower() for segment in path)
        logging.info("Traversing path %s", path_label)
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
            node = find_tree_node_with_scroll(page, segment, level)
            if not node.count() or not node.is_visible():
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
                # For close/save-only menus, do not capture before dedicated workflow.
                if not (node_is_leaf and (should_force_close_only(path) or should_force_save_only(path))):
                    handle_error_dialog(page, top_level, path_label)

            page.wait_for_timeout(1500)

            if node_is_leaf and should_force_close_only(path):
                run_close_only_menu_workflow(page, path_label)
                collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                continue

            if node_is_leaf and should_force_save_only(path):
                logging.info("Applying save-only workflow for %s", path_label)
                run_save_only_menu_workflow(page, top_level, path_label)
                collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                continue

            if node_is_leaf:
                if should_skip_recycler_auto_search(path):
                    logging.info("Skipping pre-execute search click for recycler path %s", path_label)
                else:
                    click_search_button_if_available(page, top_level, path_label)

            if node_is_leaf:
                table = page.locator("table.x-form-search")
                if table.count():
                    table_root = table.first
                    result_row = table_root.locator("tbody tr").first
                    if result_row.count() or should_skip_recycler_auto_search(path):
                        try:
                            if result_row.count():
                                result_row.scroll_into_view_if_needed()
                            if result_row.count() and not should_skip_recycler_auto_search(path):
                                result_row.click(force=True, timeout=4000)
                            handle_error_dialog(page, top_level, path_label)

                            recycler_mode = should_skip_recycler_auto_search(path)
                            execute_clicked = False
                            if not recycler_mode:
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

                            execute_clicked = click_execute_search(page, path_label, recycler_mode)
                            if not execute_clicked:
                                capture_failure(page, top_level, path_label, always=True)
                                raise PlaywrightTimeoutError("Execute Search could not be clicked")

                            page.wait_for_timeout(20)  # Let popup paint, then dismiss almost immediately
                            _fast_dismiss_ok_popup_if_present(page, path_label)
                            # Also dismiss any remaining popups (e.g. NPE Error popup)
                            try:
                                page.evaluate("""
                                () => {
                                    for (const win of document.querySelectorAll('div.x-window,div.x-window-plain,div.x-window-dlg')) {
                                        const s = window.getComputedStyle(win);
                                        if (s.display === 'none' || s.visibility === 'hidden') continue;
                                        for (const t of win.querySelectorAll('.x-tool-close')) t.click();
                                        for (const b of win.querySelectorAll('button')) { if ((b.textContent||'').trim().toUpperCase()==='OK') b.click(); }
                                    }
                                }
                                """)
                            except Exception:
                                pass
                            try:
                                page.wait_for_selector("div.x-grid3-row", timeout=9000)
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
                                logging.info("Search header found for %s", path_label)
                            else:
                                logging.warning(
                                    "Search header missing for %s", path_label
                                )
                            viewport_locators = page.locator("div.x-grid3-viewport")
                            viewport_count = viewport_locators.count()
                            if not viewport_count:
                                logging.warning(
                                    "Grid viewport missing for %s", path_label
                                )
                            table_root = page.locator("table.x-form-search").first
                            grid_row_locator = page.locator("[id$=PalmyraGrid_0]").first
                            try:
                                grid_row_locator.wait_for(timeout=9000)
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

                            activate_row_checkbox(result_row, path_label)
                            awb_view_then_edit_flow(page, top_level, path_label)
                        except PlaywrightTimeoutError as exc:
                            logging.warning("Context menu interaction failed for %s: %s", path_label, exc)
                            capture_failure(page, top_level, path_label, always=True)
                    else:
                        logging.warning("No result rows found for %s", path_label)
                        capture_failure(page, top_level, path_label)
                else:
                    # No form table yet: still keep the full process and execute search.
                    try:
                        recycler_mode = should_skip_recycler_auto_search(path)
                        execute_clicked = click_execute_search(page, path_label, recycler_mode)
                        if not execute_clicked:
                            capture_failure(page, top_level, path_label, always=True)
                            logging.warning("Skipping path after missing Execute Search for %s", path_label)
                            close_work_window(page, path_label)
                            collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                            break

                        page.wait_for_timeout(20)  # Let popup paint, then dismiss almost immediately
                        _fast_dismiss_ok_popup_if_present(page, path_label)

                        # Wait and right-click row after execute (robust path with internal waits).
                        right_clicked_row = right_click_row_after_execute(page, top_level, path_label)
                        if right_clicked_row is not None:
                            result_row = right_clicked_row
                            activate_row_checkbox(result_row, path_label)
                            awb_view_then_edit_flow(page, top_level, path_label)
                        else:
                            logging.warning("No result row found after execute for %s", path_label)
                            capture_failure(page, top_level, path_label)
                    except Exception as exc:
                        logging.warning("Leaf processing failed for %s: %s", path_label, exc)
                        capture_failure(page, top_level, path_label, always=True)
                        close_work_window(page, path_label)
                        collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)
                        break

                close_button = page.locator("a.x-tab-strip-close")
                if close_button.count():
                    close_button.first.click()
                    page.wait_for_timeout(600)
                collapse_unused_ancestors(page, menu_paths, index, path, expanded_nodes)

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
        page.emulate_media(reduced_motion="reduce")
        page.add_init_script("""
            const _noAnim = document.createElement('style');
            _noAnim.textContent = [
                '*, *::before, *::after { animation-duration: 0ms !important; animation-delay: 0ms !important; transition-duration: 0ms !important; transition-delay: 0ms !important; }',
                'html { overflow-y: scroll !important; scrollbar-gutter: stable both-edges !important; }',
                'body { overflow-y: scroll !important; overflow-anchor: none !important; overscroll-behavior: none !important; }',
                '.x-mask { position: fixed !important; width: 100vw !important; height: 100vh !important; margin: 0 !important; transform: none !important; }',
                '.x-window, .x-window-plain, .x-window-dlg, .x-window-shadow { position: fixed !important; transform: none !important; }'
            ].join(' ');
            (document.head || document.documentElement).appendChild(_noAnim);
        """)
        page.add_init_script("window.addEventListener('contextmenu', event => event.preventDefault(), { capture: true });")
        try:
            if not login(page):
                logging.error("Login failed for %s. Aborting menu traversal.", LOGIN_ENTRY)
                return
            if menu_paths:
                traverse_menu_paths(page, menu_paths, context)
            else:
                process_menu(page)
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
