from playwright.sync_api import sync_playwright
import json

# Load your recorded JSON
with open("recorded_test.json") as f:
    actions = json.load(f)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headless=True for no browser UI
    page = browser.new_page()

    for action in actions:
        # Wait for the element to appear
        try:
            page.wait_for_selector(action['selector'], timeout=5000)
        except:
            print(f"Element not found: {action['selector']}")
            continue

        if action['type'] == 'fill':
            page.fill(action['selector'], action['value'])
        elif action['type'] == 'click':
            # If click navigates, wait for navigation
            with page.expect_navigation(timeout=5000):
                page.click(action['selector'])
        page.wait_for_timeout(200)  # small delay to mimic human behavior

    browser.close()
