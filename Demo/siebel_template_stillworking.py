# siebel_template.py
import json, time, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# -------- Config ----------
ACTIONS_FILE = "recorded_test_siebel.json"   # JSON actions
CONFIG_FILE  = "config.json"                 # user credentials
REPORT_DIR   = "dd_reports"
WAIT_TIMEOUT = 1000                          # ms for selector waiting (generic)
NAV_TIMEOUT  = 30000                         # ms to wait for navigation

# ------------------------
TEMPLATE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

def render(template, row):
    if not isinstance(template, str):
        return template
    return TEMPLATE_RE.sub(lambda m: str(row.get(m.group(1), m.group(0))), template)

def load_actions():
    if not os.path.exists(ACTIONS_FILE):
        raise FileNotFoundError(f"Actions file not found: {ACTIONS_FILE}")
    with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "username" not in data or "password" not in data:
        raise ValueError("Config JSON must contain 'username' and 'password'")
    return data

def choose_initial_url(actions):
    for a in actions:
        url = a.get("pageUrl") or a.get("url")
        if url and isinstance(url, str) and url.startswith("http"):
            return url
    return None

def wait_after_actions(page, timeout_sec=0.05):
    try:
        page.wait_for_load_state('networkidle', timeout=timeout_sec*1000)
    except Exception:
        time.sleep(0.15)

def safe_fill(page, selector, value, row, timeout=WAIT_TIMEOUT):
    sel = render(selector, row)
    val = render(value, row) if value is not None else ""
    if not sel:
        return False, "Empty selector for fill"
    try:
        locator = page.locator(sel)
        locator.wait_for(state="visible", timeout=timeout)
        # handle dropdowns
        tag_name = locator.evaluate("el => el.tagName.toLowerCase()")
        if tag_name == "select":
            locator.select_option(val)
        else:
            locator.fill(str(val), timeout=1000)
        time.sleep(0.15)
        return True, None
    except Exception as e:
        return False, f"safe_fill failed for {sel}: {e}"

def safe_click(page, selector, row, max_click=1, wait_for_nav=False, timeout=30000, nav_timeout=NAV_TIMEOUT):
    sel = render(selector, row)
    if not sel:
        return False, "Empty selector for click"
    try:
        locator = page.locator(sel)
        locator.first.wait_for(state="visible", timeout=timeout)
    except Exception as e:
        return False, f"No element visible for {sel}: {e}"

    count = locator.count() if locator else 0
    if count == 0:
        return False, f"No elements matched selector {sel}"

    clicked = 0
    last_err = None
    for i in range(min(count, max_click)):
        try:
            nth = locator.nth(i)
            if wait_for_nav:
                try:
                    with page.expect_navigation(timeout=nav_timeout):
                        nth.click(timeout=1000)
                except Exception as nav_err:
                    last_err = f"click succeeded but navigation did not occur: {nav_err}"
                time.sleep(0.05)
            else:
                nth.click(timeout=1000)
                time.sleep(0.05)
            clicked += 1
        except Exception as e:
            last_err = str(e)
            time.sleep(0.15)
            continue

    if clicked == 0:
        return False, f"click attempts failed for {sel}; lastErr={last_err}"
    return True, None

def wait_for_home_page(page):
    try:
        page.locator("#j_s_sctrl_tabScreen").wait_for(state="visible", timeout=100000)
    except Exception:
        raise RuntimeError("Home page did not load in time")

def do_action(page, action, row, next_action_pageUrl=None):
    a_type = action.get("type")
    selector = action.get("selector")
    value = action.get("value")
    max_click = int(action.get("maxClick", 1)) if action.get("maxClick") is not None else 1

    if a_type == "goto" or (a_type == "click" and action.get("url") and not selector):
        url = action.get("url") or action.get("pageUrl")
        if url:
            url_r = render(url, row)
            print(f"    -> goto {url_r}")
            page.goto(url_r, timeout=NAV_TIMEOUT)
            wait_after_actions(page, 0.15)
            return

    if a_type == "fill":
        ok, err = safe_fill(page, selector, value, row, timeout=30000)
        if not ok:
            raise RuntimeError(err)
        print(f"    -> fill {render(selector,row)} -> {render(value,row)}")
        return

    if a_type == "click":
        wait_for_nav = False
        if next_action_pageUrl:
            expected = render(next_action_pageUrl, row)
            if expected and expected != page.url:
                wait_for_nav = True
        ok, err = safe_click(page, selector, row, max_click=max_click, wait_for_nav=wait_for_nav, timeout=100000)
        if not ok:
            raise RuntimeError(err)
        print(f"    -> click {render(selector,row)} (max_click={max_click})")
        return

    print(f"    ⚠ skipping unknown action type: {a_type}")

def run_all():
    actions = load_actions()
    config = load_config()
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        results = []

        for idx, row in enumerate([config], start=1):
            print(f"\n=== RUN {idx}: {row} ===")
            page = context.new_page()
            try:
                initial = choose_initial_url(actions)
                if initial:
                    print(f"  navigating to initial URL: {initial}")
                    page.goto(initial, timeout=NAV_TIMEOUT)
                    page.wait_for_load_state('networkidle', timeout=100000)

                # iterate actions from JSON
                for i, action in enumerate(actions):
                    next_page_url = None
                    for a in actions[i+1:]:
                        if a.get("pageUrl") or a.get("url"):
                            next_page_url = a.get("pageUrl") or a.get("url")
                            break
                    do_action(page, action, row, next_action_pageUrl=next_page_url)
                    wait_after_actions(page, 0.15)

                results.append((row, "PASS", ""))
                print("  ✅ Run succeeded")
            except Exception as e:
                results.append((row, "FAIL", str(e)))
                print(f"  ❌ Run failed: {e}")
            finally:
                try:
                    page.close()
                except Exception:
                    pass

        report_path = Path(REPORT_DIR) / "report.txt"
        with open(report_path, "w", encoding="utf-8") as rf:
            for row, status, note in results:
                rf.write(f"{row} -> {status} {note}\n")
        print(f"\nReports written to {REPORT_DIR}")

        context.close()
        browser.close()

if __name__ == "__main__":
    run_all()
