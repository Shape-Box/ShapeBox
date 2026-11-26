#!/usr/bin/env python3
"""Act on the PR agent's check results: comment, label and maybe squash-merge.

The agent only reports. This script makes the merge decision with fixed rules, so a
pull request cannot talk its way into a merge. It reads the agent's result file, checks
every auto-merge condition, writes one summary comment on the pull request (updated on
every run), and squash-merges only when all conditions hold.

Usage (all values also come from the environment in CI):
    decide.py --repo OWNER/NAME --pr 42 --head-sha SHA --analyze-result success \
              --result result.json --policy risk-policy.yml --run-url URL [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

import yaml

MARKER = "<!-- pr-agent-report -->"
BOT_LOGIN = "github-actions[bot]"
LABEL = "needs-human-review"
# Lines matching this never go into a merge commit message.
TOOL_REFERENCE = re.compile(r"claude|anthropic", re.IGNORECASE)
MAX_REPORT_CHARS = 12000

COMPLIANCE_AREAS = ("personal_data", "licenses", "secrets")


class ResultError(Exception):
    """The agent's result is missing or does not have the expected shape."""


class GitHubError(Exception):
    """A GitHub API call failed."""


# --- Agent result -------------------------------------------------------------------


def _require(obj: dict, key: str, kind, where: str):
    if not isinstance(obj, dict) or key not in obj:
        raise ResultError(f"{where}.{key} is missing")
    value = obj[key]
    if kind is int and isinstance(value, bool):
        raise ResultError(f"{where}.{key} must be an integer")
    if not isinstance(value, kind):
        raise ResultError(f"{where}.{key} has the wrong type")
    return value


def _require_enum(obj: dict, key: str, allowed: tuple, where: str) -> str:
    value = _require(obj, key, str, where)
    if value not in allowed:
        raise ResultError(f"{where}.{key} is {value!r}, expected one of {allowed}")
    return value


def validate_result(result) -> dict:
    """Check the result has every field the decision needs. Returns it unchanged."""
    if not isinstance(result, dict):
        raise ResultError("the result is not an object")
    review = _require(result, "review", dict, "result")
    _require_enum(review, "verdict", ("ready", "needs changes", "blocked"), "review")
    _require(review, "report", str, "review")
    security = _require(result, "security", dict, "result")
    _require(security, "ran", bool, "security")
    if _require(security, "finding_count", int, "security") < 0:
        raise ResultError("security.finding_count is negative")
    _require(security, "report", str, "security")
    compliance = _require(result, "compliance", dict, "result")
    for area in COMPLIANCE_AREAS:
        _require_enum(compliance, area, ("pass", "fail"), "compliance")
    _require(compliance, "report", str, "compliance")
    blast = _require(result, "blast_radius", dict, "result")
    score = _require(blast, "score", int, "blast_radius")
    if not 0 <= score <= 100:
        raise ResultError("blast_radius.score is outside 0-100")
    _require_enum(blast, "level", ("low", "medium", "high"), "blast_radius")
    _require(blast, "critical_paths", list, "blast_radius")
    _require(blast, "report", str, "blast_radius")
    return result


def load_result(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ResultError("the agent wrote no result") from exc
    except json.JSONDecodeError as exc:
        raise ResultError(f"the result is not valid JSON ({exc})") from exc
    return validate_result(data)


# --- Policy -------------------------------------------------------------------------


def glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a policy glob: `**` spans folders, `*` and `?` stay inside one."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def critical_matches(paths: list[str], patterns: list[str]) -> list[str]:
    compiled = [glob_to_regex(p) for p in patterns]
    return [path for path in paths if any(rx.match(path) for rx in compiled)]


def load_policy(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    low = policy["levels"]["low"]
    critical = policy["protected_paths"]["critical"]
    if not (isinstance(low, list) and len(low) == 2 and isinstance(critical, list)):
        raise ValueError("risk policy has no usable `levels.low` or `protected_paths.critical`")
    return policy


# --- Decision -----------------------------------------------------------------------


@dataclass
class Condition:
    name: str
    ok: bool
    detail: str


@dataclass
class Decision:
    conditions: list[Condition] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return bool(self.conditions) and all(c.ok for c in self.conditions)

    @property
    def failed(self) -> list[Condition]:
        return [c for c in self.conditions if not c.ok]


def evaluate(result: dict, policy: dict, pr: dict, changed_files: list[str], head_sha: str) -> Decision:
    review = result["review"]
    security = result["security"]
    compliance = result["compliance"]
    blast = result["blast_radius"]
    low_min, low_max = policy["levels"]["low"]
    critical = critical_matches(changed_files, policy["protected_paths"]["critical"])
    failing_areas = [a.replace("_", " ") for a in COMPLIANCE_AREAS if compliance[a] != "pass"]

    conditions = [
        Condition(
            'Review verdict is "ready"',
            review["verdict"] == "ready",
            f'verdict "{review["verdict"]}"',
        ),
        Condition(
            "Security check reports no findings",
            security["ran"] and security["finding_count"] == 0,
            "did not run" if not security["ran"] else f'{security["finding_count"]} finding(s)',
        ),
        Condition(
            "All three compliance areas pass",
            not failing_areas,
            "all pass" if not failing_areas else "failed: " + ", ".join(failing_areas),
        ),
        Condition(
            'Blast radius level is "low"',
            blast["level"] == "low" and low_min <= blast["score"] <= low_max,
            f'{blast["score"]}/100 ({blast["level"]})',
        ),
        Condition(
            "No critical path changed",
            not critical,
            "none" if not critical else ", ".join(f"`{p}`" for p in critical),
        ),
        Condition(
            "Pull request is open, not a draft, and unchanged since the checks",
            pr["state"] == "open" and not pr["draft"] and pr["head"]["sha"] == head_sha,
            _pr_state_detail(pr, head_sha),
        ),
        Condition(
            "Title can be used in the merge message",
            not TOOL_REFERENCE.search(pr["title"]),
            "ok" if not TOOL_REFERENCE.search(pr["title"])
            else "the title names an AI tool; rename the pull request",
        ),
    ]
    return Decision(conditions)


def _pr_state_detail(pr: dict, head_sha: str) -> str:
    if pr["state"] != "open":
        return f'state is "{pr["state"]}"'
    if pr["draft"]:
        return "draft"
    if pr["head"]["sha"] != head_sha:
        return "new commits arrived; the next run checks them"
    return "ok"


def merge_message(pr: dict, commit_messages: list[str]) -> tuple[str, str]:
    """Squash title and body with every reference to an AI tool or session removed."""
    title = f'{pr["title"].strip()} (#{pr["number"]})'
    lines = []
    for message in commit_messages:
        subject = message.strip().splitlines()[0].strip() if message.strip() else ""
        if subject and not TOOL_REFERENCE.search(subject):
            lines.append(f"* {subject}")
    return title, "\n".join(lines)


# --- Comment ------------------------------------------------------------------------


def fenced(text: str) -> str:
    text = text.strip() or "(no output)"
    if len(text) > MAX_REPORT_CHARS:
        text = text[:MAX_REPORT_CHARS] + "\n… (shortened)"
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def render_comment(
    *,
    head_sha: str,
    run_url: str,
    result: dict | None = None,
    decision: Decision | None = None,
    merged: bool = False,
    merge_error: str | None = None,
    failure: str | None = None,
) -> str:
    parts = [MARKER, "## PR agent checks", ""]
    if failure is not None:
        parts += [
            "**Result: the checks could not finish.** The pull request was not merged and "
            "needs human review.",
            "",
            f"Reason: {failure}",
            "",
            f"Commit `{head_sha[:7]}` · [workflow run]({run_url})",
        ]
        return "\n".join(parts) + "\n"

    assert result is not None and decision is not None
    if merged:
        headline = "**Result: squash-merged automatically.** Every check is clean and the blast radius is low, so no human review is needed."
    elif decision.eligible and merge_error:
        headline = f"**Result: needs human review.** Every condition passed, but GitHub refused the merge: `{merge_error}`"
    elif decision.eligible:
        headline = "**Result: eligible for auto-merge** (dry run, nothing was merged)."
    else:
        names = "; ".join(c.name for c in decision.failed)
        headline = f"**Result: needs human review.** Not met: {names}."
    parts += [headline, "", f"Commit `{head_sha[:7]}` · [workflow run]({run_url})", ""]

    parts += ["### Auto-merge conditions", ""]
    for c in decision.conditions:
        parts.append(f"- {'✅' if c.ok else '❌'} {c.name}: {c.detail}")

    for heading, key in (
        ("Review", "review"),
        ("Security", "security"),
        ("Compliance", "compliance"),
        ("Blast radius", "blast_radius"),
    ):
        parts += ["", f"### {heading}", "", fenced(result[key]["report"])]
    return "\n".join(parts) + "\n"


# --- GitHub -------------------------------------------------------------------------


def gh(method: str, path: str, body: dict | None = None):
    cmd = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    if body is not None:
        cmd += ["--input", "-"]
    proc = subprocess.run(
        cmd,
        input=json.dumps(body) if body is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitHubError((proc.stderr or proc.stdout).strip() or f"gh exited {proc.returncode}")
    return json.loads(proc.stdout) if proc.stdout.strip() else None


def gh_pages(path: str) -> list:
    items, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        batch = gh("GET", f"{path}{sep}per_page=100&page={page}")
        items.extend(batch)
        if len(batch) < 100:
            return items
        page += 1


class GitHub:
    def __init__(self, repo: str, number: int, dry_run: bool):
        self.repo, self.number, self.dry_run = repo, number, dry_run

    def pull(self) -> dict:
        return gh("GET", f"repos/{self.repo}/pulls/{self.number}")

    def changed_files(self) -> list[str]:
        files = gh_pages(f"repos/{self.repo}/pulls/{self.number}/files")
        paths = []
        for f in files:
            paths.append(f["filename"])
            if f.get("previous_filename"):
                paths.append(f["previous_filename"])
        return paths

    def commit_messages(self) -> list[str]:
        commits = gh_pages(f"repos/{self.repo}/pulls/{self.number}/commits")
        return [c["commit"]["message"] for c in commits]

    def upsert_comment(self, body: str) -> None:
        if self.dry_run:
            print(body)
            return
        comments = gh_pages(f"repos/{self.repo}/issues/{self.number}/comments")
        mine = [
            c for c in comments
            if c["user"]["login"] == BOT_LOGIN and c["body"].startswith(MARKER)
        ]
        if mine:
            gh("PATCH", f"repos/{self.repo}/issues/comments/{mine[0]['id']}", {"body": body})
        else:
            gh("POST", f"repos/{self.repo}/issues/{self.number}/comments", {"body": body})

    def set_needs_review(self, needed: bool) -> None:
        if self.dry_run:
            print(f"[dry run] label {LABEL}: {'add' if needed else 'remove'}")
            return
        if needed:
            gh("POST", f"repos/{self.repo}/issues/{self.number}/labels", {"labels": [LABEL]})
            return
        try:
            gh("DELETE", f"repos/{self.repo}/issues/{self.number}/labels/{LABEL}")
        except GitHubError:
            pass  # the label was not there

    def squash_merge(self, head_sha: str, title: str, message: str) -> None:
        gh(
            "PUT",
            f"repos/{self.repo}/pulls/{self.number}/merge",
            {
                "merge_method": "squash",
                "sha": head_sha,
                "commit_title": title,
                "commit_message": message,
            },
        )


# --- Main ---------------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    github = GitHub(args.repo, args.pr, args.dry_run)

    def fail(reason: str) -> int:
        github.upsert_comment(render_comment(head_sha=args.head_sha, run_url=args.run_url, failure=reason))
        github.set_needs_review(True)
        print(f"Checks could not finish: {reason}", file=sys.stderr)
        return 1

    if args.analyze_result != "success":
        return fail(f"the agent job ended with `{args.analyze_result}`.")
    try:
        result = load_result(args.result)
    except ResultError as exc:
        return fail(f"{exc}.")

    try:
        policy = load_policy(args.policy)
        pr = github.pull()
        decision = evaluate(result, policy, pr, github.changed_files(), args.head_sha)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, GitHubError) as exc:
        return fail(f"the merge decision could not be made ({type(exc).__name__}: {exc}).")

    merged, merge_error = False, None
    if decision.eligible and not args.dry_run:
        title, message = merge_message(pr, github.commit_messages())
        try:
            github.squash_merge(args.head_sha, title, message)
            merged = True
        except GitHubError as exc:
            merge_error = str(exc).replace("`", "'")[:300]

    github.set_needs_review(not merged)
    github.upsert_comment(
        render_comment(
            head_sha=args.head_sha,
            run_url=args.run_url,
            result=result,
            decision=decision,
            merged=merged,
            merge_error=merge_error,
        )
    )
    for c in decision.conditions:
        print(f"{'PASS' if c.ok else 'FAIL'}  {c.name}: {c.detail}")
    print("Merged." if merged else "Not merged.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = os.environ.get
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=env("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int, default=env("PR_NUMBER"))
    parser.add_argument("--head-sha", default=env("HEAD_SHA"))
    parser.add_argument("--analyze-result", default=env("ANALYZE_RESULT"))
    parser.add_argument("--result", default=env("RESULT_FILE"))
    parser.add_argument("--policy", default=env("RISK_POLICY"))
    parser.add_argument("--run-url", default=env("RUN_URL", ""))
    parser.add_argument("--dry-run", action="store_true", help="print instead of writing to GitHub")
    args = parser.parse_args(argv)
    missing = [n for n in ("repo", "pr", "head_sha", "analyze_result", "result", "policy") if not getattr(args, n)]
    if missing:
        parser.error("missing: " + ", ".join(missing))
    return args


if __name__ == "__main__":
    sys.exit(run(parse_args()))
