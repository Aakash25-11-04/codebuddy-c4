# Changelog

## 2026-11-24
- Deployed app: added the missing `GEMINI_API_KEY` secret on Streamlit Cloud; the pipeline now also retries on 504 errors.
- Switched the app model to `gemini-3.5-flash-lite`, because `gemini-3.5-flash` kept returning 503 (high demand). The evaluation results in `test-data/results/` are still the `gemini-3.5-flash` runs.
- Added a Groq provider to the pipeline and switched the app to `openai/gpt-oss-120b` on the free Groq API, because Gemini (`gemini-3.5-flash` and `-lite`) kept returning 503. Real v4 reviews on T01 and T10 took about 5 s each. Gemini stays available via `provider` in `prompts/config.json`.

## 2026-11-22 (evening)
- Built `codebuddy/prompts.py`, `codebuddy/pipeline.py` (validator, ast syntax pre-check, P1, schema check + retry, P2 Hint Guard), `app.py` (Streamlit) and `eval/run_eval.py`.
- Switched the model to `gemini-3.5-flash`: `gemini-2.5-flash` returns 404 for new API keys, and `gemini-3.8-flash` and `gemini-3.7-flash` returned 503 (high demand).
- Ran the evaluation until the free-tier quota (20 requests per model per day) ran out: v1 and v3 on T01–T09, and v4 on T14. Results are in `test-data/results/` and `docs/metrics.md`.
- Leak check fix: a code block that only shows printed program output no longer counts as a leak (found on v1 T09).
- Deployed the app to Streamlit Community Cloud; filled in the Milestone 2 report and technical report and built the PDFs.

## 2026-11-22
- Added prompt versions v1 (baseline), v2 (role + no-solution rule + JSON in prompt) and v3 (10 rules, 2 few-shot examples, line numbers, ast syntax check, JSON mode, temperature 0.2).
- Added the final two-prompt chain: P1 Reviewer + P2 Hint Guard, with an input validator and a schema check with retry (v4).
- Added 16 test inputs (9 normal, 4 edge, 3 invalid) with automatic checks.
- Added the four workflow, decomposition, input-output and architecture diagrams.
- Added the Milestone 2 report, technical report, reel script and form answer sheet.
