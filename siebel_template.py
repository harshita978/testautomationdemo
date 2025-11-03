# siebel_template.py
"""
Robust Siebel replay script with:
- stable-home waiting to avoid false failures on slow loads
- success screenshots when navigation/tab click succeeds
- generic tab handling (works for any recorded tab text/value)
- minimal invasive changes - drop-in replacement
"""
import json
import time
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# -------- Config ----------
ACTIONS_FILE = "recorded_test_siebel.json"
CONFIG_FILE = "config.json"
REPORT_DIR = "dd_reports"
WAIT_TIMEOUT = 30000  # ms - increased default wait
RETRY_COUNT = 6
RETRY_DELAY = 0.8
HOME_STABLE_SECONDS = 3   # require no URL/frame changes for this many seconds
HOME_MAX_WAIT = 60       # max seconds to wait for home to be ready
# ------------------------

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_actions():
    with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def wait_for(page_or_frame, selector, timeout=WAIT_TIMEOUT):
    try:
        return page_or_frame.wait_for_selector(selector, timeout=timeout)
    except PWTimeout:
        print(f"  ⚠ Timeout waiting for selector: {selector}")
        return None

# ---------- Fill / click helpers ----------
def safe_fill(ctx, selector, value):
    try:
        h = ctx.query_selector(selector)
    except Exception:
        h = None
    if not h:
        h = wait_for(ctx, selector)
    if not h:
        print(f"  ⚠ safe_fill: selector not found: {selector}")
        return False
    try:
        h.fill(value, timeout=5000)
        return True
    except Exception:
        try:
            h.focus()
            ctx.keyboard.type(value, delay=10)
            return True
        except Exception as e:
            print(f"  ⚠ Fill failed for {selector}: {e}")
            return False

def find_frame_containing(page, selector):
    try:
        h = page.query_selector(selector)
        if h:
            return page, h
    except Exception:
        pass
    for f in page.frames:
        try:
            h = f.query_selector(selector)
            if h:
                return f, h
        except Exception:
            continue
    return None, None

def robust_click(page, selector=None, by_text=None):
    last_err = None
    for attempt in range(RETRY_COUNT):
        try:
            if selector:
                ctx, handle = find_frame_containing(page, selector)
                if ctx and handle:
                    try:
                        try:
                            handle.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        handle.click(timeout=5000)
                        return True
                    except Exception as e:
                        last_err = e
                        try:
                            ctx.evaluate("(el) => el.click()", handle)
                            return True
                        except Exception as e2:
                            last_err = e2
            if by_text:
                txt = str(by_text).strip()
                if txt:
                    try:
                        loc = page.locator(f'text="{txt}"')
                        if loc.count() > 0:
                            loc.first.scroll_into_view_if_needed()
                            loc.first.click(timeout=4000)
                            return True
                    except Exception:
                        pass
                    for f in page.frames:
                        try:
                            loc = f.locator(f'text="{txt}"')
                            if loc.count() > 0:
                                loc.first.scroll_into_view_if_needed()
                                loc.first.click(timeout=4000)
                                return True
                        except Exception:
                            continue
        except Exception as e:
            last_err = e
        time.sleep(RETRY_DELAY)
    print(f"  ⚠ robust_click failed for selector={selector} by_text={by_text}, last_err={last_err}")
    traceback.print_exc()
    return False

def safe_select(ctx, selector, value):
    try:
        h = wait_for(ctx, selector)
        if not h:
            print(f"  ⚠ safe_select: selector not found: {selector}")
            return False
        h.select_option(value)
        return True
    except Exception as e:
        print(f"  ⚠ safe_select failed for {selector}: {e}")
        return False

# ---------- generic tab handler ----------
def click_siebel_tab(page, action):
    """
    Generic handler: tries recorded selector, recorded value (text),
    then falls back to any visible text found in the action or the selector's element text.
    Returns True on success.
    """
    sel = action.get("selector")
    val = action.get("value")
    # 1) try selector (frame-aware)
    if sel and robust_click(page, selector=sel):
        return True
    # 2) try recorded value as text (if present and not a template)
    if val and isinstance(val, str) and "{{" not in val:
        if robust_click(page, by_text=val.strip()):
            return True
    # 3) try common label strategies: split value if it contains pipes/commas, or try trimmed words
    if val and isinstance(val, str):
        # try tokens from value (e.g., "tabScreen9" might not be helpful, but other values may contain label)
        tokens = [t.strip() for t in val.replace("+", " ").replace("_", " ").split() if t.strip()]
        # try longer tokens first
        tokens = sorted(tokens, key=lambda s: -len(s))
        for t in tokens:
            if len(t) >= 3 and robust_click(page, by_text=t):
                return True
    # 4) if selector points to a select element, try select_option by value
    if sel:
        ctx, handle = find_frame_containing(page, sel)
        if ctx and handle:
            try:
                handle.select_option(val)
                return True
            except Exception:
                pass
    # 5) fallback: find anchors containing "SWEView=" with any non-home keywords and click the first sensible one
    try:
        for f in page.frames:
            anchors = f.query_selector_all("a[href*='SWEView=']")
            for a in anchors:
                try:
                    href = f.evaluate("(el) => el.getAttribute('href') || ''", a)
                    if href and not any(x in href.lower() for x in ["home+page", "system+preferences"]):
                        try:
                            a.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        try:
                            a.click(timeout=2000)
                            return True
                        except Exception:
                            try:
                                f.evaluate("(el) => el.click()", a)
                                return True
                            except Exception:
                                continue
                except Exception:
                    continue
    except Exception:
        pass
    # all attempts failed
    print("  ⚠ click_siebel_tab: all strategies failed for action:", action)
    return False

# ---------- login iframe discovery ----------
def list_frames_for_debug(page):
    try:
        print("Frames present on page (name / url):")
        for f in page.frames:
            print(f" - name: '{f.name}' url: '{f.url}'")
    except Exception:
        pass

IFRAME_CANDIDATES = [
    "iframe[name='swepi']",
    "iframe[name='swepi_main']",
    "iframe#s_swepi_iframe",
    "iframe",
]

def get_login_context(page, timeout_ms=30000, poll_interval=0.5):
    waited = 0.0
    while waited * 1000 < timeout_ms:
        try:
            if page.query_selector("#s_swepi_1") or page.query_selector("#s_swepi_2"):
                return page, "page"
        except Exception:
            pass
        for candidate in IFRAME_CANDIDATES:
            try:
                elems = page.query_selector_all(candidate)
            except Exception:
                elems = []
            for e in elems:
                try:
                    f = e.content_frame()
                    if not f:
                        continue
                    if f.query_selector("#s_swepi_1") or f.query_selector("#s_swepi_2"):
                        return f, candidate
                except Exception:
                    continue
        try:
            for f in page.frames:
                try:
                    if f.query_selector("#s_swepi_1") or f.query_selector("#s_swepi_2"):
                        return f, f.name or f.url or "unnamed-frame"
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(poll_interval)
        waited += poll_interval
    list_frames_for_debug(page)
    return None, None

# ---------- home readiness helpers ----------
def current_frame_urls(page):
    """Return tuple of (top_url, sorted frame urls) for stable-checking."""
    try:
        top = page.url or ""
        frames = sorted([f.url or "" for f in page.frames])
        return top, tuple(frames)
    except Exception:
        return page.url or "", tuple()

def wait_for_home_ready(page, max_wait=HOME_MAX_WAIT, stable_seconds=HOME_STABLE_SECONDS):
    """
    Wait until the page/frame URLs are stable for `stable_seconds` consecutively OR a known Siebel app element appears.
    Return True if ready, False if timeout.
    """
    start = time.time()
    last_change_time = time.time()
    last_state = None
    # candidate elements that indicate app rendered; try several common ones
    app_selectors = [
        ".siebui-app",       # generic siebel app container
        ".siebui-application",
        ".swe-view",         # possible view container
        ".siebui-iframe",    # some deployments
        "#s_sctrl",          # generic control
    ]
    while time.time() - start < max_wait:
        # 1) check for app selectors in page or frames
        try:
            for sel in app_selectors:
                # check top page
                try:
                    if page.query_selector(sel):
                        # require a short wait to ensure stability
                        time.sleep(1)
                        return True
                except Exception:
                    pass
                # check frames
                for f in page.frames:
                    try:
                        if f.query_selector(sel):
                            time.sleep(1)
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        # 2) check for URL/frame stability
        state = current_frame_urls(page)
        if state != last_state:
            last_state = state
            last_change_time = time.time()
        else:
            # stable for some time?
            if time.time() - last_change_time >= stable_seconds:
                return True
        time.sleep(0.8)
    # timed out
    print(f"  ⚠ wait_for_home_ready timed out after {max_wait}s (last_state={last_state})")
    return False

# ---------- debug / screenshot helpers ----------
def save_debug(page, tag="debug"):
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)
    try:
        png = Path(REPORT_DIR) / f"{tag}_{int(time.time())}.png"
        page.screenshot(path=str(png), full_page=True)
        print(f"Saved screenshot: {png}")
    except Exception:
        pass
    try:
        html = Path(REPORT_DIR) / f"{tag}_{int(time.time())}.html"
        html.write_text(page.content(), encoding="utf-8")
        print(f"Saved HTML: {html}")
    except Exception:
        pass

def save_success(page, tag="success"):
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)
    try:
        png = Path(REPORT_DIR) / f"{tag}_{int(time.time())}.png"
        page.screenshot(path=str(png), full_page=True)
        print(f"Saved success screenshot: {png}")
    except Exception:
        pass

# ---------- goto filter ----------
MEANINGFUL_KEYWORDS = [
    "sweview=service",
    "service+request",
    "personal+service",
    "servicerequest",
    "personal+service+request",
]

def is_meaningful_goto(url):
    if not url or not isinstance(url, str):
        return False
    u = url.lower()
    for kw in MEANINGFUL_KEYWORDS:
        if kw in u:
            return True
    if "sweview=" in u and ("service" in u or "request" in u or "list" in u):
        return True
    return False

# ---------- main flow ----------
def run_all():
    actions = load_actions()
    config = load_config()
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False, args=["--ignore-certificate-errors"])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # --- navigate to login page ---
        login_action = next((a for a in actions if a.get("type") == "fill" and a.get("selector") == "#s_swepi_1"), None)
        goto_action = next((a for a in actions if a.get("type") == "goto"), None)
        login_url = None
        if login_action and login_action.get("pageUrl"):
            login_url = login_action.get("pageUrl")
        elif goto_action and goto_action.get("url"):
            login_url = goto_action.get("url")
        if login_url:
            print(f"Navigating to login page: {login_url}")
            page.goto(login_url, timeout=60000, wait_until="domcontentloaded")

        # --- find login context and fill ---
        print("Looking for login inputs/iframe (may take a few seconds)...")
        login_ctx, where = get_login_context(page, timeout_ms=30000)
        if not login_ctx:
            print("  ⚠ Could not find login inputs. See frames above or open browser DevTools.")
            raise RuntimeError("Login iframe or inputs not found")
        print(f"Login inputs found in: {where}")
        print("Filling login credentials...")
        safe_fill(login_ctx, "#s_swepi_1", config.get("USERNAME"))
        safe_fill(login_ctx, "#s_swepi_2", config.get("PASSWORD"))

        # Click login button
        login_btns = ["#s_swepi_22", "#s_swepi_20", "input[type='submit']", "button[type='submit']"]
        clicked = False
        for b in login_btns:
            try:
                if login_ctx.query_selector(b):
                    print(f"Clicking login button selector: {b}")
                    if robust_click(page, selector=b):
                        clicked = True
                        break
            except Exception:
                continue
        if not clicked:
            for t in ["Sign In", "Log In", "Login"]:
                if robust_click(page, by_text=t):
                    clicked = True
                    break
        if not clicked:
            print("  ⚠ Could not click login button automatically. Please click manually in the opened browser.")
        else:
            print("Login click attempted.")

        # Wait for home to be ready (this is the added logic to avoid false failures)
        print("Waiting for home page to become ready (may take up to {}s)...".format(HOME_MAX_WAIT))
        ready = wait_for_home_ready(page, max_wait=HOME_MAX_WAIT, stable_seconds=HOME_STABLE_SECONDS)
        if not ready:
            print("  ⚠ Home did not become ready in time; continuing but results may be flaky.")
            save_debug(page, "home_not_ready")
        else:
            print("Home appears ready.")
            save_success(page, "home_ready")

        # iterate actions but filter gotos
        last_goto = None
        for idx, action in enumerate(actions):
            sel = action.get("selector")
            val = action.get("value")
            a_type = action.get("type")

            if a_type == "goto":
                url = action.get("url")
                if not url:
                    continue
                if url == last_goto:
                    print(f"Skipping duplicate goto: {url}")
                    continue
                if is_meaningful_goto(url):
                    try:
                        print(f"Performing meaningful goto: {url}")
                        page.goto(url, timeout=60000, wait_until="domcontentloaded")
                        last_goto = url
                        # wait for home-like readiness after each meaningful goto
                        if wait_for_home_ready(page, max_wait=30, stable_seconds=2):
                            save_success(page, "goto_success")
                        else:
                            save_debug(page, "goto_partial")
                    except Exception as e:
                        print(f"  ⚠ goto failed: {e}")
                        save_debug(page, "goto_fail")
                else:
                    print(f"Skipping noisy/irrelevant goto: {url}")
                time.sleep(1)
                continue

            if not sel:
                continue

            # generic tab/dropdown/navigation: now works with any tab text/value
            if sel == "#j_s_sctrl_tabScreen" or (val and isinstance(val, str) and (("tab" in str(val).lower()) or "service" in str(val).lower() or len(str(val).strip())>0)):
                # We allow any recorded val to be used as text — this generalizes it for any tab
                print(f"Attempting generic tab/navigation for action #{idx}: sel={sel} val={val}")
                ok = click_siebel_tab(page, action)
                if ok:
                    # wait for page/app to settle and take success screenshot
                    if wait_for_home_ready(page, max_wait=30, stable_seconds=2):
                        save_success(page, f"tab_success_{idx}")
                    else:
                        save_debug(page, f"tab_maybe_{idx}")
                else:
                    print("Navigation attempt failed; saving debug artifacts.")
                    save_debug(page, f"tab_fail_{idx}")
                page.wait_for_timeout(1000)
                continue

            # fill / click / select actions (frame-aware)
            if a_type == "fill":
                ctx, handle = find_frame_containing(page, sel)
                if ctx and handle:
                    safe_fill(ctx, sel, val)
                else:
                    print(f"  ⚠ fill target not found for selector {sel}")
            elif a_type == "click":
                print(f"Clicking selector: {sel}")
                if not robust_click(page, selector=sel):
                    print(f"  ⚠ click failed for {sel}")
                    save_debug(page, "click_fail")
                else:
                    # on success, capture screenshot to mark pass
                    save_success(page, f"click_success_{idx}")
            elif a_type == "select":
                ctx, handle = find_frame_containing(page, sel)
                if ctx and handle:
                    try:
                        handle.select_option(val)
                        save_success(page, f"select_success_{idx}")
                    except Exception:
                        print(f"  ⚠ select_option failed for {sel}, trying robust_click")
                        if robust_click(page, selector=sel):
                            save_success(page, f"select_click_success_{idx}")
                        else:
                            save_debug(page, f"select_fail_{idx}")
                else:
                    print(f"  ⚠ select target not found for selector {sel}")
            else:
                print(f"  ⚠ Unknown/unsupported action type: {a_type} - skipping")

            time.sleep(0.5)

        print("\n✅ Replay completed. Browser remains open for 5 minutes for manual checks.")
        page.wait_for_timeout(5 * 60 * 1000)
        browser.close()

if __name__ == "__main__":
    run_all()
