"""Playwright-based smoke flow for the Mega CDG clients."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from playwright.sync_api import Browser, Page, sync_playwright

CLIENT_ID = "MegaCommon"
BASE_HOST = "https://10.1.140.42"
AUTH_URL = (
    "http://10.1.145.37:8780/auth/realms/EXTERNAL/protocol/openid-connect/auth"
    "?response_type=code&client_id=MegaCommon"
    "&redirect_uri=https%3A%2F%2F10.1.140.42%2FMegaCommon%2F"
    "&state=1e55198f-bb41-49ce-93b0-a34b073e3e0d&login=true&scope=openid"
)

MODULE_PATHS: Sequence[str] = [
    "MegaCommon",
    "MegaCustody",
    "MegaCor",
    "MegaTrade",
    "MegaCompliance",
    "MegaLend",
    "MegaAccounting",
]


def build_module_url(module_name: str) -> str:
    """Return the canonical entry URL for a module."""

    return f"{BASE_HOST}/{module_name}/"


def login(page: Page, username: str, password: str) -> None:
    """Automate the Keycloak flow for the CDG internal users."""

    page.goto(AUTH_URL, wait_until="networkidle")
    page.locator("#social-internal-keycloak-oidc-link").click()
    page.wait_for_url("**/realms/CDG/**", wait_until="networkidle")

    checkbox = page.locator("#userTransform")
    if checkbox.is_checked():
        checkbox.click()

    page.fill("#username", username)
    page.fill("#password", password)

    # Domain defaults to CDG CAPITAL so no explicit selection is required.
    page.get_by_role("button", name="Submit").click()

    page.wait_for_url("**/MegaCommon/**", wait_until="networkidle")


def visit_modules(
    page: Page,
    save_screenshots: bool,
    screenshot_dir: Path | None,
    module_names: Sequence[str],
) -> None:
    """Open each module page to ensure the landing screen loads."""

    for module in module_names:
        url = build_module_url(module)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1_000)

        print(f"Visited {module} at {url}")

        if save_screenshots and screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=screenshot_dir / f"{module}.png", full_page=True)


def run(
    username: str,
    password: str,
    headless: bool,
    save_screenshots: bool,
    screenshot_dir: Path | None,
    modules: Sequence[str] | None,
) -> None:
    """Drive the browser and execute the megara smoke path."""

    module_names = tuple(modules or MODULE_PATHS)

    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.launch(headless=headless)
        try:
            page = browser.new_page()
            login(page, username=username, password=password)

            if module_names:
                visit_modules(page, save_screenshots, screenshot_dir, module_names)
        finally:
            browser.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke CDG client navigation")
    parser.add_argument(
        "--username",
        default="migration",
        help="Keycloak username (default: migration)",
    )
    parser.add_argument(
        "--password",
        default="Vermeg+123",
        help="Keycloak password (default: Vermeg+123)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless instead of with UI.",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        help="Directory where module screenshots are written.",
    )
    parser.add_argument(
        "--save-screenshots",
        action="store_true",
        help="Capture each module landing page in the screenshot directory.",
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        help=(
            "Only visit the supplied module names. Valid values: "
            + ", ".join(MODULE_PATHS)
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        username=args.username,
        password=args.password,
        headless=args.headless,
        save_screenshots=args.save_screenshots,
        screenshot_dir=args.screenshot_dir,
        modules=args.modules,
    )


if __name__ == "__main__":
    main()
