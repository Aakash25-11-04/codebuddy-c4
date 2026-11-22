"""Markdown -> HTML (images embedded) -> A4 PDF with Playwright.

Usage: python tools/build_pdf.py docs/M2_report.md docs/M2_T00_CodeBuddy.pdf
"""
import base64
import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 11pt; line-height: 1.45; color: #1e293b; }
h1 { font-size: 18pt; color: #312e81; border-bottom: 2px solid #c7d2fe; padding-bottom: 4px; margin-top: 0; }
h2 { font-size: 14pt; color: #3730a3; margin-top: 18px; }
h3 { font-size: 12pt; color: #3730a3; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.5pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e1; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #eef2ff; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px;
      white-space: pre-wrap; word-wrap: break-word; font-size: 8.5pt; line-height: 1.35; }
code { font-family: Consolas, "Courier New", monospace; font-size: 9pt; }
img { max-width: 100%; display: block; margin: 6px auto; border: 1px solid #e2e8f0; }
p em { color: #475569; }
"""


def embed_images(html: str, base: Path) -> str:
    def repl(m):
        src = m.group(1)
        if src.startswith(("http", "data:")):
            return m.group(0)
        p = (base / src).resolve()
        if not p.exists():
            return m.group(0)
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return f'src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"'
    return re.sub(r'src="([^"]+)"', repl, html)


def build(md_path: Path, pdf_path: Path):
    text = md_path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "md_in_html"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>{md_path.stem}</title><style>{CSS}</style></head><body>{body}</body></html>"
    html = embed_images(html, md_path.parent)
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    print(pdf_path, f"{pdf_path.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2]))
