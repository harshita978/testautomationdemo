from playwright.sync_api import sync_playwright
import json

# Load recorded JSON
with open("recorded_test.json") as f:
    actions = json.load(f)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # Start with the first page
    page.goto("https://www.flipkart.com")  # or redbus

    for action in actions:
        try:
            page.wait_for_selector(action['selector'], timeout=5000)
        except:
            print(f"Element not found: {action['selector']}")
            continue

        if action['type'] == 'fill':
            page.fill(action['selector'], action['value'])
        elif action['type'] == 'click':
            page.click(action['selector'])
            # Small delay to allow SPA to update DOM
            page.wait_for_timeout(1000)

    browser.close()
