#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture KEATS login state as a Playwright auth-state JSON file.")
    parser.add_argument("--course-url", required=True)
    parser.add_argument("--auth-state", required=True, type=Path)
    parser.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    args = parser.parse_args()

    args.auth_state.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser_type = getattr(playwright, args.browser)
        browser = browser_type.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(args.course_url, wait_until="domcontentloaded")

        print("Complete the KEATS login in the opened browser window.")
        print("After the course page is visible, return here and press Enter to save auth state.")
        input()

        context.storage_state(path=str(args.auth_state))
        browser.close()

    print(f"Saved auth state to {args.auth_state}")


if __name__ == "__main__":
    main()
