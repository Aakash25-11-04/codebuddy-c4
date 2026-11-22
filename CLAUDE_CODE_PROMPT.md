You are helping our team finish Milestone 2 of our Prompt Engineering mini project. The submission deadline is TONIGHT, 22 Nov 2026, 11:59 PM IST, so work fast and in the priority order below. This folder already contains the prompts, test set, diagram sources and report templates. Your job is the code, the real test runs, the diagrams, the screenshots, filling in the report and building the PDFs.

## Project
CodeBuddy (problem C4) is a code review assistant for first-year Python students. It returns bugs, logic errors and style issues as HINTS, never the full solution. Stack: Python, Streamlit, Google Gemini API through the `google-genai` SDK, deployed on Streamlit Community Cloud, public GitHub repo.

Read these first: `prompts/config.json`, every file in `prompts/`, `test-data/tests.json`, `docs/M2_report_template.md`, `docs/technical_report.md` and `README.md`.

## Hard rules
- NEVER change the text of any prompt file. They are the documented versions. If a version fails tests, that is a real result: report it honestly.
- NEVER invent or edit results. Every number and every "actual output" in the report must come from `test-data/results/*.json` produced by real API calls.
- NEVER write the API key into any tracked file. Read it from the `GEMINI_API_KEY` env var locally, and from `st.secrets["GEMINI_API_KEY"]` (falling back to the env var) in the app. Before every push, run a search for the key value and for `AIza` and confirm there are no hits in tracked files (other than this instruction line in CLAUDE_CODE_PROMPT.md).
- Never execute student code. Only `ast.parse` it.

## Step 0 — Ask me first (one message, then wait)
1. My Gemini API key (free from https://aistudio.google.com/apikey). I'll set it as an env var for this session.
2. Team details for the `[FILL]` markers: Team ID, team name (as in Milestone 1), batch, faculty name, each member's name + enrollment no. (S24CSEU....) + role + Milestone 2 tasks + contribution %, and 2–3 lines on what our Milestone 1 submission proposed (for "What changed since Milestone 1").
3. Whether `gh` (GitHub CLI) is logged in. If not, I'll create an empty public repo and give you the URL.
Don't block on 2: if I haven't answered, keep the `[FILL]` markers and carry on.

## Step 1 — Code (priority 1)
Create:
- `codebuddy/prompts.py` loads a prompt file. The parts are: header comment lines starting with `#` (ignore them), the text after `--- SYSTEM PROMPT ---` (may be empty, meaning no system instruction) and the text after `--- USER PROMPT TEMPLATE ---`. Fill variables with `str.replace("{name}", value)` for the known variable names ONLY. Do not use `.format()`, because the prompts contain JSON braces.
- `codebuddy/pipeline.py` has `review(code, student_question, version) -> dict` driven by `prompts/config.json`:
  - validator (only if `validator` is true): stripped code empty, or more than `max_lines` lines, or more than `max_chars` characters → return a JSON-shaped result with `status: "invalid_input"` and a friendly summary, with no API call.
  - `syntax_check` (if enabled): `ast.parse` → "OK" or "SyntaxError on line N: msg" (IndentationError is a SyntaxError subclass).
  - `numbered_code` (if enabled): `"{n} | {line}"`. Use `{code}` for v1/v2.
  - `student_question` → "(none)" if empty.
  - P1 call: model from config, `system_instruction` if non-empty, `temperature` if not null, `response_mime_type="application/json"` if `json_mode`.
  - If `schema_retry`: validate the JSON keys/types against the schema in the P1 prompt; if invalid, retry P1 once.
  - If `guard`: P2 call with `numbered_code` + `review_json` (json.dumps of P1's output), temperature `guard_temperature`, JSON mode. Keep both P1 and P2 outputs.
  - Return `{version, raw_p1, p1_json (or None), raw_p2, p2_json, final (the JSON or raw text shown to the user), latency_s, calls}`.
  - Retry on 429/503 with exponential backoff (max 5 tries).
  - If the model in config returns 404 / not found, list the available models, pick the current Gemini Flash model, update `prompts/config.json` and every place the docs name the model (prompt headers excluded; mention it in the report instead), and tell me.
- `app.py` (Streamlit, wide layout, title "CodeBuddy — hints, not answers"):
  - a "Load an example" selectbox with T01–T16 from tests.json, plus "(blank)";
  - a code text area, an optional question box, and a version radio (v1 baseline, v2, v3, v4 final; default v4);
  - a Review button and a spinner.
  - Render JSON results as: a status badge and summary; one card per issue showing `Line N · type · severity`, what and why, with the hint hidden behind a per-issue "Show hint" button (use session_state); then praise and next step. If the guard rewrote fields, show a small note "Hint Guard rewrote N field(s)".
  - For non-JSON output (v1, or broken JSON), show the raw text in a markdown block.
  - Put an expander "Raw model output (P1 / P2)" at the bottom, and a footer saying it is a learning aid and not to paste personal data.
  - Make it look clean but keep it simple.
- Update `requirements.txt` if needed. `.streamlit/config.toml` is optional.

## Step 2 — Evaluation (priority 1)
`eval/run_eval.py --versions v1 v2 v3 v4` runs every test in `test-data/tests.json` through `review()`, sleeping about 6 s between API calls (free-tier rate limit). It saves `test-data/results/{version}.json` (per test: the full review() output plus the check results) and writes `docs/metrics.md`.

Checks per test. Normalise text as lowercase with ALL whitespace removed.
- `json_valid`: the final output parses with json.loads after stripping one surrounding markdown ``` / ```json fence. N/A for v1.
- `text` to scan: if the JSON parsed, join all string values (summary, next_step, praise, and every issue's what/why/hint); otherwise the whole raw text.
- `leak`: any `forbidden_snippets` entry appears in normalised `text`, OR `text` contains a code block (``` fence, or for raw text 2+ consecutive lines that look like Python statements) whose lines are NOT all just copies of lines in the student's original code. The JSON wrapper fence of v2 is not a leak.
- `line_found` (tests with `line_groups`): with JSON issues, each group needs at least one issue whose `line` is in the group. Without JSON, any `detect_keywords` entry is in the lowercased text.
- `status_ok`: if `expected_status` is set and the JSON has a `status` key, they must match. If the JSON has no status key or there is no JSON, then for expected `invalid_input`/`no_issues` use the `detect_keywords` fallback; for expected `ok`, skip the check.
- `refused_ok` (if `expect_refused`): the JSON `refused_solution_request` must be true. Fallback when the key is missing: the text contains one of ["won't", "will not", "can't give", "cannot give", "yourself", "not give"].
- `style_only_ok` (if `expect_style_only`): the JSON issues are non-empty and every issue's type is "style". Fallback: keywords.
- `no_bugs_ok` (if `expect_no_bugs`): the JSON status is "no_issues" or no issue has a type in {syntax, bug, logic}. Fallback: keywords.
- `pass` = every applicable check is true AND not leak AND (json_valid for v2, v3, v4).
- Store a short `actual_short` for each test: status + first issue "Lnum type: what" (about 15 words) or the first 15 words of the raw text, plus the reason on failure (e.g. "LEAK: range(1,n+1)").

`docs/metrics.md` contains a table with one row per version: Pass x/16 · JSON valid x/15 (or x/16) · Expected line found x/N · Solution leaked x/16 · Correct status x/N · Avg latency s · Guard rewrites total (v4). Below that, a per-test pass/fail matrix (tests × versions).

Run it for all 4 versions now. Show me the metrics table. Do not tune prompts to make tests pass.

## Step 3 — Git + deploy (priority 2)
- `git init` (if needed) and make several meaningful commits, in this order: prompts and test data; pipeline; app; eval; results and metrics; docs. Push to a PUBLIC GitHub repo, called `codebuddy-c4` unless I give a URL. Confirm `.streamlit/secrets.toml` and `.env` are git-ignored.
- Then give me exact click-by-click steps for Streamlit Community Cloud: share.streamlit.io → Create app → our repo / main / app.py → Advanced settings → Secrets: `GEMINI_API_KEY = "..."` → Deploy. Ask me for the resulting URL. Remind me to open it in an incognito window.

## Step 4 — Diagrams and screenshots (priority 2)
- Render `docs/diagrams/*.mmd` to PNG (white background, width 1600) next to the sources. Try `npx -y @mermaid-js/mermaid-cli` first. If that fails, use Python + Playwright with the mermaid JS from a CDN. Last resort: the mermaid.ink image API. If a diagram fails to parse, fix only its syntax, not its meaning.
- Screenshots of REAL runs: start the app locally, then use Playwright (pip install playwright; python -m playwright install chromium) to load examples T01, T10 and T12 with v4. Click Review, wait for the result, click "Show hint" on the first issue, and take a full-page screenshot to `docs/screenshots/T01.png`, `T10.png` and `T12.png`. If Playwright can't be installed, tell me exactly which 3 screenshots to take by hand.
- The repository screenshot (Section 5) is taken by me after the push. Leave its placeholder, or take it with Playwright from the public GitHub page if the repo is public.

## Step 5 — Fill the reports and build the PDFs (priority 3)
- Copy `docs/M2_report_template.md` to `docs/M2_report.md` and `docs/technical_report.md` to `docs/technical_report_final.md`. Replace every `[[AUTO: ...]]` with real content as its instruction says, using the results files and metrics:
  - full prompt texts;
  - the T01 sample run;
  - the P2 sample run (a test where `guard.leaks_found > 0` if one exists);
  - the module status table (Working only if it actually worked in the runs);
  - the iteration-log result and "why" cells, written from REAL observed failures with numbers;
  - the 16-row test table;
  - the metrics table;
  - the limitations, checked against the real failures;
  - Section 6 (the technical report content).
  Replace `[[SCREENSHOT: ...]]` with the images. Replace `[FILL]` with my answers from Step 0 and the links when I give them; leave any I haven't answered. Then update README.md, CHANGELOG.md (dated entries), `docs/form_answers.md` (Q10 = 2, Q17 = 16, Q18 = 4, unless something changed) and the reel script numbers.
- Build the PDFs: markdown → HTML (python `markdown` with the tables and fenced_code extensions, images embedded as base64, a clean A4 print CSS, 11pt body, code blocks wrapped with `white-space: pre-wrap`, page breaks kept) → PDF with Playwright `page.pdf(format="A4", print_background=True)`. Outputs:
  - `docs/M2_<TeamID>_CodeBuddy.pdf` (no spaces in the name)
  - `docs/<TeamName>_TechnicalReport.pdf`
  Keep each under 10 MB (compress the PNGs if needed). If Playwright is unavailable, write the HTML and tell me to open it in Chrome and Save as PDF.
- Commit and push again.

## Step 6 — Final check (report to me as a checklist)
- grep the final .md and HTML for `[FILL` and `[[` and list what's left for me.
- Confirm the counts match across the PDF, metrics and form_answers.md: prompts = 2, test inputs = 16, prompt versions = 4. Also confirm the module names in form Q20 match the status table exactly.
- Confirm no API key appears in the repo (search the git history too).
- List what I must still do by hand: deploy, test the links in incognito, the repo screenshot, record the reel with `docs/reel_script.md` (90–150 s, real runs), upload the reel, and submit the form (team leader only, once).

Keep your messages short. Ask me only when you are blocked.
