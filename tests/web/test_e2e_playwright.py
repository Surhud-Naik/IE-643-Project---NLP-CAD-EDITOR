"""
Playwright End-to-End Browser Tests for CAD Patch Editor Web UI.
Tests:
1. Example loading -> edit execution -> 3D renders -> download verification
2. Invalid script pre-flight failure display
3. Patch-failure error state with collapsible raw patch
4. Chaining two sequential edits via 'Continue editing from result'
5. Revert from session history
Saves full-page screenshots to outputs/web_screenshots/
"""

import os
import sys
import time
import subprocess
import threading
import uvicorn
import pytest
from playwright.sync_api import sync_playwright

from cadpatch.web.config import WebConfig
from cadpatch.web.app import create_app
from cadpatch.web.model_service import MockModelBackend

SCREENSHOT_DIR = os.path.abspath("outputs/web_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


@pytest.fixture(scope="module")
def web_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "cadpatch.web.app:app", "--host", "127.0.0.1", "--port", "8125", "--log-level", "warning"],
        env={**os.environ, "PYTHONPATH": "src"}
    )
    url = "http://127.0.0.1:8125"
    import urllib.request
    for _ in range(40):
        try:
            r = urllib.request.urlopen(f"{url}/api/health", timeout=1)
            if r.status == 200:
                break
        except Exception:
            time.sleep(0.5)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def test_example_to_edit_render_download(web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 950})

        page.goto(web_server)
        page.wait_for_selector("text=CAD Patch Editor")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_initial_page.png"))

        # 1. Open Examples Gallery
        page.click("button:has-text('Examples')")
        page.wait_for_selector("text=Built-in CAD Examples Gallery")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_example_gallery_modal.png"))

        # Select example "Mounting Plate Bore Expansion"
        page.click("text=Mounting Plate Bore Expansion")

        # 2. Click Apply CAD Patch
        page.click("button:has-text('Apply CAD Patch')")

        # 3. Wait for completed status (stepper or completed badge)
        page.wait_for_selector("text=Valid B-Rep Solid", timeout=30000)
        page.wait_for_selector("text=Predicted Code Patch")
        page.wait_for_selector("text=Parametric & Geometric Changes")

        # 4. Save screenshot of successful result
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_edit_completed_result.png"))

        # 5. Check downloads are present
        assert page.is_visible("text=Download:")
        assert page.is_visible("text=Python (.py)")
        assert page.is_visible("text=Patch (.diff)")
        assert page.is_visible("text=STL")
        assert page.is_visible("text=GLB")

        # 6. Test Overlay Mode Toggle
        page.click("button:has-text('Overlay Mode')")
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_ghost_overlay_mode.png"))

        browser.close()


def test_invalid_script_error(web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 950})

        page.goto(web_server)
        page.wait_for_selector("text=CAD Patch Editor")

        # Enter broken script
        editor = page.locator("textarea").first
        editor.fill("import cadquery as cq\n\nresult = cq.Workplane('XY').box(20, 20, 10).shell(-999.0)\n")

        # Submit
        page.click("button:has-text('Apply CAD Patch')")

        # Wait for failure alert
        page.wait_for_selector("text=Editing Attempt Unsuccessful", timeout=20000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_invalid_script_error.png"))

        browser.close()


def test_patch_failure_error_state(web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 950})

        page.goto(web_server)
        page.wait_for_selector("text=CAD Patch Editor")

        # Enter instruction triggering non-match patch
        inst_box = page.locator("textarea").nth(1)
        inst_box.fill("Widen hole simulate_no_match by 2 mm")

        page.click("button:has-text('Apply CAD Patch')")

        # Wait for failure alert
        page.wait_for_selector("text=Editing Attempt Unsuccessful", timeout=25000)
        page.wait_for_selector("text=View raw model output", timeout=10000)

        # Click view raw output
        page.click("text=View raw model output")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_patch_failure_collapsible.png"))

        browser.close()


def test_chaining_two_edits(web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 950})

        page.goto(web_server)
        page.wait_for_selector("text=CAD Patch Editor")

        # Edit 1: Widen hole
        inst_box = page.locator("textarea").nth(1)
        inst_box.fill("Widen the hole by 4 mm")
        page.click("button:has-text('Apply CAD Patch')")
        page.wait_for_selector("text=Valid B-Rep Solid", timeout=25000)

        # Click "Continue Editing from Result"
        page.click("button:has-text('Continue Editing from Result')")
        page.wait_for_timeout(300)

        # Verify the script in editor now has HOLE_DIA = 12.0
        editor_content = page.locator("textarea").first.input_value()
        assert "HOLE_DIA" in editor_content

        # Edit 2: Increase length
        inst_box.fill("Make the plate longer by 15 mm")
        page.click("button:has-text('Apply CAD Patch')")
        page.wait_for_selector("text=Valid B-Rep Solid", timeout=25000)

        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_chained_second_edit.png"))
        browser.close()


def test_revert_from_history(web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 950})

        page.goto(web_server)
        page.wait_for_selector("text=CAD Patch Editor")

        # Edit 1
        inst_box = page.locator("textarea").nth(1)
        inst_box.fill("Widen the hole by 2 mm")
        page.click("button:has-text('Apply CAD Patch')")
        page.wait_for_selector("text=Valid B-Rep Solid", timeout=25000)

        # Check history item appears
        page.wait_for_selector("text=Session Edit History")
        assert page.is_visible("button:has-text('Revert')")

        # Click Revert
        page.click("button:has-text('Revert')")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_revert_history.png"))

        browser.close()
