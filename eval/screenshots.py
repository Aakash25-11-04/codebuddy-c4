"""Take screenshots of real v4 runs in the local Streamlit app.

Start the app first: streamlit run app.py --server.headless true --server.port 8501
Then: python eval/screenshots.py T01 T10 T12
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
URL = "http://localhost:8501"


def shoot(page, test_id: str):
    page.goto(URL, wait_until="networkidle")
    page.get_by_text("Your review will appear here").wait_for(timeout=60000)
    sel = page.locator("[data-testid='stSelectbox']").first
    sel.click()
    page.get_by_role("option", name=test_id, exact=False).first.click()
    page.wait_for_timeout(1500)
    page.get_by_text("v4 final").click()
    page.get_by_role("button", name="Review").click()
    page.get_by_text("API call(s)").wait_for(timeout=240000)
    hint = page.get_by_role("button", name="Show hint")
    if hint.count():
        hint.first.click()
        page.wait_for_timeout(2500)
    # Streamlit scrolls inside its own container, so size the viewport to the content.
    h = page.evaluate("Math.max(document.querySelector('[data-testid=\"stMain\"]')?.scrollHeight || 0, document.body.scrollHeight)")
    page.set_viewport_size({"width": 1400, "height": min(max(int(h) + 40, 900), 4000)})
    page.wait_for_timeout(1000)
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{test_id}.png"), full_page=True)
    print("saved", test_id)


if __name__ == "__main__":
    ids = sys.argv[1:] or ["T01", "T10", "T12"]
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        for t in ids:
            shoot(page, t)
            page.set_viewport_size({"width": 1400, "height": 1000})
        b.close()
