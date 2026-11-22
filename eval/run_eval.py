"""Run every test in test-data/tests.json through review() and score it.

Usage: python eval/run_eval.py --versions v1 v2 v3 v4 [--only T01 T02] [--metrics-only]
Writes test-data/results/{version}.json and docs/metrics.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from codebuddy import pipeline  # noqa: E402
from codebuddy.pipeline import guard_rewrites, parse_json, review, strip_fence  # noqa: E402

TESTS = json.loads((ROOT / "test-data" / "tests.json").read_text(encoding="utf-8"))
RESULTS_DIR = ROOT / "test-data" / "results"
METRICS = ROOT / "docs" / "metrics.md"
ALL_VERSIONS = ["v1", "v2", "v3", "v4"]

REFUSE_KEYWORDS = ["won't", "will not", "can't give", "cannot give", "yourself", "not give"]
BUG_TYPES = {"syntax", "bug", "logic"}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower().replace("’", "'"))


def low(s: str) -> str:
    return s.lower().replace("’", "'")


# ------------------------------------------------------------------ code-block detection
_PY_STMT = re.compile(
    r"""^(
        (def|class|for|while|if|elif|return|import|from|try|with|print|lambda|global)\b.*
      | (else|try|finally)\s*:.*
      | except\b.*:
      | [A-Za-z_][\w\.]*(\[[^\]]*\])?\s*([+\-*/%]|//)?=(?!=)\s*\S.*
      | [A-Za-z_][\w\.]*\(.*\)\s*
    )$""",
    re.VERBOSE,
)


def _clean_code_line(line: str) -> str:
    line = re.sub(r"^\s*\d+\s*\|\s?", "", line)      # numbered "3 | ..." form
    line = re.sub(r"\s+#.*$", "", line)               # trailing comment
    return norm(line)


def _clean_code_line_keep(line: str) -> str:
    return re.sub(r"^\s*\d+\s*\|\s?", "", line).strip()


def code_blocks(text: str, raw: bool) -> list[list[str]]:
    blocks = [b.split("\n") for b in re.findall(r"```[a-zA-Z]*\n?(.*?)```", text, re.DOTALL)]
    if raw:
        outside = re.sub(r"```.*?```", "\n", text, flags=re.DOTALL)
        run: list[str] = []
        for line in outside.split("\n") + [""]:
            s = line.strip()
            if s and _PY_STMT.match(s) and not s.endswith(".") and len(s.split()) < 14:
                run.append(line)
            else:
                if len(run) >= 2:
                    blocks.append(run)
                run = []
    return blocks


def leaked_block(text: str, raw: bool, student_code: str) -> str | None:
    student = {_clean_code_line(l) for l in student_code.split("\n")}
    student.discard("")
    for block in code_blocks(text, raw):
        # A block counts as code only if at least one line looks like a Python statement
        # (a block of printed program output such as "1 False" is not a solution leak).
        if not any(_PY_STMT.match(_clean_code_line_keep(l)) for l in block):
            continue
        for line in block:
            c = _clean_code_line(line)
            if c and c not in student and c not in {"...", "#..."} and not c.startswith("#"):
                return line.strip()[:60]
    return None


# ------------------------------------------------------------------ scoring
def as_review(obj):
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj[0]
    return obj if isinstance(obj, dict) else None


def review_text(d: dict) -> str:
    parts = [d.get("summary"), d.get("next_step"), d.get("praise")]
    for it in d.get("issues") or []:
        if isinstance(it, dict):
            parts += [it.get("what"), it.get("why"), it.get("hint")]
    return "\n".join(p for p in parts if isinstance(p, str))


def score(test: dict, version: str, res: dict) -> dict:
    ch = test["checks"]
    final = res.get("final")
    if isinstance(final, (dict, list)):
        final_text = json.dumps(final, ensure_ascii=False)
    else:
        final_text = final or ""

    data = None
    json_valid = None
    if version != "v1":
        parsed = parse_json(final_text)
        json_valid = parsed is not None
        data = as_review(parsed)

    if data is not None:
        text, raw = review_text(data), False
    else:
        text, raw = final_text, True
        m = re.match(r"^\s*```json\s*\n(.*)\n?```\s*$", text, re.DOTALL)  # v2 wrapper fence is not a leak
        if m:
            text = m.group(1)
    ntext, ltext = norm(text), low(text)

    reasons = []
    leak_snip = next((s for s in ch["forbidden_snippets"] if norm(s) in ntext), None)
    leak_line = leaked_block(text, raw, test["code"])
    leak = bool(leak_snip or leak_line)
    if leak_snip:
        reasons.append(f"LEAK: {leak_snip}")
    elif leak_line:
        reasons.append(f"LEAK code block: {leak_line}")

    kw_hit = any(low(k) in ltext for k in ch["detect_keywords"])
    issues = [i for i in (data.get("issues") or []) if isinstance(i, dict)] if data else None

    checks: dict = {}
    if ch["line_groups"]:
        if issues is not None:
            lines = set()
            for i in issues:
                try:
                    lines.add(int(i.get("line")))
                except (TypeError, ValueError):
                    pass
            checks["line_found"] = all(any(l in lines for l in g) for g in ch["line_groups"])
        else:
            checks["line_found"] = kw_hit
    if ch["expected_status"]:
        exp = ch["expected_status"]
        if data is not None and "status" in data:
            checks["status_ok"] = data["status"] == exp
        elif exp in ("invalid_input", "no_issues"):
            checks["status_ok"] = kw_hit
    if ch["expect_refused"]:
        if data is not None and "refused_solution_request" in data:
            checks["refused_ok"] = data["refused_solution_request"] is True
        else:
            checks["refused_ok"] = any(k in ltext for k in REFUSE_KEYWORDS)
    if ch["expect_style_only"]:
        if issues is not None:
            checks["style_only_ok"] = bool(issues) and all(i.get("type") == "style" for i in issues)
        else:
            checks["style_only_ok"] = kw_hit
    if ch["expect_no_bugs"]:
        if data is not None:
            checks["no_bugs_ok"] = data.get("status") == "no_issues" or not any(
                i.get("type") in BUG_TYPES for i in (issues or []))
        else:
            checks["no_bugs_ok"] = kw_hit

    for k, v in checks.items():
        if not v:
            reasons.append(f"{k} failed")
    if version != "v1" and not json_valid:
        reasons.append("JSON invalid")
    passed = all(checks.values()) and not leak and (json_valid if version != "v1" else True)

    # short description of the actual output
    if data is not None:
        s = f"status={data.get('status')}"
        if issues:
            i0 = issues[0]
            what = " ".join(str(i0.get("what", "")).split()[:12])
            s += f"; L{i0.get('line')} {i0.get('type')}: {what}"
        elif data.get("summary"):
            s += "; " + " ".join(str(data["summary"]).split()[:12])
    else:
        s = " ".join(final_text.split()[:15])
    if reasons:
        s += " | " + "; ".join(reasons)

    return {"json_valid": json_valid, "leak": leak, **checks, "pass": bool(passed),
            "actual_short": s, "guard_rewrites": guard_rewrites(res)}


# ------------------------------------------------------------------ metrics
def write_metrics() -> None:
    rows, matrix = [], {}
    for v in ALL_VERSIONS:
        p = RESULTS_DIR / f"{v}.json"
        if not p.exists():
            rows.append([v, f"0/{len(TESTS)}", "not run"] + ["—"] * 6)
            continue
        items = json.loads(p.read_text(encoding="utf-8"))["tests"]
        matrix[v] = {it["id"]: it["check"]["pass"] for it in items}
        n = len(items)

        def frac(key):
            vals = [it["check"][key] for it in items if it["check"].get(key) is not None]
            return f"{sum(bool(x) for x in vals)}/{len(vals)}" if vals else "N/A"

        lat = [it["result"]["latency_s"] for it in items if it["result"].get("calls")]
        rows.append([
            v,
            f"{n}/{len(TESTS)}",
            f"{sum(it['check']['pass'] for it in items)}/{n}",
            frac("json_valid"),
            frac("line_found"),
            f"{sum(it['check']['leak'] for it in items)}/{n}",
            frac("status_ok"),
            f"{sum(lat) / len(lat):.1f}" if lat else "N/A",
            str(sum(it["check"]["guard_rewrites"] for it in items)) if v == "v4" else "N/A",
        ])
    out = ["# Evaluation metrics", "",
           f"Generated by `eval/run_eval.py` on {time.strftime('%Y-%m-%d %H:%M')} from `test-data/results/*.json` "
           f"(model: `{pipeline.load_config()['model']}`).", "",
           "| Version | Tests run | Pass | JSON valid | Expected line found | Solution leaked | Correct status | Avg latency (s) | Guard rewrites |",
           "|---|---|---|---|---|---|---|---|---|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    out += ["", "Fractions are over the tests that were run. Avg latency counts only tests that made API calls "
            "(v4 T14 is rejected by the validator with no call).",
            "", "## Per-test pass/fail", "",
            "| Test | " + " | ".join(matrix) + " |", "|---|" + "---|" * len(matrix)]
    for t in TESTS:
        cells = ["— not run" if t["id"] not in matrix[v] else ("✅ pass" if matrix[v][t["id"]] else "❌ fail")
                 for v in matrix]
        out.append(f"| {t['id']} {t['title']} | " + " | ".join(cells) + " |")
    METRICS.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", default=ALL_VERSIONS)
    ap.add_argument("--only", nargs="*", help="test ids to (re)run; others are kept from the saved file")
    ap.add_argument("--gap", type=float, default=6.0, help="seconds between API calls")
    ap.add_argument("--metrics-only", action="store_true")
    ap.add_argument("--rescore", action="store_true", help="re-apply the checks to saved outputs, no API calls")
    args = ap.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pipeline.CALL_GAP_S = args.gap
    if args.rescore:
        tests = {t["id"]: t for t in TESTS}
        for v in args.versions:
            path = RESULTS_DIR / f"{v}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for it in data["tests"]:
                it["check"] = score(tests[it["id"]], v, it["result"])
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    elif not args.metrics_only:
        model = pipeline.load_config()["model"]
        for v in args.versions:
            path = RESULTS_DIR / f"{v}.json"
            saved = {}
            if args.only and path.exists():
                saved = {it["id"]: it for it in json.loads(path.read_text(encoding="utf-8"))["tests"]}
            out = []
            for t in TESTS:
                if args.only and t["id"] not in args.only:
                    if t["id"] in saved:
                        out.append(saved[t["id"]])
                    continue
                res = review(t["code"], t["student_question"], v)
                chk = score(t, v, res)
                print(f"{v} {t['id']}: {'PASS' if chk['pass'] else 'FAIL'}  {chk['actual_short']}", flush=True)
                out.append({"id": t["id"], "title": t["title"], "type": t["type"],
                            "expected_output": t["expected_output"], "result": res, "check": chk})
                path.write_text(json.dumps({"version": v, "model": model,
                                            "run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "tests": out},
                                           indent=2, ensure_ascii=False), encoding="utf-8")
    write_metrics()
    print((METRICS).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
