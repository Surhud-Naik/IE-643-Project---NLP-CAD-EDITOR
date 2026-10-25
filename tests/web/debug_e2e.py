import subprocess
import sys
import time
import os
import urllib.request
from playwright.sync_api import sync_playwright

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "cadpatch.web.app:app", "--host", "127.0.0.1", "--port", "8125", "--log-level", "info"],
    env={**os.environ, "PYTHONPATH": "src"}
)

try:
    print("Waiting for server...")
    for _ in range(40):
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8125/api/health", timeout=1)
            if r.status == 200:
                print("Server is healthy!")
                break
        except Exception:
            time.sleep(0.5)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 950})
        page.on("console", lambda msg: print(f"[CONSOLE {msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"[PAGEERROR] {err}"))

        print("Navigating to page...")
        page.goto("http://127.0.0.1:8125")
        page.wait_for_selector("text=CAD Patch Editor")
        print("Page opened.")

        page.click("button:has-text('Examples')")
        page.wait_for_selector("text=Built-in CAD Examples Gallery")
        page.click("text=Mounting Plate Bore Expansion")
        time.sleep(0.5)

        print("Clicking Apply CAD Patch...")
        page.click("button:has-text('Apply CAD Patch')")

        for i in range(20):
            time.sleep(1)
            txt = page.locator("body").inner_text()
            if "Valid B-Rep Solid" in txt:
                print(f"SUCCESS! Valid B-Rep Solid found at {i+1}s")
                break
            if "Editing Attempt Unsuccessful" in txt:
                print(f"FAILED at {i+1}s")
                break
            print(f"Waiting... ({i+1}s)")

        page.screenshot(path="outputs/web_screenshots/debug_test_run.png")
        browser.close()
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
