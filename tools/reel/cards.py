"""Render the still cards for the reel (1280x720 PNG) with Playwright."""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[2] / "build" / "reel"

BASE = """<html><head><meta charset='utf-8'><style>
body{margin:0;width:1280px;height:720px;display:flex;flex-direction:column;justify-content:center;
 align-items:center;font-family:'Segoe UI',Arial;background:linear-gradient(135deg,#1e1b4b,#3730a3);color:#fff;text-align:center}
h1{font-size:64px;margin:0 0 12px} h2{font-size:30px;font-weight:400;margin:6px;color:#c7d2fe}
.small{font-size:22px;color:#e0e7ff;margin-top:28px}
table{border-collapse:collapse;font-size:26px;margin-top:20px;background:rgba(255,255,255,.06)}
td,th{border:1px solid rgba(255,255,255,.3);padding:10px 26px} th{color:#c7d2fe}
.good{color:#86efac;font-weight:700} .bad{color:#fca5a5;font-weight:700}
</style></head><body>{body}</body></html>"""

CARDS = {
    "card_title": """<h1>CodeBuddy</h1><h2>Hints, not answers: a code reviewer for first-year Python students</h2>
<div class='small'>Team Decentralized Vision (PE-B25-10) · SCSE4041 Prompt Engineering · Problem C4</div>""",
    "card_metrics": """<h2 style='font-size:38px;color:#fff'>Real test results (same inputs, T01–T09)</h2>
<table><tr><th>Prompt version</th><th>Tests passed</th><th>Solution leaked</th><th>Valid JSON</th></tr>
<tr><td>v1 baseline</td><td class='bad'>0 / 9</td><td class='bad'>9 / 9</td><td>n/a (free text)</td></tr>
<tr><td>v3 (rules + examples + JSON)</td><td class='good'>9 / 9</td><td class='good'>0 / 9</td><td class='good'>9 / 9</td></tr></table>
<div class='small'>Evaluation model: gemini-3.5-flash · 16-input test suite, run stopped at 9 tests by the free API quota<br>Live app: gpt-oss-120b on Groq · details in docs/metrics.md</div>""",
    "card_end": """<h1>Thank you</h1><h2>Team Decentralized Vision · PE-B25-10</h2>
<div class='small'>github.com/Aakash25-11-04/codebuddy-c4<br>codebuddy-c4-mnmykb7xf2wbtypxhez3dn.streamlit.app</div>""",
}


def cut_card(name, seconds):
    return f"<h2 style='font-size:40px;color:#fff'>⏳ Waiting for the model…</h2><div class='small'>{seconds:.0f} s of waiting cut from this recording</div>"


def render(extra=None):
    OUT.mkdir(parents=True, exist_ok=True)
    cards = dict(CARDS, **(extra or {}))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 720})
        for name, body in cards.items():
            pg.set_content(BASE.replace("{body}", body))
            pg.screenshot(path=str(OUT / f"{name}.png"))
        b.close()


if __name__ == "__main__":
    render()
