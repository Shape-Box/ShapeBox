---
name: review
description: Review a change against the ticket it belongs to. Runs the built-in /code-review for the code findings, then checks every task and acceptance criterion of the ticket against the diff and ends with a verdict (ready, needs changes, blocked). Use when asked to review a diff, branch or pull request, or to check whether a change does what its ticket asked. Reports only; never edits, comments, approves or merges.
argument-hint: "optional: PR number or branch, issue number (#n), code-review level (default: current branch vs main, linked issue, medium)"
---

# Review

Answer two questions about a change in one written review:

1. Is the code correct? The built-in `/code-review` answers this. Do not add bug-finding rules of your own.
2. Does it do what the ticket asked? This skill answers this.

This skill only reports. It does not edit code, comment on GitHub, approve or merge anything.

## Arguments

All optional, in any order:

- **Change:** a PR number (`42`) or a branch name. Default: the current branch compared with `main`.
- **Ticket:** an issue number written as `#n` or `issue n`. Default: the issue the change links to (step 2).
- **Level:** `low`, `medium`, `high`, `xhigh` or `max`, passed on to `/code-review`. Default: `medium`. Use `max` only when the person explicitly asked for it.

If an argument is ambiguous (a bare number could be the PR or the issue), treat a bare number as the PR and `#n` as the issue.

## Steps

1. **Pick the change.**
   - PR number: read it with `gh api repos/{owner}/{repo}/pulls/{n}` (title, body, `head.ref`, `base.ref`), then `git fetch origin pull/{n}/head` and `git diff origin/<base>...FETCH_HEAD`.
   - Branch: `git fetch origin <branch>` and `git diff origin/main...FETCH_HEAD`.
   - Default: `git diff origin/main...HEAD`.

   If the diff is empty, say so, give the verdict "blocked" and stop.

2. **Find the ticket.** Take the first that applies:
   1. The issue number passed as an argument.
   2. For a PR: an issue named in its body as `Closes #n`, `Fixes #n` or `Resolves #n` (any letter case).
   3. For a branch or the default: the open PR for that branch (`gh api "repos/{owner}/{repo}/pulls?head={owner}:<branch>&state=open"`) and its body as in 2.2, then the same keywords in the commit messages of the change (`git log origin/main..<head>`).

   Read the ticket with `gh api repos/{owner}/{repo}/issues/{n}`. If no ticket is found, ask for the issue number and stop. Do not guess one. If several are linked, review against all of them and name each.

3. **Run the built-in code review. Always, on every run.** Invoke the `code-review` skill with the level and the same change, for example `medium 42` or `medium my-branch`. For the default, pass the current branch name (`git branch --show-current`) so it reviews the same diff as step 1. Never pass `--comment` or `--fix`. Keep its findings exactly as it gives them: do not add, drop, reword or re-rank any.

4. **Check the ticket against the diff.**
   - List every acceptance criterion and every task (`- [ ]` item) from the ticket, word for word.
   - Mark each one **met**, **not met** or **unclear**.
     - met: name the file and line that does it (a test counts as strong evidence).
     - not met: say what is missing.
     - unclear: say what would settle it (for example "no test covers this; run X and check Y").
   - Judge from the diff and the code around it. Do not mark anything met because a commit message or the PR body says so.

5. **Flag unrequested changes.** List changed files or hunks that no task, criterion or the goal asks for, and any change to something the ticket lists under "Out of scope". Small edits that a task clearly needs (imports, a test helper) are not unrequested.

6. **Give the verdict.**
   - **blocked:** the review cannot be done properly: the diff is empty, or the ticket has no acceptance criteria that can be checked. Say what a person must decide or add first.
   - **needs changes:** any criterion or task is not met or unclear, `/code-review` reports a finding the change introduces, or there are unrequested changes.
   - **ready:** every criterion and task is met, `/code-review` reports no finding the change introduces, and there are no unrequested changes.

   Findings `/code-review` marks as pre-existing or as nits are listed but do not change the verdict on their own.

## Output

Keep it short, in this shape:

```text
Review: PR 42 against #3
Code review (built-in /code-review, level medium):
- src/api/users.ts:58 returns every user's records when the id is missing [important]
- src/api/users.ts:12 unused import [nit]

Acceptance criteria:
- [met] Returns 3 suggestions within 5 seconds: src/suggest.ts:40, test in test/suggest.test.ts:12
- [not met] If no ticket can be found, the skill asks for one and stops: no such branch in SKILL.md
- [unclear] Works offline: no test covers it; disconnect the network and run the suggest command

Tasks:
- [met] Write SKILL.md: .claude/skills/review/SKILL.md
- [not met] Define a fixed output format: no Output section

Unrequested changes:
- package.json: adds lodash, which no task asks for

Verdict: needs changes
```

When `/code-review` finds nothing, write `Code review (built-in /code-review, level medium): no findings`. When there are no unrequested changes, write `Unrequested changes: none`.

## Examples

- Every criterion met, no code-review findings, only the requested files changed: `Verdict: ready`.
- All criteria met, but `/code-review` reports a bug the change introduces: `Verdict: needs changes`.
- All criteria met, and `/code-review` only reports a pre-existing bug in untouched code: `Verdict: ready`, with that finding listed.
- The ticket has no "Acceptance criteria" section and its tasks cannot be checked: `Verdict: blocked`, asking for checkable criteria.
- No issue argument, no linked issue in the PR or the commits: ask for the issue number and stop.
