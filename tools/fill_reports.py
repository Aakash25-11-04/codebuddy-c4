"""Fill the [[AUTO: ...]] markers of the report templates from real eval results.

Mechanical values (prompt texts, sample runs, tables) come straight from prompts/ and
test-data/results/. Written analysis (iteration log, limitations, interpretation) comes from
tools/analysis.json, which the team writes after reading the results.
Usage: python tools/fill_reports.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RES = {v: json.loads((ROOT / f"test-data/results/{v}.json").read_text(encoding="utf-8")) for v in ["v1", "v2", "v3", "v4"]}
TESTS = json.loads((ROOT / "test-data/tests.json").read_text(encoding="utf-8"))
A = json.loads((ROOT / "tools/analysis.json").read_text(encoding="utf-8"))
SHOTS = DOCS / "screenshots"


def part(path, which):
    raw = (ROOT / path).read_text(encoding="utf-8")
    _, rest = raw.split("--- SYSTEM PROMPT ---", 1)
    sys_, user = rest.split("--- USER PROMPT TEMPLATE ---", 1)
    return (sys_ if which == "system" else user).strip()


def by_id(v, tid):
    return next(t for t in RES[v]["tests"] if t["id"] == tid)


def metrics_table(compact=False):
    lines = (DOCS / "metrics.md").read_text(encoding="utf-8").split("\n")
    tbl = [l for l in lines[: lines.index("## Per-test pass/fail")] if l.startswith("|")]
    if compact:  # drop latency + guard rewrites columns
        tbl = ["|".join(l.split("|")[:7]) + "|" for l in tbl]
    return "\n".join(tbl)


def short_input(code):
    first = next((l for l in code.split("\n") if l.strip()), "(empty)")
    first = first.replace("|", "\\|")
    return f"`{first[:45]}`" + (" …" if len(code.split("\n")) > 1 or len(first) > 45 else "")


def test_table():
    rows = ["| Test no. | Input (short) | Type | Expected output | Actual output (short) | Pass / Fail |",
            "|---|---|---|---|---|---|"]
    for t in TESTS:
        r = by_id("v4", t["id"])
        inp = f"{t['title']}: " + (short_input(t["code"]) if t["code"] else "(empty)")
        if t["student_question"]:
            inp += f" + question \"{t['student_question'][:40]}…\""
        act = r["check"]["actual_short"].replace("|", "—").replace("\n", " ")
        rows.append(f"| {t['id']} | {inp} | {t['type']} | {t['expected_output']} | {act} | "
                    f"{'Pass' if r['check']['pass'] else '**Fail**'} |")
    return "\n".join(rows)


def guard_test():
    for t in RES["v4"]["tests"]:
        p2 = t["result"].get("p2_json")
        if isinstance(p2, dict) and isinstance(p2.get("guard"), dict) and (p2["guard"].get("leaks_found") or 0) > 0:
            return t["id"]
    return "T10"


def pretty(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) if not isinstance(obj, str) else obj


def screenshot(tid, what):
    p = SHOTS / f"{tid}.png"
    return f"![{what}](screenshots/{tid}.png)" if p.exists() else f"[[SCREENSHOT: {what}]]"


def fill_tech():
    t = (DOCS / "technical_report.md").read_text(encoding="utf-8")
    t = re.sub(r"\[\[AUTO: compact metrics table[^\]]*\]\]", lambda m: metrics_table(compact=True), t)
    t = re.sub(r"\[\[AUTO: 2–3 sentences interpreting[^\]]*\]\]", lambda m: A["interpretation"], t)
    t = re.sub(r"\[\[AUTO: same 2–4 limitations[^\]]*\]\]",
               lambda m: "\n".join(f"- {l['short']}" for l in A["limitations"]), t)
    (DOCS / "technical_report_final.md").write_text(t, encoding="utf-8")
    return t


def fill_m2(tech):
    t = (DOCS / "M2_report_template.md").read_text(encoding="utf-8")
    p1, p2 = "prompts/final/P1_reviewer.txt", "prompts/final/P2_hint_guard.txt"
    gt = guard_test()
    v4 = {x["id"]: x for x in RES["v4"]["tests"]}
    subs = [
        (r"\[\[AUTO: full text of the SYSTEM PROMPT part of prompts/final/P1_reviewer.txt\]\]", part(p1, "system")),
        (r"\[\[AUTO: full text of the USER PROMPT TEMPLATE part of prompts/final/P1_reviewer.txt\]\]", part(p1, "user")),
        (r"\[\[AUTO: T01 student code\]\]", next(x for x in TESTS if x["id"] == "T01")["code"]),
        (r"\[\[AUTO: actual P1 JSON output for T01[^\]]*\]\]", pretty(v4["T01"]["result"]["p1_json"] or v4["T01"]["result"]["raw_p1"])),
        (r"\[\[AUTO: full text of the SYSTEM PROMPT part of prompts/final/P2_hint_guard.txt\]\]", part(p2, "system")),
        (r"\[\[AUTO: full text of the USER PROMPT TEMPLATE part of prompts/final/P2_hint_guard.txt\]\]", part(p2, "user")),
        (r"\[\[AUTO: pick a test where guard[^\]]*\]\]", gt),
        (r"\[\[AUTO: actual P2 JSON output for that test\]\]", pretty(v4[gt]["result"]["p2_json"] or v4[gt]["result"]["raw_p2"])),
        (r"\[\[AUTO: table with columns: Test no\.[^\]]*\]\]", test_table()),
        (r"\[\[AUTO: the metrics table from docs/metrics.md[^\]]*\]\]", metrics_table()),
        (r"\[\[AUTO: check these against the real failures[^\]]*\]\]\n\n(1\..*?)(?=\n<div)", "\n".join(
            f"{i}. **{l['title']}** {l['text']} *Next:* {l['next']}" for i, l in enumerate(A["limitations"], 1)) + "\n"),
        (r"\[\[AUTO: insert the full content of docs/technical_report.md[^\]]*\]\]",
         re.sub(r"^# ", "## ", re.sub(r"^## ", "### ", tech, flags=re.M), count=1, flags=re.M)),
        (r"\[\[SCREENSHOT: Test T01[^\]]*\]\]", screenshot("T01", "Test T01 run")),
        (r"\[\[SCREENSHOT: Test T10[^\]]*\]\]", screenshot("T10", "Test T10 run")),
        (r"\[\[SCREENSHOT: Test T12[^\]]*\]\]", screenshot("T12", "Test T12 run")),
        (r"\[\[SCREENSHOT: GitHub repository[^\]]*\]\]", screenshot("repo", "GitHub repository")),
    ]
    for pat, val in subs:
        t, n = re.subn(pat, lambda m, v=val: v, t, flags=re.DOTALL)
        if n == 0:
            print("WARN no match:", pat[:60])
    # module status + iteration log + version texts
    for key, val in A["m2_cells"].items():
        t = t.replace(key, val, 1)
    for v in ["v1", "v2", "v3"]:
        t = t.replace("[[AUTO: full file]]", (ROOT / f"prompts/{v}/P1_reviewer.txt").read_text(encoding="utf-8").strip(), 1)
    t = re.sub(r"<!--\s*HOW THIS FILE WORKS.*?-->\n*", "", t, flags=re.DOTALL)
    (DOCS / "M2_report.md").write_text(t, encoding="utf-8")
    left = re.findall(r"\[\[[^\]]*\]\]", t)
    print("M2 left markers:", left)


if __name__ == "__main__":
    fill_m2(fill_tech())
