# CodeBuddy: Hint-First Code Review Assistant for Beginner Python Programmers

SCSE4041 Prompt Engineering Mini Project. Problem **C4**: code review assistant for beginner programmers.

CodeBuddy reviews a first-year student's Python program and points out bugs, logic errors and style issues with **hints, never the full solution**. It uses a two-prompt chain on Gemini (the deployed app uses `gemini-3.5-flash-lite`): **P1 Reviewer** finds and explains the issues, then **P2 Hint Guard** rewrites anything that gives the fix away.

- **Prototype:** https://codebuddy-c4-mnmykb7xf2wbtypxhez3dn.streamlit.app/
- **Reel:** [FILL]
- **Repository:** https://github.com/Aakash25-11-04/codebuddy-c4
- **Team:** Decentralized Vision (PE-B25-10): AAKASH RAUNIAR (S24CSEU0036, team leader), TANNU SHARMA (S24CSEU1420)

## Status (22 Nov 2026)
The Gemini free tier allows 20 requests per model per day, and this ran out during evaluation. Real results so far: v1 and v3 on tests T01–T09 (v1 passed 0/9 and leaked the fix in 9/9; v3 passed 9/9 with 0 leaks), and v4 on T14. See [docs/metrics.md](docs/metrics.md). The evaluation used `gemini-3.5-flash`, because `gemini-2.5-flash` returns 404 for new API keys. Then the deployed app switched from `gemini-3.5-flash` to `gemini-3.5-flash-lite` on 24 Nov 2026, because `gemini-3.5-flash` kept returning 503 (high demand).

## How to use the prototype
Open the prototype link, paste Python code, add a question if you have one, keep **v4 (final)** selected and press **Review**. Use the version selector to compare earlier prompt versions.

## Run locally
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then put your own GEMINI_API_KEY in it
streamlit run app.py
python eval/run_eval.py --versions v1 v2 v3 v4                # re-runs the 16 tests
```

## Folders
| Folder | Contents |
|---|---|
| `prompts/v1, v2, v3` | Older P1 versions |
| `prompts/final` | Final prompts: `P1_reviewer.txt`, `P2_hint_guard.txt` |
| `prompts/config.json` | Model and settings for each version |
| `app.py`, `codebuddy/` | Streamlit app and pipeline |
| `eval/` | Evaluation script |
| `test-data/` | `tests.json`, readable inputs, saved outputs in `results/` |
| `docs/` | Diagrams, metrics, Milestone 2 PDF, technical report, reel script |
| `CHANGELOG.md` | Dated changes since Milestone 1 |
