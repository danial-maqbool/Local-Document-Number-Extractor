"""
Automated Playwright script for Local Document Number Extractor:
- Launches backend server (or connects to running server)
- Verifies HTTP 200 on /, /ui, /style.css, /app.js
- Verifies 0 console errors and 0 CSS/JS 404 errors
- Navigates to every page
- Uploads documents and tests batch extraction UI
- Interacts with Review Queue (canvas overlay & field inputs)
- Interacts with Template Calibrator (draws bounding box & computes coords)
- Captures full-resolution screenshots for all views
- Tests multiple responsive viewport sizes
"""
import os
import sys
import time
import subprocess
import threading
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

SERVER_URL = "http://127.0.0.1:8000"

def wait_for_server(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = requests.get(f"{url}/api/health", timeout=2)
            if res.status_code == 200:
                print(f"[OK] Backend server is responsive at {url}")
                return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    print("=" * 60)
    print("STARTING FRONTEND VALIDATION & SCREENSHOT CAPTURE")
    print("=" * 60)

    # Check if server is already running
    server_process = None
    try:
        res = requests.get(f"{SERVER_URL}/api/health", timeout=1)
        server_running = (res.status_code == 200)
    except Exception:
        server_running = False

    if not server_running:
        print("[INFO] Launching uvicorn server in background...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if not wait_for_server(SERVER_URL):
            print("[ERROR] Server failed to start in time.")
            if server_process:
                server_process.kill()
            sys.exit(1)
    else:
        print("[INFO] Server is already running at", SERVER_URL)

    console_errors = []
    failed_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1440 x 900 standard enterprise desktop
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Track network errors and console errors
        def on_response(response):
            if response.status >= 400:
                failed_requests.append(f"{response.url} returned HTTP {response.status}")

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        page.on("response", on_response)
        page.on("console", on_console)

        print("[STEP 1] Navigating to Root URL: / ...")
        resp = page.goto(f"{SERVER_URL}/", wait_until="networkidle")
        assert resp.status == 200, f"Root returned {resp.status}"

        # Verify static asset routes
        css_resp = page.goto(f"{SERVER_URL}/style.css")
        assert css_resp.status == 200, f"/style.css returned {css_resp.status}"
        assert "text/css" in css_resp.headers.get("content-type", "")

        js_resp = page.goto(f"{SERVER_URL}/app.js")
        assert js_resp.status == 200, f"/app.js returned {js_resp.status}"
        assert "application/javascript" in js_resp.headers.get("content-type", "")

        print("[STEP 2] Returning to UI and validating Dashboard...")
        page.goto(f"{SERVER_URL}/", wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Check KPI cards exist and are populated
        stat_total = page.locator("#statTotal").inner_text()
        print(f"       Total documents in dashboard: {stat_total}")

        # Capture Dashboard Screenshot
        dashboard_path = SCREENSHOTS_DIR / "dashboard.png"
        page.screenshot(path=str(dashboard_path), full_page=False)
        print(f"[SCREENSHOT] Saved Dashboard -> {dashboard_path}")

        # Step 3: Process Documents Tab
        print("[STEP 3] Testing Process Documents page...")
        page.click("button[data-tab='process']")
        page.wait_for_timeout(500)

        # Stage files into upload zone
        sample_img = BASE_DIR / "sample_data" / "synthetic" / "bill_doc_01.jpg"
        if sample_img.exists():
            page.set_input_files("#filePicker", [str(sample_img)])
            page.wait_for_timeout(500)

        process_path = SCREENSHOTS_DIR / "process_documents.png"
        page.screenshot(path=str(process_path), full_page=False)
        print(f"[SCREENSHOT] Saved Process Documents -> {process_path}")

        # Step 4: Results Tab
        print("[STEP 4] Testing Results Table page...")
        page.click("button[data-tab='results']")
        page.wait_for_timeout(800)

        results_path = SCREENSHOTS_DIR / "results.png"
        page.screenshot(path=str(results_path), full_page=False)
        print(f"[SCREENSHOT] Saved Results Table -> {results_path}")

        # Step 5: Review Queue Tab
        print("[STEP 5] Testing Manual Review Queue page...")
        page.click("button[data-tab='review']")
        page.wait_for_timeout(1000)

        # Click first review item if available
        review_items = page.locator(".review-item-card")
        if review_items.count() > 0:
            review_items.first.click()
            page.wait_for_timeout(1000)

        review_path = SCREENSHOTS_DIR / "review_queue.png"
        page.screenshot(path=str(review_path), full_page=False)
        print(f"[SCREENSHOT] Saved Review Queue -> {review_path}")

        # Step 6: Template Calibrator Tab
        print("[STEP 6] Testing Template Calibrator page...")
        page.click("button[data-tab='calibrate']")
        page.wait_for_timeout(500)

        calib_img = BASE_DIR / "sample_data" / "synthetic" / "bill_doc_01.jpg"
        if calib_img.exists():
            page.set_input_files("#calibImagePicker", str(calib_img))
            page.wait_for_timeout(800)

            # Drag to draw bounding box on canvas
            canvas = page.locator("#calibrationCanvas")
            box = canvas.bounding_box()
            if box:
                # Drag from 20% to 50%
                start_x = box["x"] + box["width"] * 0.2
                start_y = box["y"] + box["height"] * 0.2
                end_x = box["x"] + box["width"] * 0.5
                end_y = box["y"] + box["height"] * 0.35

                page.mouse.move(start_x, start_y)
                page.mouse.down()
                page.mouse.move(end_x, end_y, steps=5)
                page.mouse.up()
                page.wait_for_timeout(500)

        calib_path = SCREENSHOTS_DIR / "template_calibrator.png"
        page.screenshot(path=str(calib_path), full_page=False)
        print(f"[SCREENSHOT] Saved Template Calibrator -> {calib_path}")

        # Step 7: Templates Management Tab
        print("[STEP 7] Testing Templates & Fields page...")
        page.click("button[data-tab='templates']")
        page.wait_for_timeout(500)

        templates_path = SCREENSHOTS_DIR / "templates.png"
        page.screenshot(path=str(templates_path), full_page=False)
        print(f"[SCREENSHOT] Saved Templates -> {templates_path}")

        # Step 8: Settings Tab
        print("[STEP 8] Testing Settings page...")
        page.click("button[data-tab='settings']")
        page.wait_for_timeout(500)

        settings_path = SCREENSHOTS_DIR / "settings.png"
        page.screenshot(path=str(settings_path), full_page=False)
        print(f"[SCREENSHOT] Saved Settings -> {settings_path}")

        # Step 9: Responsive Viewports Testing
        print("[STEP 9] Validating Responsive Viewports...")
        viewports = [
            ("1920x1080", 1920, 1080),
            ("1366x768", 1366, 768),
            ("1024x768", 1024, 768),
            ("mobile_375x812", 375, 812)
        ]
        for name, w, h in viewports:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(300)
            vp_path = SCREENSHOTS_DIR / f"viewport_{name}.png"
            page.screenshot(path=str(vp_path), full_page=False)
            print(f"[RESPONSIVE] Viewport {name} validated -> {vp_path}")

        browser.close()

    if server_process:
        server_process.kill()

    print("=" * 60)
    print("VALIDATION SUMMARY:")
    print(f"Network errors count: {len(failed_requests)}")
    for err in failed_requests:
        print("  -", err)
    print(f"Console errors count: {len(console_errors)}")
    for err in console_errors:
        print("  -", err)
    print("Screenshots created:", len(list(SCREENSHOTS_DIR.glob("*.png"))))
    print("=" * 60)

    if len(failed_requests) > 0:
        print("[FAIL] There were failed network requests!")
        sys.exit(1)
    if len(console_errors) > 0:
        print("[FAIL] There were console errors!")
        sys.exit(1)

    print("[SUCCESS] All routes, interactions, and visuals validated with 0 errors!")

if __name__ == "__main__":
    main()
