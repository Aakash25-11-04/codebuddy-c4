"""Record real runs of the deployed app, one video per scene.

Usage: python tools/reel/record.py [scene ...]
Writes build/reel/<scene>.webm, <scene>.json (event timestamps + text shown on screen).
"""
import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("REEL_URL", "http://localhost:8501/")
OUT = Path(__file__).resolve().parents[2] / "build" / "reel"
SIZE = {"width": 1280, "height": 720}

SCENES = {
    "before_v1": ("T10", "v1 baseline", "BEFORE · v1 baseline prompt · test T10"),
    "after_v4": ("T10", "v4 final", "AFTER · v4 final (P1 Reviewer + P2 Hint Guard) · same input"),
    "t01": ("T01", "v4 final", "v4 · T01 off-by-one loop"),
    "t12": ("T12", "v4 final", "v4 · T12 instruction hidden in a comment"),
    "t15": ("T15", "v4 final", "v4 · T15 not Python code"),
}

CAPTION_JS = """(text) => {
  let d = document.getElementById('reel-cap');
  if (!d) { d = document.createElement('div'); d.id = 'reel-cap';
    d.style.cssText = 'position:fixed;left:0;right:0;top:0;z-index:999999;background:rgba(49,46,129,.92);color:#fff;font:600 18px Segoe UI,Arial;padding:8px 18px;';
    document.body.appendChild(d); }
  d.textContent = text; }"""


def app_frame(page):
    for _ in range(90):
        btn = page.get_by_role("button", name="Yes, get this app back up!")
        if btn.count():
            btn.click()
        for f in page.frames:
            if f.get_by_text("Your review will appear here").count():
                return f
        page.wait_for_timeout(1000)
    raise RuntimeError("app did not load")


def record(name):
    test_id, version, caption = SCENES[name]
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / f"_tmp_{name}"
    shutil.rmtree(tmp, ignore_errors=True)
    ev = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport=SIZE, record_video_dir=str(tmp), record_video_size=SIZE)
        t0 = time.time()
        page = ctx.new_page()
        mark = lambda k: ev.__setitem__(k, round(time.time() - t0, 2))
        page.goto(URL, wait_until="domcontentloaded", timeout=90000)
        f = app_frame(page)
        page.evaluate(CAPTION_JS, caption)
        page.wait_for_timeout(800)
        mark("loaded")
        f.locator("[data-testid='stSelectbox']").first.click()
        page.wait_for_timeout(400)
        page.keyboard.type(test_id, delay=80)
        page.wait_for_timeout(400)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        f.get_by_text(version, exact=True).first.click()
        page.wait_for_timeout(1200)
        f.get_by_role("button", name="Review").click()
        mark("review_clicked")
        done = f.get_by_text("API call(s)").or_(f.get_by_text("The review failed"))
        done.first.wait_for(timeout=400000)
        mark("result")
        if f.get_by_text("The review failed").count():
            ev["error"] = f.locator("[data-testid='stMain']").inner_text()[-600:]
            print("ERROR on screen:", ev["error"][-300:], flush=True)
        main = f.locator("[data-testid='stMain']")
        center = "e => e.scrollIntoView({behavior: 'smooth', block: 'center'})"
        page.wait_for_timeout(1500)
        badge = f.locator(".cb-badge")
        if badge.count():
            badge.first.evaluate(center)
            page.wait_for_timeout(3500)
        ev["screen_text"] = main.inner_text()
        hint = f.get_by_role("button", name="Show hint")
        if hint.count():
            hint.first.evaluate(center)
            page.wait_for_timeout(1800)
            hint.first.click()
            mark("hint_clicked")
            page.wait_for_timeout(1500)
            tip = f.locator("[data-testid='stAlert']")
            if tip.count():
                tip.first.evaluate(center)
            page.wait_for_timeout(4000)
            ev["screen_text"] = main.inner_text()
        code = f.locator("pre").filter(has_text="result = 1")
        if not code.count():
            code = f.locator("pre")
        if version.startswith("v1") and code.count():
            code.first.evaluate(center)
            page.wait_for_timeout(5000)
        page.wait_for_timeout(1500)
        mark("end")
        page.wait_for_timeout(1500)
        vid = page.video.path()
        ctx.close()
        b.close()
    shutil.move(vid, OUT / f"{name}.webm")
    shutil.rmtree(tmp, ignore_errors=True)
    (OUT / f"{name}.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False), encoding="utf-8")
    print(name, {k: v for k, v in ev.items() if k != "screen_text"}, flush=True)


if __name__ == "__main__":
    for s in sys.argv[1:] or list(SCENES):
        record(s)
