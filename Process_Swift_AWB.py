"""
Process_Swift.py
================
Automated end-to-end SWIFT injection for AWB:
  Step 1 – MT54X   → instruction creation
  Step 2 – MT548   → matching  (MT548_1.swf then MT548_2.swf)
  Step 3 – MT54Y   → settlement

Each file is uploaded to the AWB integration drop-box via WinSCP (SFTP),
then polled until it disappears (= absorbed by the Megara gateway).
"""

import logging
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── AWB SFTP credentials (override via environment variables) ────────────────
AWB_HOST     = os.getenv("AWB_HOST",     "10.1.140.244")
AWB_USER     = os.getenv("AWB_USER",     "server")
AWB_PASSWORD = os.getenv("AWB_PASSWORD", "server@244")
AWB_PORT     = int(os.getenv("AWB_PORT", "22"))

# ── Remote Megara ALLIANCE drop-box ──────────────────────────────────────────
REMOTE_ALLIANCE_PATH = os.getenv(
    "REMOTE_ALLIANCE_PATH",
    "/Megara/IODevices/MegaCustody/IN/ALLIANCE",
)

# ── Local SWIFT files ─────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent
SWIFT_MT54X   = _BASE / "SWIFTS" / "AWB" / "MT54X" / "MT54X.txt"
SWIFT_MT548_1 = _BASE / "SWIFTS" / "AWB" / "MT548" / "MT548_1.txt"
SWIFT_MT54Y_1 = _BASE / "SWIFTS" / "AWB" / "MT54Y" / "MT54Y_1.txt"

# ── Absorption polling settings ───────────────────────────────────────────────
ABSORPTION_TIMEOUT_S  = int(os.getenv("ABSORPTION_TIMEOUT",  "1800"))  # seconds (30 min – IODevice cycle is slow)
ABSORPTION_INTERVAL_S = int(os.getenv("ABSORPTION_INTERVAL", "15"))    # seconds

# ── WinSCP discovery ──────────────────────────────────────────────────────────
_WINSCP_CANDIDATES = [
    r"C:\Program Files (x86)\WinSCP\WinSCP.com",
    r"C:\Program Files\WinSCP\WinSCP.com",
    r"C:\Program Files (x86)\WinSCP\winscp.com",
    r"C:\Program Files\WinSCP\winscp.com",
]

# ── MegaCustody UI (Playwright) ──────────────────────────────────────────────
MEGACUSTODY_ENTRY = os.getenv("MEGACUSTODY_URL", "http://10.1.140.244:9082/MegaCustody/login.jsp")
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "migration")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Vermeg+123")
AUTH_DOMAIN   = os.getenv("AUTH_DOMAIN", "awb")

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)
SWIFT_SCREENSHOTS_DIR = SCREENSHOT_DIR / "AWB" / "Process_Swift" / "notifications"
SWIFT_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_VIEWPORT = {"width": 1366, "height": 768}

# Timestamp captured at script start, minus 3 minutes (safety margin so the
# Creation Date >= filter always catches the freshly-injected MT54X record).
from datetime import timedelta as _timedelta
_now_minus_3min = datetime.now() - _timedelta(minutes=3)
SCRIPT_START_TIMESTAMP = _now_minus_3min.strftime("%d/%m/%Y %H:%M:%S:") + f"{_now_minus_3min.microsecond // 1000:03d}"


def _find_winscp() -> Optional[str]:
    """Return path to winscp.com, or None if not found."""
    env_override = os.getenv("WINSCP_EXE")
    if env_override and Path(env_override).exists():
        return env_override
    for candidate in _WINSCP_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


# ── Low-level WinSCP helpers ──────────────────────────────────────────────────

def _open_line() -> str:
    """Build the WinSCP 'open' command line for the AWB server."""
    return (
        f"open sftp://{AWB_USER}:{AWB_PASSWORD}@{AWB_HOST}:{AWB_PORT}/"
        " -hostkey=* -timeout=30"
    )


def _run_winscp_script(script_body: str, label: str, timeout: int = 120) -> bool:
    """
    Write *script_body* to a temp file and run it through winscp.com.
    Returns True on exit code 0.
    """
    winscp = _find_winscp()
    if not winscp:
        log.error(
            "WinSCP.com not found. Install WinSCP or set the WINSCP_EXE "
            "environment variable to its path."
        )
        return False

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script_body)
        script_path = fh.name

    try:
        # NOTE: do NOT pass /log= or /loglevel= — they cause WinSCP to use a
        # different transfer code-path that fails on this Megara SFTP server.
        # The working reference (inject_mt54x.py) uses no extra flags.
        result = subprocess.run(
            [winscp, f"/script={script_path}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            log.info("[%s] WinSCP completed successfully.", label)
            return True

        log.error(
            "[%s] WinSCP exited with code %d.\nSTDOUT: %s\nSTDERR: %s",
            label,
            result.returncode,
            result.stdout[:800],
            result.stderr[:400],
        )
        return False

    except subprocess.TimeoutExpired:
        log.error("[%s] WinSCP timed out after %d s.", label, timeout)
        return False

    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ── Core SFTP operations ──────────────────────────────────────────────────────

def _remote_name(local_file: Path) -> str:
    """Return the remote filename (same as local, already .txt)."""
    return local_file.name


def upload_swift(local_file: Path, remote_dir: str) -> bool:
    """
    Upload *local_file* renamed to .txt (IODevice is configured for .txt only)
    to *remote_dir* on the AWB SFTP server.
    """
    if not local_file.exists():
        log.error("Local SWIFT file not found: %s", local_file)
        return False

    rname = _remote_name(local_file)
    remote_dest = f"{remote_dir}/{rname}"
    # -resumesupport=off → write directly to the final filename (no .filepart
    # temp file). The Megara SFTP server rejects the temp-file CREATE, so
    # this flag is required.
    script = "\n".join([
        _open_line(),
        f'put -resumesupport=off "{local_file}" "{remote_dest}"',
        "close",
        "exit",
    ])

    log.info("Uploading  %s  \u2192  %s:%s", local_file.name, AWB_HOST, remote_dest)
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        if _run_winscp_script(script, f"upload_{rname}"):
            return True
        if attempt < max_attempts:
            log.warning(
                "Upload attempt %d/%d failed \u2014 cleaning up and retrying in 30 s \u2026",
                attempt, max_attempts,
            )
            cleanup_alliance()
            time.sleep(30)
    log.error("All %d upload attempts failed for %s.", max_attempts, rname)
    return False


def _remote_file_exists(remote_dir: str, filename: str) -> bool:
    """
    Return True if *filename* is still visible inside *remote_dir*.
    Lists the directory and checks stdout for the filename — this is
    equivalent to pressing CTRL+R (Refresh) in the WinSCP GUI.
    """
    winscp = _find_winscp()
    if not winscp:
        return False

    script = "\n".join([
        _open_line(),
        f"ls {remote_dir}/",
        "close",
        "exit",
    ])

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script)
        script_path = fh.name

    try:
        result = subprocess.run(
            [winscp, f"/script={script_path}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Parse only actual directory listing lines (format: permissions links owner group size date name)
        # A real ls line ends with the filename and contains at least 8 fields
        for line in result.stdout.splitlines():
            parts = line.split()
            # A valid ls -l line has ≥9 parts and the last part is the filename
            if len(parts) >= 9 and parts[-1] == filename:
                return True
        return False
    except subprocess.TimeoutExpired:
        log.warning("Timeout refreshing remote directory: %s", remote_dir)
        return False
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def wait_for_absorption(
    remote_dir: str,
    filename: str,
    timeout: int = ABSORPTION_TIMEOUT_S,
    interval: int = ABSORPTION_INTERVAL_S,
) -> bool:
    """
    Poll the remote directory every *interval* seconds (CTRL+R equivalent)
    until *filename* disappears (absorbed by Megara gateway) or *timeout*
    seconds elapse.
    """
    deadline = time.time() + timeout
    log.info(
        "Waiting for absorption of %s  (timeout=%ds, refresh every %ds) …",
        filename, timeout, interval,
    )

    while time.time() < deadline:
        if not _remote_file_exists(remote_dir, filename):
            elapsed = timeout - max(0.0, deadline - time.time())
            log.info("✓  %s absorbed after ~%.0f s.", filename, elapsed)
            return True

        remaining = max(0.0, deadline - time.time())
        log.info("  [CTRL+R] %s still present — %.0f s remaining, next refresh in %d s …", filename, remaining, interval)
        time.sleep(interval)

    log.warning("✗  Absorption timeout for %s after %d s.", filename, timeout)
    return False


# ── Cleanup ──────────────────────────────────────────────────────────────────

def cleanup_alliance() -> None:
    """
    Delete any leftover SWIFT files in the ALLIANCE drop-box before injecting.
    Uses 'option batch continue' so missing files don't cause a fatal error.
    """
    winscp = _find_winscp()
    if not winscp:
        return

    known_files = [
        _remote_name(SWIFT_MT54X),
        _remote_name(SWIFT_MT548_1),
        _remote_name(SWIFT_MT54Y_1),
    ]
    # Also delete .filepart leftovers from interrupted WinSCP uploads (in both root and temp/)
    filepart_files = [f"{f}.filepart" for f in known_files]
    root_files = known_files + filepart_files
    temp_files = known_files + filepart_files  # same names under temp/

    script = "\n".join(
        [_open_line(), "option batch continue"]
        + [f'rm "{REMOTE_ALLIANCE_PATH}/{f}"' for f in root_files]
        + [f'rm "{REMOTE_ALLIANCE_PATH}/temp/{f}"' for f in temp_files]
        + ["close", "exit"]
    )

    log.info("Cleaning up any leftover files in ALLIANCE drop-box …")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script)
        script_path = fh.name

    try:
        subprocess.run(
            [winscp, f"/script={script_path}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        log.info("Cleanup done.")
    except subprocess.TimeoutExpired:
        log.warning("Cleanup timed out.")
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ── Diagnostics ──────────────────────────────────────────────────────────────

def diagnose_alliance_dirs() -> None:
    """
    List the ALLIANCE directory and its known sub-folders (temp, ERR, REJECTED)
    to see where Megara moved the injected files.
    """
    winscp = _find_winscp()
    if not winscp:
        log.error("WinSCP not found, cannot run diagnostics.")
        return

    dirs_to_check = [
        REMOTE_ALLIANCE_PATH,
        f"{REMOTE_ALLIANCE_PATH}/temp",
        f"{REMOTE_ALLIANCE_PATH}/ERR",
        f"{REMOTE_ALLIANCE_PATH}/REJECTED",
        f"{REMOTE_ALLIANCE_PATH}/ERROR",
        "/Megara/IODevices/MegaCustody/ERR",
        "/Megara/IODevices/MegaCustody/ERROR",
    ]

    ls_commands = "\n".join(
        [_open_line(), "option batch continue", "option confirm off"]
        + [f"ls {d}/" for d in dirs_to_check]
        + ["close", "exit"]
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(ls_commands)
        script_path = fh.name

    try:
        result = subprocess.run(
            [winscp, f"/script={script_path}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        log.info("=== DIAGNOSTIC — remote directory listing ===\n%s", result.stdout[:3000])
        if result.stderr:
            log.info("=== DIAGNOSTIC stderr ===\n%s", result.stderr[:1000])
    except subprocess.TimeoutExpired:
        log.warning("Diagnostic timed out.")
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ── Process steps ─────────────────────────────────────────────────────────────

def step_create_instruction() -> bool:
    """Step 1 – inject MT54X (instruction creation)."""
    log.info("=" * 60)
    log.info("STEP 1: Instruction creation  (MT54X)")
    log.info("=" * 60)
    if not upload_swift(SWIFT_MT54X, REMOTE_ALLIANCE_PATH):
        return False
    return wait_for_absorption(REMOTE_ALLIANCE_PATH, _remote_name(SWIFT_MT54X))


def step_matching() -> bool:
    """Step 2 – inject MT548 files (matching)."""
    log.info("=" * 60)
    log.info("STEP 2: Matching  (MT548)")
    log.info("=" * 60)
    for swift_file in [SWIFT_MT548_1]:
        if not upload_swift(swift_file, REMOTE_ALLIANCE_PATH):
            return False
        if not wait_for_absorption(REMOTE_ALLIANCE_PATH, _remote_name(swift_file)):
            return False
    return True


def step_settlement() -> bool:
    """Step 3 – inject MT54Y (settlement)."""
    log.info("=" * 60)
    log.info("STEP 3: Settlement  (MT54Y)")
    log.info("=" * 60)
    if not upload_swift(SWIFT_MT54Y_1, REMOTE_ALLIANCE_PATH):
        return False
    return wait_for_absorption(REMOTE_ALLIANCE_PATH, _remote_name(SWIFT_MT54Y_1))


# ── MegaCustody UI verification (Playwright) ──────────────────────────────────

EXECUTE_CRITERIA_SELECTOR = "#Component_PAGE_FORM_0_executeCriteria_null"
AWB_CLOSE_TAB_AFTER_VIEW_XPATH = "/html/body/div[2]/div/div[3]/div[1]/div[1]/ul/li[1]/a[1]"


def close_work_window(page, path_label: str) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
    if page.is_closed():
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
            pass
        except PlaywrightError:
            return


NOTIFICATION_MESSAGES_PATH = ("Notification", "Messages")
NOTIFICATION_SWIFTS_MT54X_PATH = ("Notification", "Swifts", "MT54X")
MONITORING_INSTRUCTIONS_PATH = (
    "Règlement/Livraison",
    "Instructions Clients",
    "Monitoring Instructions Client",
)
VALIDATION_INSTRUCTION_CLIENT_PATH = (
    "Règlement/Livraison",
    "Instructions Clients",
    "Validation Instruction Client",
)
MONITORING_INSTRUCTIONS_MARCHE_PATH = (
    "Règlement/Livraison",
    "Instructions Marché",
    "Monitoring Instructions Marché",
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_") or "value"


def _swift_login_megacustody(page) -> bool:
    """Login to MegaCustody with affiliate=awb (handles SSO wrong-affiliate)."""
    import Process_RL_AWB as awb_proc
    return awb_proc._awb_login(page, MEGACUSTODY_ENTRY)


def _find_visible_tree_node(page, label: str, timeout_ms: int = 4000):
    """Fast lookup: scan visible treeitems by exact text, no scroll loops.

    Most MegaCustody menus (Notification, Règlement/Livraison) auto-expand
    their root, so the target leaf is already in the DOM. A single visibility
    scan is much faster than the generic find_tree_node which scrolls 12× even
    when the node is on screen.
    """
    target = (label or "").strip().casefold()
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        items = page.locator("div[role='treeitem']")
        try:
            count = items.count()
        except Exception:
            count = 0
        for i in range(count):
            item = items.nth(i)
            try:
                if not item.is_visible():
                    continue
                txt = (item.inner_text() or "").strip().casefold()
                if txt == target or txt.startswith(target + "\n") or txt.splitlines()[0].strip() == target:
                    return item
            except Exception:
                continue
        page.wait_for_timeout(120)
    return None


def _open_menu_path(page, path: Tuple[str, ...]) -> bool:
    """Fast menu navigation: top-level tab → visible treeitem per segment."""
    import Process_RL_CDG as base
    if not path:
        return False

    if not base.open_top_level_menu(page, path[0]):
        log.warning("Top level menu %s not opened", path[0])
        return False
    page.wait_for_timeout(200)

    for idx, segment in enumerate(path[1:], start=1):
        node = _find_visible_tree_node(page, segment, timeout_ms=4000)
        if node is None:
            log.warning("Tree node '%s' not visible (after %ss)", segment, 4)
            return False
        try:
            node.scroll_into_view_if_needed()
        except Exception:
            pass
        try:
            if idx < len(path) - 1:
                # Intermediate node: ensure children are expanded.
                # Ext JS trees require dblclick to toggle expansion.
                # If next leaf is already visible, the parent is already expanded — do nothing.
                # Otherwise dblclick. If still not visible, dblclick again (the previous
                # state was expanded and our first dblclick collapsed it).
                next_leaf = path[idx + 1]
                if _find_visible_tree_node(page, next_leaf, timeout_ms=300) is None:
                    try:
                        node.dblclick(force=True, timeout=2500)
                    except Exception:
                        pass
                    page.wait_for_timeout(400)
                    if _find_visible_tree_node(page, next_leaf, timeout_ms=1500) is None:
                        try:
                            node.dblclick(force=True, timeout=2500)
                        except Exception:
                            pass
                        page.wait_for_timeout(400)
            else:
                node.click(force=True, timeout=2500)
                page.wait_for_timeout(150)
        except Exception as exc:
            log.warning("Failed to open node '%s': %s", segment, exc)
            return False
    return True


def _close_all_work_tabs(page, max_iterations: int = 10) -> None:
    """Close every open work-area tab/detail view so the tree menu has full focus.

    Some flows leave a Voir detail tab open in addition to a grid tab; a single
    `close_work_window` call only dismisses one. Loop until no closable tab
    is found or the safety cap is reached.
    """
    # First, dismiss any stuck modal popup (validation confirmation, error dialog, …)
    # by trying common OK/close affordances and pressing Escape twice.
    try:
        # Error window: click its x-tool-close (X) icon
        try:
            err = page.locator(
                "xpath=//div[contains(@class,'x-window') and not(contains(@style,'display: none'))]"
                "[.//span[contains(@class,'x-window-header-text') and normalize-space(text())='Error']]"
                "//div[contains(@class,'x-tool-close')]"
            ).first
            if err.count():
                err.click(force=True, timeout=1500)
                page.wait_for_timeout(300)
        except Exception:
            pass
        for popup_sel in [
            "xpath=//div[contains(@class,'x-window') and not(contains(@style,'display: none'))]//button[normalize-space(text())='OK']",
            "xpath=//div[contains(@class,'x-window') and not(contains(@style,'display: none'))]//button[normalize-space(text())='Ok']",
            "xpath=//div[contains(@class,'x-window') and not(contains(@style,'display: none'))]//div[contains(@class,'x-tool-close')]",
        ]:
            try:
                btn = page.locator(popup_sel).first
                if btn.count():
                    btn.click(force=True, timeout=1500)
                    page.wait_for_timeout(250)
            except Exception:
                pass
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
            page.keyboard.press("Escape")
            page.wait_for_timeout(150)
        except Exception:
            pass
    except Exception:
        pass
    selectors = [
        "a.x-tab-strip-close:visible",
        "div.x-tool-close:visible",
        "button[aria-label='Close']:visible",
    ]
    for _ in range(max_iterations):
        # First try the high-level helper (handles Megara-specific close icons)
        try:
            close_work_window(page, "")
        except Exception:
            pass
        page.wait_for_timeout(150)
        # Then sweep any remaining visible close affordances
        closed_any = False
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(force=True, timeout=1500)
                    page.wait_for_timeout(200)
                    closed_any = True
                    break
            except Exception:
                continue
        if not closed_any:
            return


def _click_execute_search(page) -> bool:
    locator = page.locator(EXECUTE_CRITERIA_SELECTOR)
    for i in range(locator.count()):
        candidate = locator.nth(i)
        try:
            if candidate.is_visible():
                try:
                    candidate.scroll_into_view_if_needed()
                except Exception:
                    pass
                candidate.click(force=True, timeout=4000)
                page.wait_for_timeout(2000)
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
        except Exception:
            continue
    log.warning("Execute Search button not found / not visible")
    return False


def _expand_collapsed_fieldsets(page) -> None:
    """Click any visible collapsed fieldset toggles to reveal hidden criteria.

    Some search forms (e.g. Monitoring Instructions Client) hide the Creation
    Date row inside a collapsed fieldset. The toggle is a `div.x-tool-toggle`
    with role=checkbox sitting in the fieldset legend; the dynamic id varies.
    """
    try:
        toggles = page.locator("legend div.x-tool-toggle[role='checkbox']")
        count = toggles.count()
    except Exception:
        return
    for i in range(count):
        t = toggles.nth(i)
        try:
            if not t.is_visible():
                continue
            t.click(force=True, timeout=2000)
            page.wait_for_timeout(150)
        except Exception:
            continue


def _set_creation_date_filter(page, timestamp: str) -> bool:
    """
    Set the Creation Date criteria operator to '>=' (7th option in the dropdown)
    and fill the value field with `timestamp`.

    Strategy: locate the operator field via its stable name attribute
    (`Component_PAGE_FORM_0_atomicCriteria_creationDate_operation`), then walk
    the surrounding row to find the operator trigger arrow and the value input.
    """
    op_wrap = page.locator(
        "div[id='Component_PAGE_FORM_0_atomicCriteria_creationDate_operation']"
    ).first
    # If the criteria field is hidden inside a collapsed fieldset, expand it.
    if op_wrap.count():
        try:
            if not op_wrap.is_visible():
                _expand_collapsed_fieldsets(page)
                page.wait_for_timeout(250)
        except Exception:
            _expand_collapsed_fieldsets(page)
            page.wait_for_timeout(250)
    else:
        _expand_collapsed_fieldsets(page)
        page.wait_for_timeout(250)
        op_wrap = page.locator(
            "div[id='Component_PAGE_FORM_0_atomicCriteria_creationDate_operation']"
        ).first
    if not op_wrap.count():
        # Fallback by input name
        op_wrap = page.locator(
            "xpath=//input[@name='Component_PAGE_FORM_0_atomicCriteria_creationDate_operation']/ancestor::div[contains(@class,'x-form-field-wrap')][1]"
        ).first
    if not op_wrap.count():
        log.warning("Creation Date operator wrapper not found")
        return False

    # Click the trigger arrow inside the operator wrap
    trigger = op_wrap.locator("img.x-form-trigger-arrow").first
    if not trigger.count():
        log.warning("Creation Date operator trigger arrow not found")
        return False
    try:
        trigger.click(force=True, timeout=4000)
        page.wait_for_timeout(400)
    except Exception as exc:
        log.warning("Click on Creation Date operator trigger failed: %s", exc)
        return False

    # Pick the 7th list item (>=) from the visible combo list
    item = page.locator(
        "xpath=(//div[contains(@class,'x-combo-list') and not(contains(@class,'x-hidden'))][.//div[contains(@class,'x-combo-list-item')]])[last()]/div[contains(@class,'x-combo-list-item')][7]"
    ).first
    if not item.count():
        # Fallback: any visible list with text exactly '>='
        item = page.locator(
            "xpath=//div[contains(@class,'x-combo-list-item') and normalize-space(text())='>=']"
        ).first
    try:
        item.click(force=True, timeout=4000)
        page.wait_for_timeout(300)
    except Exception as exc:
        log.warning("Click on '>=' option failed: %s", exc)
        return False

    # Fill the criteria value input (sibling cell of the operator wrap)
    value_wrap = page.locator(
        "div[id='Component_PAGE_FORM_0_atomicCriteria_creationDate_criteria']"
    ).first
    if not value_wrap.count():
        log.warning("Creation Date value wrapper not found")
        return False
    value_input = value_wrap.locator("input.x-form-text").first
    if not value_input.count():
        log.warning("Creation Date value input not found")
        return False

    try:
        value_input.click(force=True, timeout=4000)
        value_input.press("Control+A")
        value_input.fill(timestamp)
        page.wait_for_timeout(200)
        log.info("Creation Date filter set: >= %s", timestamp)
        return True
    except Exception as exc:
        log.warning("Failed to fill Creation Date value: %s", exc)
        return False


def _right_click_first_row_voir_screenshot(page, screenshot_path: Path, return_after: bool = True) -> bool:
    """Right-click 1st result row, choose 'Voir', wait, take full-page screenshot."""
    # 1) Bring the grid container into the viewport (handles long forms
    #    where the grid sits below the fold).
    try:
        grid_container = page.locator("[id$='PalmyraGrid_0']").first
        if grid_container.count():
            grid_container.scroll_into_view_if_needed(timeout=2000)
            page.wait_for_timeout(300)
    except Exception:
        pass

    # Only consider real DATA rows inside the grid body. Order matters:
    # x-grid3-row is the ExtJS data-row class (never matches headers).
    row = None
    for selector in [
        "div.x-grid3-body tr.x-grid3-row",
        "tr.x-grid3-row",
        "tr[id*='PalmyraGrid_0']",
    ]:
        try:
            page.wait_for_selector(selector, timeout=4000)
            candidate = page.locator(selector).first
            if candidate.count() and candidate.is_visible():
                row = candidate
                break
        except Exception:
            continue
    if row is None:
        log.warning("No result row found for screenshot %s", screenshot_path.name)
        return False

    # 2) Scroll the row itself into view vertically BEFORE any click.
    try:
        row.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
        page.wait_for_timeout(250)
    except Exception:
        pass

    # 3) Reset the grid's internal horizontal scroller so the leftmost cells
    #    (clientReference, mainReference…) are on-screen. The row is ~20000px
    #    wide so without this its center is far off-screen.
    try:
        page.evaluate(
            "() => { document.querySelectorAll('.x-grid3-scroller').forEach(el => { el.scrollLeft = 0; }); }"
        )
        page.wait_for_timeout(200)
    except Exception:
        pass

    # 4) Pick a VISIBLE target cell inside the row (leftmost small cell).
    target = None
    for cell_selector in [
        "td.x-grid3-td-clientReference",
        "td.x-grid3-td-mainReference",
        "td.x-grid3-td-oTCTraded",
        "td:nth-child(4)",
        "td:nth-child(2)",
    ]:
        try:
            candidate = row.locator(cell_selector).first
            if candidate.count() and candidate.is_visible():
                target = candidate
                break
        except Exception:
            continue
    if target is None:
        target = row  # last-resort fallback

    # 5) Make sure the chosen cell is actually scrolled into view BEFORE clicking.
    try:
        target.scroll_into_view_if_needed(timeout=2000)
        page.wait_for_timeout(200)
    except Exception:
        pass

    # 6) Select the row first (ExtJS often requires a selection before the
    #    context menu offers row-level actions like 'Voir').
    try:
        target.click(force=True, timeout=3000)
        page.wait_for_timeout(250)
    except Exception:
        pass

    # Right-click on the visible target cell.
    right_clicked = False
    try:
        target.click(button="right", force=True, timeout=4000)
        page.wait_for_timeout(700)
        right_clicked = True
    except Exception as exc:
        log.warning("Playwright right-click failed (%s) — falling back to JS dispatch", exc)
    if not right_clicked:
        try:
            box = target.bounding_box()
            if box:
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                page.mouse.move(cx, cy)
                page.mouse.click(cx, cy, button="right")
                page.wait_for_timeout(700)
                right_clicked = True
        except Exception as exc:
            log.warning("Mouse right-click fallback failed: %s", exc)
    if not right_clicked:
        return False

    voir = None
    for selector in [
        "xpath=//span[contains(@class,'x-menu-item-text') and normalize-space(text())='Voir']",
        "xpath=//li[contains(@class,'x-menu-item')]//span[normalize-space(text())='Voir']",
        "xpath=//a[contains(@class,'x-menu-item') and contains(normalize-space(string(.)),'Voir')]",
        # Broader fallbacks: other common French / English equivalents
        "xpath=//span[contains(@class,'x-menu-item-text') and (normalize-space(text())='Consulter' or normalize-space(text())='Détail' or normalize-space(text())='Detail' or normalize-space(text())='View' or normalize-space(text())='Afficher')]",
        "xpath=//a[contains(@class,'x-menu-item') and (contains(.,'Consulter') or contains(.,'Détail') or contains(.,'View') or contains(.,'Afficher'))]",
    ]:
        candidate = page.locator(selector).first
        if candidate.count():
            try:
                if candidate.is_visible():
                    voir = candidate
                    break
            except Exception:
                continue
    if voir is None:
        # Dump the menu items so we know what is actually being offered.
        try:
            items = page.evaluate(
                """
                () => {
                  const out = [];
                  document.querySelectorAll('.x-menu:not(.x-hide-offsets) .x-menu-item-text, .x-menu .x-menu-item-text').forEach(el => {
                    const s = (el.textContent || '').trim();
                    if (s) out.push(s);
                  });
                  return out;
                }
                """
            )
            log.warning("'Voir' menu item not visible. Available items: %s", items)
        except Exception:
            log.warning("'Voir' menu item not visible (could not enumerate items)")
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False

    try:
        voir.click(force=True, timeout=4000)
        page.wait_for_timeout(1500)
    except Exception as exc:
        log.warning("Click 'Voir' failed: %s", exc)
        return False

    try:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        log.info("Screenshot saved: %s", screenshot_path)
    except Exception as exc:
        log.warning("Failed to save screenshot %s: %s", screenshot_path, exc)
        return False

    # Try to return to the grid (best-effort)
    if not return_after:
        return True
    for selector in [
        "#Component_PAGE_FORM_2_return_null",
        "xpath=//*[contains(@id,'_return_null')]",
    ]:
        btn = page.locator(selector).first
        if btn.count():
            try:
                btn.click(force=True, timeout=3000)
                page.wait_for_timeout(400)
                break
            except Exception:
                continue

    return True


def _filter_view_and_screenshot(page, menu_path: Tuple[str, ...], timestamp: str, label: str) -> bool:
    """Open menu, set Creation Date >= timestamp, execute, view 1st row, screenshot."""
    log.info("UI step → %s", " > ".join(menu_path))
    # Close any leftover work window from a previous step
    try:
        close_work_window(page, label)
    except Exception:
        pass
    if not _open_menu_path(page, menu_path):
        log.warning("Could not open menu %s", menu_path)
        return False
    page.wait_for_timeout(800)

    if not _set_creation_date_filter(page, timestamp):
        return False

    if not _click_execute_search(page):
        return False
    page.wait_for_timeout(1500)

    screenshot_path = SWIFT_SCREENSHOTS_DIR / f"{label}_{int(time.time())}.png"
    return _right_click_first_row_voir_screenshot(page, screenshot_path)


def _execute_and_screenshot_grid(page, menu_path: Tuple[str, ...], label: str) -> bool:
    """Open menu, click Execute Search, screenshot the grid."""
    log.info("UI step → %s", " > ".join(menu_path))
    try:
        close_work_window(page, label)
    except Exception:
        pass
    if not _open_menu_path(page, menu_path):
        log.warning("Could not open menu %s", menu_path)
        return False
    page.wait_for_timeout(800)

    if not _click_execute_search(page):
        return False
    page.wait_for_timeout(2000)

    screenshot_path = SWIFT_SCREENSHOTS_DIR / f"{label}_{int(time.time())}.png"
    try:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        log.info("Grid screenshot saved: %s", screenshot_path)
        return True
    except Exception as exc:
        log.warning("Failed to save grid screenshot: %s", exc)
        return False


def _capture_client_reference(page) -> Optional[str]:
    """Read the displayed `Référence Client` value from the Voir detail page."""
    candidates = [
        "div[id='Field_ComponentclientReference'] label.x-view-value",
        "xpath=//div[@id='Field_ComponentclientReference']//label[contains(@class,'x-view-value')]",
    ]
    for sel in candidates:
        loc = page.locator(sel).first
        if loc.count():
            try:
                txt = (loc.inner_text(timeout=2000) or "").strip()
                if txt:
                    log.info("Captured Référence Client = %s", txt)
                    return txt
            except Exception:
                continue
    log.warning("Référence Client value not found on detail page")
    return None


def _capture_link_ref(page) -> Optional[str]:
    """Read the displayed `Ref Lien` value from the Voir detail page (Marche)."""
    candidates = [
        "div[id='Field_ComponentlinkRef'] label.x-view-value",
        "xpath=//div[@id='Field_ComponentlinkRef']//label[contains(@class,'x-view-value')]",
    ]
    for sel in candidates:
        loc = page.locator(sel).first
        if loc.count():
            try:
                txt = (loc.inner_text(timeout=2000) or "").strip()
                if txt:
                    log.info("Captured Ref Lien = %s", txt)
                    return txt
            except Exception:
                continue
    log.warning("Ref Lien value not found on detail page")
    return None


def _close_current_view_and_return(page) -> None:
    """Best-effort: close the current Voir/detail window before opening next menu."""
    for selector in [
        "#Component_PAGE_FORM_2_return_null",
        "xpath=//*[contains(@id,'_return_null')]",
    ]:
        btn = page.locator(selector).first
        if btn.count():
            try:
                btn.click(force=True, timeout=2000)
                page.wait_for_timeout(300)
                return
            except Exception:
                continue


def _fill_client_reference_filter(page, ref: str) -> bool:
    """Fill the Référence Client criteria input on the current search form."""
    sel = "input[name='Component_PAGE_FORM_0_atomicCriteria_clientReference_criteria']"
    inp = page.locator(sel).first
    if not inp.count():
        log.warning("Client reference criteria input not found")
        return False
    try:
        inp.click(force=True, timeout=4000)
        inp.press("Control+A")
        inp.fill(ref)
        page.wait_for_timeout(150)
        log.info("Client reference filter set: %s", ref)
        return True
    except Exception as exc:
        log.warning("Failed to fill client reference: %s", exc)
        return False


def _click_first_row(page) -> bool:
    """Single-click the first result row to select it."""
    for selector in [
        "[id$='PalmyraGrid_0']",
        "tr[id*='PalmyraGrid_0']",
        "div.x-grid3-body tr.x-grid3-row",
        "tr.x-grid3-row",
    ]:
        try:
            page.wait_for_selector(selector, timeout=4000)
            row = page.locator(selector).first
            if row.count() and row.is_visible():
                row.scroll_into_view_if_needed()
                row.click(force=True, timeout=3000)
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue
    log.warning("No first row to select")
    return False


def _click_validate_button(page) -> bool:
    """Click the Valider button on the Validation form."""
    for selector in [
        "#Component_PAGE_FORM_1_Validate_null em > button",
        "xpath=//*[@id='Component_PAGE_FORM_1_Validate_null']//button",
        "xpath=//button[contains(@class,'x-btn-text') and normalize-space(text())='Valider']",
    ]:
        btn = page.locator(selector).first
        if btn.count():
            try:
                btn.scroll_into_view_if_needed()
                btn.click(force=True, timeout=4000)
                page.wait_for_timeout(800)
                log.info("Clicked Valider button")
                return True
            except Exception:
                continue
    log.warning("Valider button not found / not clickable")
    return False


def _try_click_popup_ok(page) -> bool:
    """Attempt to click OK/close on any visible popup. Returns True if dismissed."""
    # Priority 1: Error popup close icon
    try:
        error_close = page.locator(
            "xpath=//div[contains(@class,'x-window') and not(contains(@style,'display: none'))]"
            "[.//span[contains(@class,'x-window-header-text') and normalize-space(text())='Error']]"
            "//div[contains(@class,'x-tool-close')]"
        ).first
        if error_close.count():
            error_close.click(force=True, timeout=2500)
            page.wait_for_timeout(400)
            log.info("Error popup dismissed via x-tool-close")
            return True
    except Exception:
        pass

    for selector in [
        "xpath=//div[contains(@class,'x-window') and not(contains(@style,'display: none'))]//button[normalize-space(text())='OK']",
        "xpath=//button[normalize-space(text())='OK']",
        "xpath=//button[normalize-space(text())='Ok']",
        "xpath=//button[normalize-space(text())='Oui']",
        "xpath=//button[normalize-space(text())='Yes']",
        "xpath=//span[contains(@class,'x-btn-text') and normalize-space(text())='OK']/ancestor::button[1]",
        "xpath=//span[contains(@class,'x-btn-text') and normalize-space(text())='Oui']/ancestor::button[1]",
        "xpath=//div[contains(@class,'x-window')]//button[contains(@class,'x-btn')][1]",
    ]:
        try:
            btn = page.locator(selector).first
            if btn.count():
                btn.click(force=True, timeout=3000)
                page.wait_for_timeout(500)
                log.info("Popup OK clicked (selector=%s)", selector)
                return True
        except Exception:
            continue
    return False


def _screenshot_and_dismiss_popup(page, screenshot_path: Path) -> bool:
    """Wait for a popup, capture screenshot, click OK to dismiss.

    Retries the OK-click up to 3 times (with waits between attempts) so that
    a delayed popup that wasn't yet rendered when the first attempt ran is
    still caught before the next menu navigation starts.
    """
    # Wait briefly for any popup window/dialog
    page.wait_for_timeout(1500)
    try:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        log.info("Popup screenshot saved: %s", screenshot_path)
    except Exception as exc:
        log.warning("Failed to save popup screenshot: %s", exc)

    # Retry loop: give the popup up to ~4 extra seconds to appear/become clickable
    for attempt in range(4):
        if _try_click_popup_ok(page):
            return True
        if attempt < 3:
            page.wait_for_timeout(1000)

    log.warning("Popup OK button not found — pressing Escape as fallback")
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)
    except Exception:
        pass

    # One final attempt after Escape/Enter in case a new popup appeared
    if _try_click_popup_ok(page):
        return True

    return False


def _monitoring_instruction_client_extended(page, timestamp: str) -> Optional[str]:
    """Open Monitoring Instructions Client, expand criteria, set Date, view first row,
    screenshot, capture Référence Client. Returns the captured reference or None."""
    label = "monitoring_instructions_client"
    log.info("UI step → %s", " > ".join(MONITORING_INSTRUCTIONS_PATH))
    try:
        close_work_window(page, label)
    except Exception:
        pass
    if not _open_menu_path(page, MONITORING_INSTRUCTIONS_PATH):
        return None
    page.wait_for_timeout(800)

    # Expand collapsed fieldset to reveal Date de creation
    _expand_collapsed_fieldsets(page)
    page.wait_for_timeout(300)

    if not _set_creation_date_filter(page, timestamp):
        return None

    # Megara post-processing (MT54X -> Instruction Client) can take 30s-2min
    # after absorption. Poll: click Execute Search, wait for a row, retry.
    # Only count real <tr> rows; the grid <div> container would always be
    # present (even when empty) and would falsely pass the check.
    row_selectors = (
        "div.x-grid3-body tr.x-grid3-row",
        "tr.x-grid3-row",
        "tr[id*='PalmyraGrid_0']",
    )
    poll_timeout_s = int(os.getenv("MIC_POLL_TIMEOUT", "180"))
    poll_interval_s = int(os.getenv("MIC_POLL_INTERVAL", "10"))
    deadline = time.time() + poll_timeout_s
    attempt = 0
    row_found = False
    while time.time() < deadline:
        attempt += 1
        if not _click_execute_search(page):
            return None
        page.wait_for_timeout(1800)
        # Force the grid container into view so virtualized rows render.
        try:
            grid_container = page.locator("[id$='PalmyraGrid_0']").first
            if grid_container.count():
                grid_container.scroll_into_view_if_needed(timeout=2000)
                page.wait_for_timeout(300)
        except Exception:
            pass
        for sel in row_selectors:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                row_found = True
                break
        if row_found:
            log.info("Instruction Client row found on attempt #%d", attempt)
            break
        log.info(
            "No row yet on Monitoring Instructions Client (attempt #%d) — "
            "Megara post-processing pending, retrying in %ds…",
            attempt, poll_interval_s,
        )
        page.wait_for_timeout(poll_interval_s * 1000)

    if not row_found:
        log.warning(
            "Monitoring Instructions Client still empty after %ds — giving up.",
            poll_timeout_s,
        )
        return None

    screenshot_path = SWIFT_SCREENSHOTS_DIR / f"{label}_voir_{int(time.time())}.png"
    if not _right_click_first_row_voir_screenshot(page, screenshot_path, return_after=False):
        return None

    # Give the detail view a moment to fully render
    page.wait_for_timeout(800)
    client_ref = _capture_client_reference(page)
    return client_ref


def _validation_instruction_client(page, client_ref: str) -> bool:
    """Open Validation Instruction Client, filter by client_ref, validate first row,
    screenshot popup and dismiss."""
    label = "validation_instruction_client"
    log.info("UI step → %s", " > ".join(VALIDATION_INSTRUCTION_CLIENT_PATH))
    try:
        _close_all_work_tabs(page)
    except Exception:
        pass
    if not _open_menu_path(page, VALIDATION_INSTRUCTION_CLIENT_PATH):
        return False
    page.wait_for_timeout(800)

    if not _fill_client_reference_filter(page, client_ref):
        return False
    if not _click_execute_search(page):
        return False
    page.wait_for_timeout(1800)

    if not _click_first_row(page):
        return False
    if not _click_validate_button(page):
        return False

    screenshot_path = SWIFT_SCREENSHOTS_DIR / f"{label}_popup_{int(time.time())}.png"
    result = _screenshot_and_dismiss_popup(page, screenshot_path)
    # Extra guard: retry OK dismissal once more so no popup lingers into the next step
    page.wait_for_timeout(500)
    _try_click_popup_ok(page)
    return result


def _monitoring_instruction_marche(page, client_ref: str) -> Optional[str]:
    """Open Monitoring Instructions Marché, filter by client_ref, execute, right-click
    first row, click Voir, screenshot, capture `Ref Lien`. Returns ref or None."""
    label = "monitoring_instructions_marche"
    log.info("UI step → %s", " > ".join(MONITORING_INSTRUCTIONS_MARCHE_PATH))
    try:
        _close_all_work_tabs(page)
    except Exception:
        pass
    if not _open_menu_path(page, MONITORING_INSTRUCTIONS_MARCHE_PATH):
        return None
    page.wait_for_timeout(800)

    if not _fill_client_reference_filter(page, client_ref):
        return None
    if not _click_execute_search(page):
        return None
    page.wait_for_timeout(3500)

    grid_shot = SWIFT_SCREENSHOTS_DIR / f"{label}_grid_{int(time.time())}.png"
    try:
        grid_shot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(grid_shot), full_page=True)
        log.info("Grid screenshot saved: %s", grid_shot)
    except Exception as exc:
        log.warning("Failed to save grid screenshot: %s", exc)

    voir_shot = SWIFT_SCREENSHOTS_DIR / f"{label}_voir_{int(time.time())}.png"
    if not _right_click_first_row_voir_screenshot(page, voir_shot, return_after=False):
        return None
    page.wait_for_timeout(800)
    return _capture_link_ref(page)


def run_megacustody_ui_verification(timestamp: str) -> Optional[str]:
    """End-to-end MegaCustody UI verification after MT54X absorption.

    Returns the captured `Ref Lien` (link reference from Monitoring Instructions
    Marché) if available, so the caller can patch the MT548/MT54Y SWIFT files
    before re-injecting them.
    """
    from playwright.sync_api import sync_playwright

    log.info("=" * 60)
    log.info("UI VERIFICATION (MegaCustody)  |  filter Creation Date >= %s", timestamp)
    log.info("=" * 60)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
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
        link_ref: Optional[str] = None
        try:
            if not _swift_login_megacustody(page):
                log.error("MegaCustody login failed; aborting UI verification.")
                return None

            # 1. Notification > Messages
            _filter_view_and_screenshot(
                page, NOTIFICATION_MESSAGES_PATH, timestamp, "notification_messages"
            )

            # 2. Notification > Swifts > MT54X
            _filter_view_and_screenshot(
                page, NOTIFICATION_SWIFTS_MT54X_PATH, timestamp, "notification_swifts_mt54x"
            )

            # 3. Règlement/Livraison > Instructions Clients > Monitoring Instructions Client
            #    (extended: expand criteria, set Date filter, Voir, screenshot, capture ref)
            client_ref = _monitoring_instruction_client_extended(page, timestamp)

            if client_ref:
                # 4. Validation Instruction Client (filter by captured ref, valider, popup OK)
                _validation_instruction_client(page, client_ref)

                # 5. Monitoring Instructions Marché (filter by captured ref, Voir, capture Ref Lien)
                link_ref = _monitoring_instruction_marche(page, client_ref)
            else:
                log.warning("No client reference captured — skipping Validation & Marché steps.")
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
        return link_ref


def run_post_mt54y_verification(timestamp: str) -> None:
    """After MT548/MT54Y reinjection, reopen MegaCustody, navigate to
    Règlement/Livraison > Instructions Clients > Monitoring Instructions Client,
    filter by Creation Date, right-click first row → Voir, and capture screenshot.
    """
    from playwright.sync_api import sync_playwright

    log.info("=" * 60)
    log.info("POST-MT54Y UI VERIFICATION  |  Monitoring Instructions Client")
    log.info("=" * 60)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
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
            if not _swift_login_megacustody(page):
                log.error("MegaCustody login failed; aborting post-MT54Y verification.")
                return
            client_ref = _monitoring_instruction_client_extended(page, timestamp)
            if client_ref:
                log.info("Post-MT54Y monitoring captured Référence Client = %s", client_ref)
            else:
                log.warning("Post-MT54Y monitoring: no Référence Client captured.")
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


def _rewrite_rela_comm(swift_path: Path, new_ref: str) -> bool:
    """Replace the value after RELA// and COMM// tags in a SWIFT text file."""
    if not swift_path.exists():
        log.warning("SWIFT file not found for rewrite: %s", swift_path)
        return False
    try:
        original = swift_path.read_text(encoding="utf-8")
    except Exception as exc:
        log.warning("Failed reading %s: %s", swift_path, exc)
        return False
    # Replace the value following RELA// or COMM// up to end of line
    patched = re.sub(r"(:20C::(?:RELA|COMM)//)([^\r\n]+)", lambda m: m.group(1) + new_ref, original)
    if patched == original:
        log.info("No RELA/COMM tags found in %s (nothing to replace)", swift_path.name)
        return False
    try:
        swift_path.write_text(patched, encoding="utf-8")
        log.info("Patched %s : RELA/COMM → %s", swift_path.name, new_ref)
        return True
    except Exception as exc:
        log.warning("Failed writing %s: %s", swift_path, exc)
        return False


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Starting automated SWIFT injection process for AWB")
    log.info("Server : %s  |  Drop-box : %s", AWB_HOST, REMOTE_ALLIANCE_PATH)
    log.info("Captured script start timestamp: %s", SCRIPT_START_TIMESTAMP)

    # Clean up any leftover files from previous runs
    cleanup_alliance()

    # Quick diagnostic to confirm ALLIANCE is empty
    diagnose_alliance_dirs()

    if not step_create_instruction():
        log.error("Step 1 (instruction creation) failed — aborting.")
        return

    # ── UI verification flow after MT54X absorption ───────────────────────
    link_ref: Optional[str] = None
    try:
        link_ref = run_megacustody_ui_verification(SCRIPT_START_TIMESTAMP)
    except Exception as exc:
        log.error("MegaCustody UI verification flow raised: %s", exc)

    # ── Patch MT548 / MT54Y with captured Ref Lien, then inject ───────────
    if link_ref:
        log.info("Patching MT548 / MT54Y SWIFT files with Ref Lien = %s", link_ref)
        _rewrite_rela_comm(SWIFT_MT548_1, link_ref)
        _rewrite_rela_comm(SWIFT_MT54Y_1, link_ref)

        if not step_matching():
            log.error("Step 2 (matching MT548) failed.")
        elif not step_settlement():
            log.error("Step 3 (settlement MT54Y) failed.")
        else:
            # Final UI check after MT54Y absorption
            try:
                run_post_mt54y_verification(SCRIPT_START_TIMESTAMP)
            except Exception as exc:
                log.error("Post-MT54Y UI verification raised: %s", exc)
    else:
        log.warning("No Ref Lien captured — skipping MT548 / MT54Y reinjection.")

    log.info("Process_Swift_AWB completed (MT54X + UI verification + reinjection).")


if __name__ == "__main__":
    main()
