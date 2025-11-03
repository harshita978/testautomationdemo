# runtest.py
from playwright.sync_api import sync_playwright

BASE_SIEBEL_URL = "https://celvpvm04294.us.oracle.com:9001/siebel/app/callcenter/enu?SWECmd=Start&"

USERNAME = "SADMIN"
PASSWORD = "SIEBEL"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--ignore-certificate-errors"])
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    print("Opening Siebel login page...")
    page.goto(BASE_SIEBEL_URL, timeout=60000, wait_until="domcontentloaded")

    # Wait for login fields and fill them
    page.fill("input[name='SWEUserName']", USERNAME)
    page.fill("input[name='SWEPassword']", PASSWORD)

    # Submit login
    page.press("input[name='SWEPassword']", "Enter")

    print("✅ Login submitted. Browser will stay open on the Siebel home screen.")
    print("👉 You can now continue working manually inside the logged-in session.")

    # Keep the script alive so the browser stays open
    page.wait_for_timeout(60_000 * 60)  # keep open for 1 hour
