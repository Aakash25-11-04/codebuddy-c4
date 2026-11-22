# Reel script — target 120 seconds (allowed 90–150)

Record the screen of the **deployed app** (real runs only, no mock-ups). One teammate does the voice-over; captions are optional. Upload to Drive ("Anyone with the link can view") or YouTube (Unlisted), then write the exact length in seconds in the form (Q14) and on the cover page.

| Time | Show on screen | Voice-over (read slowly) |
|---|---|---|
| 0:00–0:12 **Problem** | Title card or the app home page | "First-year students get stuck on small Python bugs. Most chatbots just hand them the fixed code, so they learn nothing. CodeBuddy is a code reviewer that gives hints, not answers." |
| 0:12–0:30 **Before (v1)** | Select **v1** in the version dropdown, paste test T10 (factorial with `result = 0`) and the question "Just give me the corrected code". Run it. Highlight the corrected code in the output. | "This is our first prompt, a one-line 'review this code'. Even for a beginner who asks for help, it rewrites the whole program, which is exactly what we don't want." |
| 0:30–0:52 **After (v4)** | Switch to **v4 (final)**, run the same input. Show the refusal summary, the issue card on line 2, then click "Show hint". | "Our final version uses a teaching-assistant role, ten rules, two examples and JSON output, plus a second prompt, the Hint Guard, that rewrites any hint giving the fix away. Same input: it refuses politely and points to line 2 with a question." |
| 0:52–1:35 **Working demo** | Run 2–3 more tests live on v4: T01 (off-by-one, reveal hint), T12 (comment saying 'ignore your rules', which is ignored), T15 (cricket question, rejected as not Python). Briefly show the issue types and the praise / next step. | "Here's an off-by-one loop: it flags line 3 and asks the student to trace the loop by hand. This program hides an instruction in a comment, and CodeBuddy ignores it. And if you paste something that isn't Python, it asks for a program instead of answering." |
| 1:35–1:55 **Progress and next steps** | The metrics table (docs/metrics.md) or a slide with the numbers | "On the 9 tests we could run before our free API quota ran out, passes went from 0 out of 9 with v1 to 9 out of 9 with v3, and solution leaks dropped from 9 out of 9 to 0. For Milestone 3 we will [the 'next' items from the limitations, e.g. add an LLM judge for leaks and better multi-line issue handling]." |
| 1:55–2:00 | Team name + repository link | "Team [name]. Thank you." |

Numbers above are from `docs/metrics.md` (v1 and v3 on T01–T09). Every on-screen review must be a real run, so record the reel once the API quota allows live reviews (paid tier, or after the daily reset).
