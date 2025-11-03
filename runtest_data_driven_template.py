# runtest_data_driven_template.py
import json, time, os, re, csv, io, datetime, math
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ---------- External reporting libs ----------
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ======== Config ========
# Root location where the project lives (your path)
BASE_DIR = r"C:\Users\Harshita Paliwal\Documents\TestAutomation\test-automation-demo"

ACTIONS_FILE = "recorded_test.json"     # generic recorded actions (your JSON)
DATA_CSV     = "users.csv"              # test data CSV (headers must match placeholders)
REPORT_DIR   = "dd_reports"             # will be placed inside BASE_DIR
WAIT_TIMEOUT = 2000
NAV_TIMEOUT  = 5000

# Optional: force script to start at a particular URL (set to None to use JSON first pageUrl)
START_URL = "http://127.0.0.1:5000"     # e.g. "http://192.168.29.63:5000/"

# Screenshot/reporting toggles
SCREENSHOT_EVERY_ACTION   = True   # before & after each action
SCREENSHOT_ON_FAILURE     = True   # on fail
SCREENSHOT_ON_SUCCESS_END = True   # final page after last action per run

# Screenshot image size for PDF thumbnails (pixels-ish; ReportLab scales by width)
PDF_THUMB_WIDTH = 150

# ========================

TEMPLATE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

def ensure_base(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(BASE_DIR) / p
    return p

def render(template, row):
    if not isinstance(template, str):
        return template
    return TEMPLATE_RE.sub(lambda m: str(row.get(m.group(1), m.group(0))), template)

def load_actions():
    actions_path = ensure_base(ACTIONS_FILE)
    if not actions_path.exists():
        raise FileNotFoundError(f"Actions file not found: {actions_path}")
    with open(actions_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_data():
    data_path = ensure_base(DATA_CSV)
    if not data_path.exists():
        raise FileNotFoundError(f"Data CSV not found: {data_path}")
    rows = []
    with open(data_path, newline='', encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({k.strip(): (v.strip() if isinstance(v, str) else v) for k,v in r.items()})
    if not rows:
        raise ValueError("CSV has no rows")
    return rows

def choose_initial_url(actions):
    # Priority: START_URL env/config -> first explicit pageUrl in actions -> None
    if START_URL:
        return START_URL
    env_start = os.environ.get("START_URL")
    if env_start:
        return env_start
    for a in actions:
        url = a.get("pageUrl") or a.get("url")
        if url and isinstance(url, str) and url.startswith("http"):
            if "google.com" in url or "bing.com" in url:
                continue
            return url
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

def _timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _safe_name(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)[:120]

def take_screenshot(page, folder: Path, prefix: str) -> Optional[str]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        fname = f"{prefix}_{int(time.time()*1000)}.png"
        fp = folder / fname
        page.screenshot(path=str(fp), full_page=True)
        return str(fp)
    except Exception:
        return None

def safe_fill(page, selector, value, row, timeout=WAIT_TIMEOUT):
    sel = render(selector, row)
    val = render(value, row) if value is not None else ""
    if not sel:
        return False, f"Empty selector for fill"
    try:
        locator = page.locator(sel)
        locator.wait_for(state="visible", timeout=timeout)
        locator.fill(str(val), timeout=1000)
        time.sleep(0.15)
        return True, None
    except Exception as e:
        return False, f"safe_fill failed for {sel}: {e}"

def safe_click(page, selector, row, max_click=1, wait_for_nav=False, timeout=WAIT_TIMEOUT, nav_timeout=NAV_TIMEOUT):
    sel = render(selector, row)
    if not sel:
        return False, "Empty selector for click"
    try:
        locator = page.locator(sel)
        locator.first.wait_for(state="visible", timeout=timeout)
    except Exception as e:
        return False, f"no element visible for {sel}: {e}"
    try:
        count = locator.count()
    except Exception:
        count = 0
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
                    last_err = f"click succeeded but navigation did not occur (or timed out): {nav_err}"
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
        ok, err = safe_fill(page, selector, value, row)
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
        ok, err = safe_click(page, selector, row, max_click=max_click, wait_for_nav=wait_for_nav)
        if not ok:
            raise RuntimeError(err)
        print(f"    -> click {render(selector,row)} (max_click={max_click})")
        return

    # replaced emoji with ASCII
    print(f"    [WARN] skipping unknown action type: {a_type}")

# ------------ Reporting structures ------------

@dataclass
class ActionLog:
    idx: int
    type: str
    selector: Optional[str]
    value: Optional[str]
    status: str
    note: str
    before_ss: Optional[str]
    after_ss: Optional[str]

@dataclass
class RunResult:
    row: Dict[str, Any]
    status: str
    note: str
    action_logs: List[ActionLog]
    fail_ss: Optional[str]
    final_ss: Optional[str]
    start_time: str
    end_time: str
    duration_sec: float

# ---------- PDF / Visualization helpers ----------

def _make_bar_chart_png(out_path: Path, passed: int, failed: int):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(4,3))
    labels = ["PASS", "FAIL"]
    values = [passed, failed]
    plt.bar(labels, values)
    plt.title("Test Outcomes")
    plt.ylabel("Count")
    plt.xlabel("Status")
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()

def _rl_image(path: str, width_px: int) -> Optional[RLImage]:
    try:
        img = RLImage(path)
        w, h = img.wrap(0,0)
        scale = width_px / max(w, 1)
        img.drawWidth = w * scale
        img.drawHeight = h * scale
        return img
    except Exception:
        return None

def build_pdf(report_folder: Path, project_title: str, usecase_title: str, results: List[RunResult]):
    pdf_path = report_folder / "report.pdf"
    chart_path = report_folder / "chart_outcomes.png"

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    _make_bar_chart_png(chart_path, passed, failed)

    styles = getSampleStyleSheet()
    story = []

    # Header
    story.append(Paragraph(f"<b>{project_title}</b>", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(usecase_title, styles["Heading2"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Report generated: {_timestamp()}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Outcome summary
    story.append(Paragraph("<b>Summary</b>", styles["Heading3"]))
    tdata = [
        ["Total Runs", str(len(results))],
        ["Passed", str(passed)],
        ["Failed", str(failed)],
    ]
    tbl = Table(tdata, hAlign="LEFT", colWidths=[80*mm, 30*mm])
    tbl.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica")
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))

    chart_img = _rl_image(str(chart_path), 360)
    if chart_img:
        story.append(Paragraph("Outcome Chart", styles["Heading4"]))
        story.append(chart_img)
        story.append(Spacer(1, 12))

    # Per-run table (compact)
    story.append(Paragraph("<b>Run Details</b>", styles["Heading3"]))
    rows = [["#", "Status", "Duration(s)", "Failure Note / Last Note", "First Failure Screenshot"]]
    for i, r in enumerate(results, start=1):
        note = (r.note or "").strip()
        if not note and r.action_logs:
            note = r.action_logs[-1].note or ""
        thumb = ""
        if r.fail_ss:
            thumb = r.fail_ss
        rows.append([str(i), r.status, f"{r.duration_sec:.1f}", note[:200], thumb])

    # Render table with thumbnails (as separate flowables per row)
    # Build table without images first
    col_widths = [10*mm, 18*mm, 25*mm, 85*mm, 40*mm]
    base_tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    base_tbl.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9)
    ]))

    # Replace last column cells with actual image flowables
    # (ReportLab tables can hold flowables directly)
    for ridx in range(1, len(rows)):
        ss_path = rows[ridx][4]
        flow = Paragraph("-", styles["Normal"])
        if isinstance(ss_path, str) and ss_path:
            img = _rl_image(ss_path, PDF_THUMB_WIDTH)
            if img:
                flow = img
        rows[ridx][4] = flow

    # Rebuild table to apply flowables
    base_tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    base_tbl.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,0), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9)
    ]))
    story.append(base_tbl)
    story.append(Spacer(1, 12))

    # Append per-run action logs on separate pages (optional but useful)
    for i, r in enumerate(results, start=1):
        story.append(PageBreak())
        story.append(Paragraph(f"Run #{i} — Status: {r.status}", styles["Heading2"]))
        story.append(Paragraph(f"Start: {r.start_time}  |  End: {r.end_time}  |  Duration: {r.duration_sec:.1f}s", styles["Normal"]))
        story.append(Spacer(1, 6))
        headers = ["#", "Type", "Selector", "Value", "Status", "Note"]
        data = [headers]
        for al in r.action_logs:
            data.append([
                str(al.idx),
                al.type,
                (al.selector or "")[:70],
                (str(al.value or ""))[:40],
                al.status,
                (al.note or "")[:120]
            ])
        atbl = Table(data, colWidths=[8*mm, 18*mm, 55*mm, 35*mm, 16*mm, 68*mm])
        atbl.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8)
        ]))
        story.append(atbl)

        # Show final or fail screenshot big if available
        big_img_path = r.fail_ss or r.final_ss
        if big_img_path:
            story.append(Spacer(1, 8))
            story.append(Paragraph("Screenshot", styles["Heading4"]))
            big_img = _rl_image(big_img_path, 420)  # larger
            if big_img:
                story.append(big_img)

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm)
    doc.build(story)
    return pdf_path

# --------------- Main runner ---------------

def run_all():
    actions = load_actions()
    data_rows = load_data()

    # Create a timestamped run folder
    root_reports = ensure_base(REPORT_DIR)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = root_reports / ts
    run_folder.mkdir(parents=True, exist_ok=True)

    # Persist copies of inputs for traceability
    with open(run_folder / "inputs_snapshot.json", "w", encoding="utf-8") as f:
        json.dump({"actions": actions}, f, indent=2, ensure_ascii=False)
    with open(run_folder / "data_rows_snapshot.json", "w", encoding="utf-8") as f:
        json.dump({"rows": data_rows}, f, indent=2, ensure_ascii=False)

    # Where screenshots live
    screenshots_root = run_folder / "screenshots"
    screenshots_root.mkdir(parents=True, exist_ok=True)

    # Action CSV (flat)
    action_csv_path = run_folder / "actions_log.csv"
    action_json_path = run_folder / "actions_log.jsonl"
    results_txt_path = run_folder / "results.txt"

    results: List[RunResult] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        overall_actions_records = []  # for CSV
        jsonl = open(action_json_path, "w", encoding="utf-8")

        for idx, row in enumerate(data_rows, start=1):
            print(f"\n=== RUN {idx}: {row} ===")
            page = context.new_page()

            run_ss_folder = screenshots_root / f"run_{idx:03d}"
            run_ss_folder.mkdir(parents=True, exist_ok=True)

            start_ts = time.time()
            start_str = _timestamp()
            action_logs: List[ActionLog] = []
            fail_ss = None
            final_ss = None
            status = "PASS"
            note = ""

            try:
                # Decide starting URL
                initial = choose_initial_url(actions)
                if initial:
                    print(f"  navigating to initial URL: {initial}")
                    page.goto(initial, timeout=NAV_TIMEOUT)
                    wait_after_actions(page, 2)

                # iterate actions
                for i, action in enumerate(actions, start=1):
                    # Determine next action pageUrl (for nav wait decision)
                    next_page_url = None
                    for a in actions[i:]:
                        if a.get("pageUrl") or a.get("url"):
                            next_page_url = a.get("pageUrl") or a.get("url")
                            break

                    # pre-wait in case action references a pageUrl we should be at
                    target = action.get("pageUrl") or action.get("url")
                    if target:
                        target_r = render(target, row)
                        if page.url != target_r:
                            try:
                                page.wait_for_url(target_r, timeout=3000)
                            except Exception:
                                if action.get("type") == "goto" or (action.get("type") == "click" and not action.get("selector") and action.get("url")):
                                    print(f"  forcing navigation to {target_r} because action contains explicit url")
                                    page.goto(target_r, timeout=NAV_TIMEOUT)
                                    wait_after_actions(page, 1)

                    before_ss = None
                    after_ss  = None
                    if SCREENSHOT_EVERY_ACTION:
                        before_ss = take_screenshot(page, run_ss_folder, f"before_action{i:02d}")

                    # Do the action
                    try:
                        do_action(page, action, row, next_action_pageUrl=next_page_url)
                        wait_after_actions(page, 0.15)
                        act_status = "OK"
                        act_note = ""
                    except Exception as e:
                        act_status = "FAIL"
                        act_note = str(e)
                        status = "FAIL"
                        note = act_note
                        if SCREENSHOT_ON_FAILURE and not fail_ss:
                            fail_ss = take_screenshot(page, run_ss_folder, f"fail_action{i:02d}")

                    if SCREENSHOT_EVERY_ACTION:
                        after_ss = take_screenshot(page, run_ss_folder, f"after_action{i:02d}")

                    # Log action
                    al = ActionLog(
                        idx=i,
                        type=action.get("type"),
                        selector=render(action.get("selector"), row) if action.get("selector") else None,
                        value=render(action.get("value"), row) if action.get("value") else None,
                        status=act_status,
                        note=act_note,
                        before_ss=before_ss,
                        after_ss=after_ss
                    )
                    action_logs.append(al)
                    # also append to overall action CSV list
                    rec = {
                        "run_index": idx,
                        "row": json.dumps(row, ensure_ascii=False),
                        "action_index": i,
                        "type": al.type,
                        "selector": al.selector or "",
                        "value": al.value or "",
                        "status": al.status,
                        "note": al.note,
                        "before_ss": al.before_ss or "",
                        "after_ss": al.after_ss or "",
                        "timestamp": _timestamp(),
                    }
                    overall_actions_records.append(rec)
                    jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")

                # End-of-run success screenshot
                if SCREENSHOT_ON_SUCCESS_END and status == "PASS":
                    final_ss = take_screenshot(page, run_ss_folder, "final_page")

                # replaced emojis with ASCII
                print(f"  [{'PASS' if status=='PASS' else 'FAIL'}] Run {idx} {status}")

            except Exception as e:
                status = "FAIL"
                note = f"Run-level error: {e}"
                if SCREENSHOT_ON_FAILURE and not fail_ss:
                    fail_ss = take_screenshot(page, run_ss_folder, f"fail_runlevel")

            finally:
                end_ts = time.time()
                end_str = _timestamp()
                dur = max(0.0, end_ts - start_ts)
                results.append(RunResult(
                    row=row,
                    status=status,
                    note=note,
                    action_logs=action_logs,
                    fail_ss=fail_ss,
                    final_ss=final_ss,
                    start_time=start_str,
                    end_time=end_str,
                    duration_sec=dur
                ))
                try:
                    page.close()
                except Exception:
                    pass

        # Close helpers
        jsonl.close()

        # Write run-level summary txt
        with open(results_txt_path, "w", encoding="utf-8") as rf:
            for rr in results:
                rf.write(f"{rr.row} -> {rr.status} {rr.note}\n")
        print(f"\nResults written to {results_txt_path}")

        # Write actions CSV
        with open(action_csv_path, "w", newline="", encoding="utf-8") as cf:
            writer = csv.DictWriter(cf, fieldnames=list(overall_actions_records[0].keys()) if overall_actions_records else [
                "run_index","row","action_index","type","selector","value","status","note","before_ss","after_ss","timestamp"
            ])
            writer.writeheader()
            for rec in overall_actions_records:
                writer.writerow(rec)
        print(f"Action log CSV written to {action_csv_path}")

        # Build PDF
        project_title = "Data-Driven UI Test Report"
        usecase_title = f"Run: {ts} | Actions: {len(actions)} | Dataset rows: {len(data_rows)}"
        pdf_path = build_pdf(run_folder, project_title, usecase_title, results)
        print(f"PDF report created at: {pdf_path}")

        context.close()
        browser.close()

    print(f"\nAll artifacts saved under: {run_folder}")

    # ---- CI-friendly exit code (add this block) ----
    if any(r.status == "FAIL" for r in results):
        import sys
        sys.exit(1)

if __name__ == "__main__":
    run_all()
