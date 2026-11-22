"""CodeBuddy Streamlit app: hints, not answers."""
import json
from pathlib import Path

import streamlit as st

from codebuddy.pipeline import guard_rewrites, review

st.set_page_config(page_title="CodeBuddy", page_icon="🧩", layout="wide")

ROOT = Path(__file__).resolve().parent
TESTS = json.loads((ROOT / "test-data" / "tests.json").read_text(encoding="utf-8"))
EXAMPLES = {f"{t['id']} · {t['title']}": t for t in TESTS}
VERSIONS = {"v1 baseline": "v1", "v2": "v2", "v3": "v3", "v4 final": "v4"}

STATUS_BADGE = {
    "ok": ("🟠", "Issues found"),
    "no_issues": ("🟢", "No issues found"),
    "invalid_input": ("⚪", "Not a Python program"),
}
TYPE_ICON = {"syntax": "⛔", "bug": "🐞", "logic": "🧠", "style": "🎨"}

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1200px;}
      .cb-badge {display:inline-block; padding:.2rem .7rem; border-radius:999px;
                 background:#eef2ff; color:#3730a3; font-weight:600; font-size:.9rem;}
      .cb-meta {font-weight:600; color:#334155;}
      .cb-note {color:#64748b; font-size:.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("CodeBuddy — hints, not answers")
st.caption("Paste a short Python program. CodeBuddy points out bugs, logic errors and style issues "
           "as hints, so you can fix the code yourself.")


def _load_example():
    choice = st.session_state.example
    if choice in EXAMPLES:
        t = EXAMPLES[choice]
        st.session_state.code = t["code"]
        st.session_state.question = t["student_question"]
    else:
        st.session_state.code = ""
        st.session_state.question = ""
    st.session_state.pop("result", None)


left, right = st.columns([1, 1], gap="large")

with left:
    st.selectbox("Load an example", ["(blank)"] + list(EXAMPLES), key="example", on_change=_load_example)
    st.text_area("Your Python code", key="code", height=320,
                 placeholder="def sum_to_n(n):\n    ...")
    st.text_input("Your question (optional)", key="question",
                  placeholder="e.g. Why does this print 10 instead of 15?")
    st.radio("Prompt version", list(VERSIONS), index=3, key="version", horizontal=True)
    if st.button("Review", type="primary", use_container_width=True):
        with st.spinner("CodeBuddy is reading your code..."):
            try:
                st.session_state.result = review(st.session_state.code, st.session_state.question,
                                                 VERSIONS[st.session_state.version])
                st.session_state.shown_hints = set()
            except Exception as exc:  # noqa: BLE001
                st.session_state.result = None
                st.error(f"The review failed: {exc}")


def render_json(res: dict, data: dict):
    icon, label = STATUS_BADGE.get(data.get("status"), ("🔵", str(data.get("status", "Review"))))
    st.markdown(f"<span class='cb-badge'>{icon} {label}</span>", unsafe_allow_html=True)
    if data.get("summary"):
        st.markdown(f"**{data['summary']}**")
    n_rewrites = guard_rewrites(res)
    if n_rewrites:
        st.markdown(f"<span class='cb-note'>🛡️ Hint Guard rewrote {n_rewrites} field(s)</span>",
                    unsafe_allow_html=True)

    shown = st.session_state.setdefault("shown_hints", set())
    for i, issue in enumerate(data.get("issues") or []):
        if not isinstance(issue, dict):
            continue
        with st.container(border=True):
            t = issue.get("type", "?")
            st.markdown(f"<span class='cb-meta'>{TYPE_ICON.get(t, '•')} Line {issue.get('line', '?')} · "
                        f"{t} · {issue.get('severity', '?')}</span>", unsafe_allow_html=True)
            if issue.get("what"):
                st.markdown(f"**What:** {issue['what']}")
            if issue.get("why"):
                st.markdown(f"**Why:** {issue['why']}")
            if issue.get("hint"):
                if i in shown:
                    st.info(f"💡 {issue['hint']}")
                elif st.button("Show hint", key=f"hint_{i}"):
                    shown.add(i)
                    st.rerun()

    if data.get("praise"):
        st.success(f"👏 {data['praise']}")
    if data.get("next_step"):
        st.markdown(f"**Next step:** {data['next_step']}")


with right:
    res = st.session_state.get("result")
    if res:
        final = res.get("final")
        if isinstance(final, dict):
            render_json(res, final)
        else:
            st.markdown(final or "_(empty response)_")
        st.caption(f"Version {res['version']} · {len(res.get('calls', []))} API call(s) · {res.get('latency_s', 0)} s")
    else:
        st.markdown("<span class='cb-note'>Your review will appear here.</span>", unsafe_allow_html=True)

res = st.session_state.get("result")
if res:
    with st.expander("Raw model output (P1 / P2)"):
        st.markdown("**P1 Reviewer**")
        st.code(res.get("raw_p1") or "(no call: input rejected by the validator)", language="json")
        if res.get("raw_p2") is not None:
            st.markdown("**P2 Hint Guard**")
            st.code(res["raw_p2"], language="json")

st.divider()
st.caption("CodeBuddy is a learning aid: it can be wrong, so always test your code yourself. "
           "Do not paste personal data, passwords or API keys. Your code is never run.")
