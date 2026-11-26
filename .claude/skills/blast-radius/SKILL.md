---
name: blast-radius
description: Score how much could break if a change goes wrong, from 0 to 100, using the risk policy. Use when asked for the blast radius, risk or impact of a diff, branch or pull request, or before a merge decision. Reports only; never merges, comments or blocks.
argument-hint: "optional: PR number, branch or base ref (default: current branch vs main)"
---

# Blast Radius

Report one score from 0 (nothing else is affected) to 100 (could affect the whole system) for a change. This skill only reports. It does not merge, comment, label or block anything.

All rules live in `policies/risk-policy.yml`. Read it fresh every run. Never edit it, and never copy its paths, thresholds or point values into this file or your answer from memory.

## Steps

1. **Pick the change.** Use the argument if given: a PR number (`gh api repos/{owner}/{repo}/pulls/{n}/files --paginate`), a branch or a base ref. Otherwise compare the current branch to `main` with `git diff --numstat origin/main...HEAD`. If there is no diff, report score 0 and say so.
2. **Collect facts.** Changed file paths and added plus removed lines per file.
3. **Match paths.** Match each changed path against `protected_paths.critical` and `protected_paths.sensitive` (glob patterns). Note every match.
4. **Add points** from `scoring.signals` (each value is already on the 0-100 scale):
   - `sensitive_path`: once per changed file that matches `sensitive`.
   - `size_medium` or `size_high`: compare total lines and file count to `size`. Add only the highest one reached.
   - Judged signals (`many_dependents`, `untested_code`, `irreversible`, `security_medium`, `compliance_review`): look at the code and tests around the change. Add the points only with clear evidence, and name the evidence. If unsure, do not add.
5. **Sum** the points. That sum is the score, capped at `scoring.max_score`. There is no conversion step.
6. **Apply the critical floor.** If any critical path matched, the score is at least `critical_floor`.
7. **Find the level** from `levels`.

## Output

Keep it short, in this shape:

```text
Blast radius: 35/100 (medium)
- size_medium +15 (200 lines)
- sensitive_path +10 package.json
- sensitive_path +10 package-lock.json
Critical paths: none
```

Always list every signal that added points, with its reason, so the points add up to the score (before the critical floor). State the critical paths matched, or "none".

## Examples

- One-line change to `README.md`: no signals, `0/100 (low)`.
- 200 changed lines across `package.json`, `package-lock.json` and one source file: size_medium 15 + two sensitive files 20 = `35/100 (medium)`.
- A 5-line edit to `.github/workflows/ci.yml`: no signals, but a critical match raises it to `67/100 (high)`.

These examples assume the shipped policy values. If the policy changes, recompute rather than trusting them.
