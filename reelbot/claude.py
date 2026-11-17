"""Asks Claude for JSON. Two ways to authenticate:

- CLAUDE_CODE_OAUTH_TOKEN: your Claude Pro/Max plan, through the Claude Code CLI
  (create the token once with `claude setup-token`).
- ANTHROPIC_API_KEY: pay-per-use API key.
"""
import json
import re
import subprocess

import requests

URL = "https://api.anthropic.com/v1/messages"
JSON_ONLY = "\nReply with one JSON object only. No prose, no code fences."


class ClaudeError(RuntimeError):
    pass


def available(cfg):
    s = cfg["secrets"]
    return bool(s["anthropic"] or s["claude_oauth"])


def _parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ClaudeError("Claude returned no JSON")
    return json.loads(m.group(0))


def _api(cfg, system, prompt, max_tokens):
    r = requests.post(
        URL,
        headers={"x-api-key": cfg["secrets"]["anthropic"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": cfg["claude"]["model"], "max_tokens": max_tokens,
              "system": system + JSON_ONLY, "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    if r.status_code != 200:
        raise ClaudeError(f"Claude API {r.status_code}: {r.text[:300]}")
    return "".join(b.get("text", "") for b in r.json().get("content", []))


def _cli(system, prompt, read_files=False):
    cmd = ["claude", "-p", "--output-format", "text"] + (["--allowedTools", "Read"] if read_files else [])
    try:
        r = subprocess.run(cmd, input=f"{system}{JSON_ONLY}\n\n{prompt}",
                           capture_output=True, text=True, timeout=600 if read_files else 300)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ClaudeError(f"Claude Code CLI failed: {e}")
    if r.returncode != 0:
        raise ClaudeError(f"Claude Code CLI error: {(r.stderr or r.stdout)[:300]}")
    return r.stdout


def ask_json(cfg, system, prompt, max_tokens=2500, read_files=False):
    """read_files lets Claude open files named in the prompt (images, for the scout); CLI only."""
    if cfg["secrets"]["anthropic"]:
        return _parse(_api(cfg, system, prompt, max_tokens))
    return _parse(_cli(system, prompt, read_files))
