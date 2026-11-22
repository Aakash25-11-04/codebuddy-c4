"""Fill the [[AUTO: ...]] markers of the report templates from real eval results.

Mechanical values (prompt texts, sample runs, tables) come straight from prompts/ and
test-data/results/. Written analysis comes from tools/analysis.json, written after reading
the results. Versions/tests that were not run are shown as "not run", never invented.
Usage: python tools/fill_reports.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RES = {}
for v in ["v1", "v2", "v3", "v4"]:
    p = ROOT / f"test-data/results/{v}.json"
    if p.exists():
        RES[v] = {t["id"]: t for t in json.loads(p.read_text(encoding="utf-8"))["tests"]}
TESTS = json.loads((ROOT / "test-data/tests.json").read_text(encoding="utf-8"))
A = json.loads((ROOT / "tools/analysis.json").read_text(encoding="utf-8"))
SHOTS = DOCS / "screenshots"


def part(path, which):
    raw = (ROOT / path).read_text(encoding="utf-8")
    _, rest = raw.split("--- SYSTEM PROMPT ---", 1)
    sys_, user = rest.split("--- USER PROMPT TEMPLATE ---", 1)
    return (sys_ if which == "system" else user).strip()


def metrics_table(compact=False):
    lines = (DOCS / "metrics.md").read_text(encoding="utf-8").split("\n")
    tbl = [l for l in lines[: lines.index("## Per-test pass/fail")] if l.startswith("|")]
    if compact:  # version | tests run | pass | JSON | line | leaks | status
        tbl = ["|".join(l.split("|")[:8]) + "|" for l in tbl]
    return "\n".join(tbl)


def per_test_matrix():
    lines = (DOCS / "metrics.md").read_text(encoding="utf-8").split("\n")
    return "\n".join(l for l in lines[lines.index("## Per-test pass/fail"):] if l.startswith("|"))


def short_input(code):
    first = next((l for l in code.split("\n") if l.strip()), "")
    first = first.replace("|", "\\|")
    return f"`{first[:40]}`" + (" …" if len(code.split("\n")) > 1 or len(first) > 40 else "")


def test_table():
    rows = ["| Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass / Fail |",
            "|---|---|---|---|---|---|"]
    for t in TESTS:
        inp = f"{t['title']}: " + (short_input(t["code"]) if t["code"] else "(empty)")
        if t["student_question"]:
            inp += f" + question \"{t['student_question'][:35]}…\""
        if t["id"] in RES.get("v4", {}):
            r, src = RES["v4"][t["id"]], "v4"
        elif t["id"] in RES.get("v3", {}):
            r, src = RES["v3"][t["id"]], "v3"
        else:
            r, src = None, None
        if r:
            act = r["check"]["actual_short"].replace("|", "—").replace("\n", " ")
            act = f"*({src} run)* {act}"
            pf = "Pass" if r["check"]["pass"] else "**Fail**"
        else:
            act, pf = "Not run: free-tier API quota reached", "Not run"
        rows.append(f"| {t['id']} | {inp} | {t['type']} | {t['expected_output']} | {act} | {pf} |")
    return "\n".join(rows)


def pretty(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) if not isinstance(obj, str) else obj


def img(name, alt):
    return f"![{alt}](screenshots/{name}.png)" if (SHOTS / f"{name}.png").exists() else f"[[SCREENSHOT: {alt}]]"


def fill_tech():
    t = (DOCS / "technical_report.md").read_text(encoding="utf-8")
    t = re.sub(r"\[\[AUTO: compact metrics table[^\]]*\]\]", lambda m: metrics_table(compact=True), t)
    t = re.sub(r"\[\[AUTO: 2–3 sentences interpreting[^\]]*\]\]", lambda m: A["interpretation"], t)
    t = re.sub(r"\[\[AUTO: same 2–4 limitations[^\]]*\]\]",
               lambda m: "\n".join(f"- **{l['title']}** {l['short']}" for l in A["limitations"]), t)
    (DOCS / "technical_report_final.md").write_text(t, encoding="utf-8")
    return t


def fill_m2(tech):
    t = (DOCS / "M2_report_template.md").read_text(encoding="utf-8")
    p1, p2 = "prompts/final/P1_reviewer.txt", "prompts/final/P2_hint_guard.txt"
    t01 = RES["v3"]["T01"]["result"]
    p2_block = re.search(r"\*\*Sample run \(real input and actual output, test \[\[AUTO: pick.*?```json\n\[\[AUTO: actual P2 JSON output for that test\]\]\n```", t, re.DOTALL).group(0)
    t = t.replace(p2_block, A["p2_sample_note"])
    t = t.replace("**Sample run (real input and actual output, test T01)**",
                  "**Sample run (real input and actual output, test T01).** Taken from the v3 run, which uses exactly the same P1 text and settings as v4 (temperature 0.2, JSON mode, numbered code, syntax check).")
    shots = (img("T14", "Test T14 run (v4)") + "\n*Figure 5 — Test T14 (empty input) run in the app with v4: the input validator rejects it with 0 API calls.*\n\n"
             + A["screenshot_note"])
    t = re.sub(r"\[\[SCREENSHOT: Test T01.*?\*Figure 7 — Test T12 run in the deployed app\.\*", lambda m: shots, t, flags=re.DOTALL)
    subs = [
        (r"\[\[AUTO: full text of the SYSTEM PROMPT part of prompts/final/P1_reviewer.txt\]\]", part(p1, "system")),
        (r"\[\[AUTO: full text of the USER PROMPT TEMPLATE part of prompts/final/P1_reviewer.txt\]\]", part(p1, "user")),
        (r"\[\[AUTO: T01 student code\]\]", next(x for x in TESTS if x["id"] == "T01")["code"]),
        (r"\[\[AUTO: actual P1 JSON output for T01[^\]]*\]\]", pretty(t01["p1_json"] or t01["raw_p1"])),
        (r"\[\[AUTO: full text of the SYSTEM PROMPT part of prompts/final/P2_hint_guard.txt\]\]", part(p2, "system")),
        (r"\[\[AUTO: full text of the USER PROMPT TEMPLATE part of prompts/final/P2_hint_guard.txt\]\]", part(p2, "user")),
        (r"\[\[AUTO: table with columns: Test no\.[^\]]*\]\]", A["test_table_note"] + "\n\n" + test_table()),
        (r"\[\[AUTO: the metrics table from docs/metrics.md[^\]]*\]\]",
         metrics_table() + "\n\n" + A["metrics_note"] + "\n\n**Per-test results**\n\n" + per_test_matrix()),
        (r"\[\[AUTO: check these against the real failures[^\]]*\]\]\n\n(1\..*?)(?=\n<div)", "\n".join(
            f"{i}. **{l['title']}** {l['text']} *Next:* {l['next']}" for i, l in enumerate(A["limitations"], 1)) + "\n"),
        (r"\[\[AUTO: insert the full content of docs/technical_report.md[^\]]*\]\]",
         re.sub(r"^# ", "## ", re.sub(r"^## ", "### ", tech, flags=re.M), count=1, flags=re.M)),
        (r"\[\[SCREENSHOT: GitHub repository[^\]]*\]\]", img("repo", "GitHub repository")),
    ]
    for pat, val in subs:
        t, n = re.subn(pat, lambda m, v=val: v, t, flags=re.DOTALL)
        if n == 0:
            print("WARN no match:", pat[:60])
    for key, val in A["m2_cells"]:
        if key not in t:
            print("WARN cell not found:", key[:60])
        t = t.replace(key, val, 1)
    for v in ["v1", "v2", "v3"]:
        t = t.replace("[[AUTO: full file]]", (ROOT / f"prompts/{v}/P1_reviewer.txt").read_text(encoding="utf-8").strip(), 1)
    t = re.sub(r"<!--\s*HOW THIS FILE WORKS.*?-->\n*", "", t, flags=re.DOTALL)
    (DOCS / "M2_report.md").write_text(t, encoding="utf-8")
    print("M2 left markers:", re.findall(r"\[\[[^\]]*\]\]|\[FILL[^\]]*\]", t))


if __name__ == "__main__":
    fill_m2(fill_tech())
