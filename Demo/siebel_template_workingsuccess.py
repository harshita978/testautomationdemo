# siebel_template_workingsuccess.py
"""
Robust Siebel replay script with:
- stable-home waiting to avoid false failures on slow loads
- success screenshots when navigation/tab click succeeds
- generic tab handling (works for any recorded tab text/value)
- generic Pick Applet handler (works across Siebel pick dialogs)
- Page/Frame-safe helpers to avoid AttributeError: 'Page' object has no attribute 'page'
"""
import json
import time
import re
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout, expect

# -------- Config ----------
ACTIONS_FILE = "recorded_test_SR.json"
CONFIG_FILE = "config_workingsuccess.json"
REPORT_DIR = "dd_reports"
WAIT_TIMEOUT = 30000  # ms
RETRY_COUNT = 6
RETRY_DELAY = 0.8
HOME_STABLE_SECONDS = 3
HOME_MAX_WAIT = 60
# ------------------------

# ---------- NEW: helpers for Pick Applet ----------
GRID_ID_RE = re.compile(r"#\d+_s_\d+_l_[A-Za-z0-9_]+$")

IFRAME_CANDIDATES = [
    "iframe[name='swepi']",
    "iframe[name='swepi_main']",
    "iframe#s_swepi_iframe",
    "iframe",
]

def iter_frames(obj):
    """
    Return a list of frames from either a Page or a Frame.
    - If obj is Page: use obj.frames
    - If obj is Frame: use obj.page.frames
    """
    # Try Page.frames
    try:
        frs = getattr(obj, "frames")
        return list(frs)
    except Exception:
        pass
    # Try Frame.page.frames
    try:
        pg = getattr(obj, "page")
        return list(pg.frames)
    except Exception:
        return []

def siebel_main_frame(page):
    """Return the most likely Siebel app frame (swepi*), falling back to top page."""
    for css in IFRAME_CANDIDATES:
        try:
            els = page.query_selector_all(css)
        except Exception:
            els = []
        for e in els:
            try:
                f = e.content_frame()
                if f and f.url:
                    return f
            except Exception:
                continue
    return page  # fallback

def visible_pick_dialog(container):
    """
    Find a visible jQuery-UI/Siebel pick dialog in either a Page or a Frame.
    """
    dialog_selectors = [".ui-dialog:visible", "[role='dialog']:visible", ".siebui-dialog:visible"]

    # 1) Check the container itself
    for sel in dialog_selectors:
        try:
            loc = container.locator(sel).first
            if loc and loc.count() > 0:
                try:
                    loc.wait_for(timeout=3000)
                    return loc
                except Exception:
                    pass
        except Exception:
            continue

    # 2) Check all frames reachable from this container
    for f in iter_frames(container):
        for sel in dialog_selectors:
            try:
                loc = f.locator(sel).first
                if loc and loc.count() > 0:
                    try:
                        loc.wait_for(timeout=3000)
                        return loc
                    except Exception:
                        pass
            except Exception:
                continue

    return None

def find_grid_cell(dialog_loc, target_text):
    """
    Resolve a grid cell in the pick dialog by role/title/text (in that order).
    """
    # 1) accessible name via role
    cell = dialog_loc.get_by_role("gridcell", name=target_text)
    if cell.count() > 0:
        return cell.first
    # 2) exact title attribute
    cell = dialog_loc.locator(f'td[role="gridcell"][title="{target_text}"]')
    if cell.count() > 0:
        return cell.first
    # 3) contains text
    cell = dialog_loc.locator('td[role="gridcell"]', has_text=target_text)
    if cell.count() > 0:
        return cell.first
    return None

def click_ok_in_dialog(dialog_loc):
    """
    Click OK (or press Enter) in the pick dialog.
    """
    for sel in ["button[title='OK']",
                "button:has-text('OK')",
                "[aria-label='OK']",
                "#ui-id-167"]:
        try:
            btn = dialog_loc.locator(sel).first
            if btn.count() > 0:
                try:
                    btn.click(timeout=3000)
                    return True
                except Exception:
                    try:
                        dialog_loc.evaluate("(el)=>el.click()", btn)
                        return True
                    except Exception:
                        pass
        except Exception:
            continue
    try:
        dialog_loc.press("Enter")
        return True
    except Exception:
        return False

def pick_applet_select(page, action):
    """
    Generic pick applet flow:
    - find the dialog in the swepi frame
    - pick cell by text/title/name (from action: pickValue/value/text/name)
    - click/dblclick, or click + OK
    - returns True on success
    """
    # Candidate target from action
    target = None
    for key in ("pickValue", "value", "text", "name"):
        v = action.get(key)
        if isinstance(v, str) and v.strip() and "{{" not in v:
            target = v.strip()
            break

    frame = siebel_main_frame(page)
    dialog = visible_pick_dialog(frame)
    if not dialog:
        # last-chance: scan all frames from the page object
        for f in iter_frames(page):
            dialog = visible_pick_dialog(f)
            if dialog:
                frame = f
                break
    if not dialog:
        print("  ⚠ pick_applet_select: no visible pick dialog detected.")
        return False

    # ensure grid is visible
    try:
        grid = dialog.locator('table, [role="grid"]').first
        grid.wait_for(timeout=5000)
    except Exception:
        pass  # not fatal

    # If we have a target, resolve the cell robustly
    cell = None
    if target:
        cell = find_grid_cell(dialog, target)

    # If no target (or not found), fall back to the first selectable row/cell
    if not cell:
        try:
            candidates = dialog.locator('td[role="gridcell"]').filter(has_text=re.compile(r'.+')).first
            if candidates.count() == 0:
                candidates = dialog.locator('td').first
            if candidates.count() > 0:
                cell = candidates
        except Exception:
            pass

    if not cell:
        print("  ⚠ pick_applet_select: could not locate any clickable grid cell.")
        return False

    # Try click then dblclick fallback
    try:
        cell.scroll_into_view_if_needed()
    except Exception:
        pass
    try:
        cell.click(timeout=4000)
    except Exception:
        try:
            cell.dblclick(timeout=4000)
            return True
        except Exception:
            pass

    # If single-click didn’t close, try OK
    if click_ok_in_dialog(dialog):
        return True

    # Final fallback: double-click after OK attempt
    try:
        cell.dblclick(timeout=4000)
        return True
    except Exception:
        print("  ⚠ pick_applet_select: interaction failed after click/dblclick/OK attempts.")
        return False

# ---------- existing helpers ----------
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
                            if f and loc.count() > 0:
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
    # 3) try tokens from value
    if val and isinstance(val, str):
        tokens = [t.strip() for t in val.replace("+", " ").replace("_", " ").split() if t.strip()]
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
    # 5) fallback: try anchors with SWEView
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
    app_selectors = [
        ".siebui-app",
        ".siebui-application",
        ".swe-view",
        ".siebui-iframe",
        "#s_sctrl",
    ]
    while time.time() - start < max_wait:
        try:
            for sel in app_selectors:
                try:
                    if page.query_selector(sel):
                        time.sleep(1)
                        return True
                except Exception:
                    pass
                for f in page.frames:
                    try:
                        if f.query_selector(sel):
                            time.sleep(1)
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        state = current_frame_urls(page)
        if state != last_state:
            last_state = state
            last_change_time = time.time()
        else:
            if time.time() - last_change_time >= stable_seconds:
                return True
        time.sleep(0.8)
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

        # Wait for home to be ready
        print(f"Waiting for home page to become ready (may take up to {HOME_MAX_WAIT}s)...")
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

            if not sel and a_type != "goto":
                continue

            # generic tab/dropdown/navigation
            if sel == "#j_s_sctrl_tabScreen" or (val and isinstance(val, str) and (("tab" in str(val).lower()) or "service" in str(val).lower() or len(str(val).strip())>0)):
                print(f"Attempting generic tab/navigation for action #{idx}: sel={sel} val={val}")
                ok = click_siebel_tab(page, action)
                if ok:
                    if wait_for_home_ready(page, max_wait=30, stable_seconds=2):
                        save_success(page, f"tab_success_{idx}")
                    else:
                        save_debug(page, f"tab_maybe_{idx}")
                else:
                    print("Navigation attempt failed; saving debug artifacts.")
                    save_debug(page, f"tab_fail_{idx}")
                page.wait_for_timeout(1000)
                continue

            # ----- NEW: Detect & handle Pick Applet clicks generically -----
            if a_type == "click":
                looks_like_grid_cell = bool(sel and GRID_ID_RE.match(sel))
                if looks_like_grid_cell:
                    print(f"[PickApplet] Attempting generic pick for action #{idx}: selector={sel}")
                    ok = pick_applet_select(page, action)
                    if ok:
                        save_success(page, f"pick_success_{idx}")
                    else:
                        # As a fallback, try the original selector and/or text
                        if robust_click(page, selector=sel) or (val and robust_click(page, by_text=val)):
                            save_success(page, f"pick_fallback_clicked_{idx}")
                        else:
                            print("  ⚠ pick applet selection failed; saving debug.")
                            save_debug(page, f"pick_fail_{idx}")
                    time.sleep(0.5)
                    continue
                else:
                    # Not an obvious grid id; try usual click first
                    print(f"Clicking selector: {sel}")
                    if not robust_click(page, selector=sel):
                        print("  ⤷ normal click failed; probing pick dialog...")
                        if pick_applet_select(page, action):
                            save_success(page, f"pick_probe_success_{idx}")
                        else:
                            print(f"  ⚠ click failed for {sel}")
                            save_debug(page, "click_fail")
                    else:
                        save_success(page, f"click_success_{idx}")
                    time.sleep(0.5)
                    continue

            # fill / select actions
            if a_type == "fill":
                ctx, handle = find_frame_containing(page, sel)
                if ctx and handle:
                    safe_fill(ctx, sel, val)
                else:
                    print(f"  ⚠ fill target not found for selector {sel}")
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
