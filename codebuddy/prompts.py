"""Load the documented prompt files from prompts/ without changing their text."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SYSTEM_MARKER = "--- SYSTEM PROMPT ---"
USER_MARKER = "--- USER PROMPT TEMPLATE ---"

# Only these placeholders are ever filled. The prompts also contain JSON braces,
# so str.format() must NOT be used.
KNOWN_VARIABLES = ("code", "numbered_code", "syntax_check", "student_question", "review_json")


@dataclass(frozen=True)
class Prompt:
    path: str
    system: str  # "" means no system instruction
    user_template: str

    def render_user(self, **values: str) -> str:
        text = self.user_template
        for name in KNOWN_VARIABLES:
            if name in values:
                text = text.replace("{" + name + "}", values[name])
        return text


def load_prompt(rel_path: str) -> Prompt:
    raw = (ROOT / rel_path).read_text(encoding="utf-8")
    if SYSTEM_MARKER not in raw or USER_MARKER not in raw:
        raise ValueError(f"{rel_path}: missing prompt section markers")
    head, rest = raw.split(SYSTEM_MARKER, 1)
    system, user = rest.split(USER_MARKER, 1)
    # Header lines before the system marker are '#' comments and are ignored.
    return Prompt(path=rel_path, system=system.strip(), user_template=user.strip("\n").rstrip())
