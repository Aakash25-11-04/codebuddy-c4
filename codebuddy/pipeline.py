"""CodeBuddy review pipeline, driven by prompts/config.json.

v4 flow: validator -> syntax pre-check -> P1 Reviewer -> schema check (+1 retry) -> P2 Hint Guard.
Student code is never executed: it is only parsed with ast.parse.
"""
from __future__ import annotations

import ast
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from .prompts import ROOT, load_prompt

CONFIG_PATH = ROOT / "prompts" / "config.json"

# Minimum gap between two API calls (seconds). The eval script raises this to
# respect the free-tier rate limit; the app leaves it at 0.
CALL_GAP_S = 0.0
_last_call_end = 0.0



# ---------------------------------------------------------------- config / key
def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


KEY_NAMES = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}
_clients: dict = {}


def provider() -> str:
    return load_config().get("provider", "gemini")


def get_api_key(prov: str | None = None) -> str | None:
    name = KEY_NAMES[prov or provider()]
    try:
        import streamlit as st  # only present when running the app

        key = st.secrets.get(name)  # type: ignore[attr-defined]
        if key:
            return str(key)
    except Exception:
        pass
    return os.environ.get(name)


def _get_client(prov: str):
    if prov not in _clients:
        key = get_api_key(prov)
        if not key:
            raise RuntimeError(f"{KEY_NAMES[prov]} is not set (env var or Streamlit secrets).")
        if prov == "groq":
            from groq import Groq

            # SDK retries off because call_model() does its own backoff.
            _clients[prov] = Groq(api_key=key, timeout=120.0, max_retries=0)
        else:
            from google import genai
            from google.genai import types

            # 120 s timeout per request; SDK retries off because call_model() does its own backoff.
            _clients[prov] = genai.Client(api_key=key, http_options=types.HttpOptions(
                timeout=120_000, retry_options=types.HttpRetryOptions(attempts=1)))
    return _clients[prov]


def _generate(prov: str, model: str, system: str, user: str, temperature, json_mode: bool) -> str:
    if prov == "groq":
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = _get_client(prov).chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
    from google.genai import types

    cfg_kwargs: dict[str, Any] = {}
    if system:
        cfg_kwargs["system_instruction"] = system
    if temperature is not None:
        cfg_kwargs["temperature"] = temperature
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"
    gen_cfg = types.GenerateContentConfig(**cfg_kwargs) if cfg_kwargs else None
    resp = _get_client(prov).models.generate_content(model=model, contents=user, config=gen_cfg)
    return resp.text or ""


# ---------------------------------------------------------------- code steps
def syntax_check(code: str) -> str:
    try:
        ast.parse(code)
        return "OK"
    except SyntaxError as e:  # IndentationError is a subclass
        return f"SyntaxError on line {e.lineno}: {e.msg}"


def number_code(code: str) -> str:
    return "\n".join(f"{n} | {line}" for n, line in enumerate(code.split("\n"), start=1))


def validate_input(code: str, cfg: dict) -> str | None:
    """Return a friendly message if the input is invalid, else None."""
    limits = cfg.get("validator", {})
    max_lines, max_chars = limits.get("max_lines", 150), limits.get("max_chars", 6000)
    stripped = code.strip()
    if not stripped:
        return "There is no code to review yet. Please paste your Python program in the box and press Review."
    if len(code.split("\n")) > max_lines:
        return f"Your code is longer than {max_lines} lines. Please paste one smaller part (one function or one exercise) at a time."
    if len(code) > max_chars:
        return f"Your code is longer than {max_chars} characters. Please paste one smaller part at a time."
    return None


# ---------------------------------------------------------------- JSON helpers
_FENCE_RE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


def strip_fence(text: str) -> str:
    """Strip one surrounding ``` / ```json fence, if present."""
    m = _FENCE_RE.match(text or "")
    return m.group(1) if m else (text or "")


def parse_json(text: str) -> Any | None:
    try:
        return json.loads(strip_fence(text).strip())
    except Exception:
        return None


_STATUS = {"ok", "no_issues", "invalid_input"}
_TYPES = {"syntax", "bug", "logic", "style"}
_SEVERITY = {"high", "medium", "low"}


def schema_errors(obj: Any) -> list[str]:
    """Check a P1 review against the schema written in the P1 prompt."""
    if not isinstance(obj, dict):
        return ["top level is not a JSON object"]
    errs: list[str] = []
    expect = {"status": str, "summary": str, "issues": list,
              "refused_solution_request": bool, "praise": str, "next_step": str}
    for key, typ in expect.items():
        if key not in obj:
            errs.append(f"missing key {key}")
        elif not isinstance(obj[key], typ):
            errs.append(f"{key} is not {typ.__name__}")
    if isinstance(obj.get("status"), str) and obj["status"] not in _STATUS:
        errs.append(f"bad status {obj['status']!r}")
    for i, issue in enumerate(obj.get("issues") or []):
        if not isinstance(issue, dict):
            errs.append(f"issues[{i}] is not an object")
            continue
        if not isinstance(issue.get("line"), int) or isinstance(issue.get("line"), bool):
            errs.append(f"issues[{i}].line is not an integer")
        if issue.get("type") not in _TYPES:
            errs.append(f"issues[{i}].type invalid")
        if issue.get("severity") not in _SEVERITY:
            errs.append(f"issues[{i}].severity invalid")
        for k in ("what", "why", "hint"):
            if not isinstance(issue.get(k), str):
                errs.append(f"issues[{i}].{k} is not a string")
    return errs


# ---------------------------------------------------------------- model call
def _is_retryable(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (429, 500, 503, 504):
        return True
    msg = str(exc)
    return any(s in msg for s in ("429", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED", "overloaded", "timed out"))


def _is_not_found(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    return code == 404 or "NOT_FOUND" in str(exc) or "not found" in str(exc).lower()


class ModelNotFound(RuntimeError):
    pass


def call_model(model: str, system: str, user: str, temperature: float | None,
               json_mode: bool, calls: list) -> str:
    """One model call (provider from config) with exponential backoff on 429/5xx (max 5 tries)."""
    global _last_call_end
    prov = provider()

    delay = 4.0
    for attempt in range(1, 6):
        wait = CALL_GAP_S - (time.time() - _last_call_end)
        if wait > 0:
            time.sleep(wait)
        t0 = time.time()
        try:
            text = _generate(prov, model, system, user, temperature, json_mode)
            dt = time.time() - t0
            _last_call_end = time.time()
            calls.append({"provider": prov, "model": model, "attempt": attempt, "seconds": round(dt, 2), "ok": True})
            return text
        except Exception as exc:  # noqa: BLE001
            dt = time.time() - t0
            _last_call_end = time.time()
            calls.append({"model": model, "attempt": attempt, "seconds": round(dt, 2), "ok": False,
                          "error": str(exc)[:300]})
            if _is_not_found(exc) and not _is_retryable(exc):
                raise ModelNotFound(str(exc)) from exc
            if attempt == 5 or not _is_retryable(exc):
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- main entry
def _invalid_result(version: str, summary: str) -> dict:
    final = {"status": "invalid_input", "summary": summary, "issues": [],
             "refused_solution_request": False, "praise": "", "next_step": "Paste a Python program and press Review."}
    return {"version": version, "raw_p1": None, "p1_json": None, "raw_p2": None, "p2_json": None,
            "final": final, "latency_s": 0.0, "calls": [], "validator": "rejected"}


def review(code: str, student_question: str, version: str) -> dict:
    cfg = load_config()
    vcfg = cfg["versions"][version]
    model = cfg["model"]
    calls: list = []

    if vcfg.get("validator"):
        msg = validate_input(code, cfg)
        if msg:
            return _invalid_result(version, msg)

    p1 = load_prompt(vcfg["p1_file"])
    numbered = number_code(code)
    values = {
        "code": code,
        "numbered_code": numbered if vcfg.get("numbered_code") else code,
        "syntax_check": syntax_check(code) if vcfg.get("syntax_check") else "OK",
        "student_question": student_question.strip() or "(none)",
    }
    user = p1.render_user(**values)

    raw_p1 = call_model(model, p1.system, user, vcfg.get("temperature"), vcfg.get("json_mode", False), calls)
    p1_json = parse_json(raw_p1)
    schema_retried = False
    if vcfg.get("schema_retry") and schema_errors(p1_json):
        schema_retried = True
        raw_p1 = call_model(model, p1.system, user, vcfg.get("temperature"), vcfg.get("json_mode", False), calls)
        p1_json = parse_json(raw_p1)

    raw_p2 = p2_json = None
    final: Any = p1_json if p1_json is not None else raw_p1
    if vcfg.get("guard") and isinstance(p1_json, dict):
        p2 = load_prompt(vcfg["p2_file"])
        user2 = p2.render_user(numbered_code=numbered, review_json=json.dumps(p1_json, ensure_ascii=False))
        raw_p2 = call_model(model, p2.system, user2, vcfg.get("guard_temperature", 0.0), True, calls)
        p2_json = parse_json(raw_p2)
        if isinstance(p2_json, dict) and not schema_errors(p2_json):
            final = p2_json

    latency = round(sum(c["seconds"] for c in calls), 2)
    return {"version": version, "raw_p1": raw_p1, "p1_json": p1_json, "raw_p2": raw_p2, "p2_json": p2_json,
            "final": final, "latency_s": latency, "calls": calls, "schema_retried": schema_retried,
            "syntax_check": values["syntax_check"] if vcfg.get("syntax_check") else None}


def guard_rewrites(result: dict) -> int:
    p2 = result.get("p2_json")
    if isinstance(p2, dict) and isinstance(p2.get("guard"), dict):
        fr = p2["guard"].get("fields_rewritten")
        return len(fr) if isinstance(fr, list) else 0
    return 0
