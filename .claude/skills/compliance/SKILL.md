---
name: compliance
description: Check a change for compliance problems in three areas, personal data, dependency licenses, and secrets or sensitive files, using the compliance policy, and print a pass/fail report with evidence. Use when asked for a compliance, privacy, license or secrets check of a diff, branch or pull request, or before a merge decision. Reports only; never edits, comments, blocks or merges.
argument-hint: "optional: PR number, branch or base ref (default: current branch vs main)"
---

# Compliance

Check a change in three areas and mark each one pass or fail:

1. **Personal data:** code that collects, stores, logs or sends data about a person.
2. **Licenses:** dependencies whose license the project may not use.
3. **Secrets:** keys, tokens, passwords and files that must never be committed.

This skill only reports. It does not edit code, comment on GitHub, block or merge anything.

All rules live in `policies/compliance-policy.yml` next to this file. Read it fresh every run. Never edit it, and never copy its categories, licenses, patterns or settings into this file or your answer from memory.

## Steps

1. **Pick the change.** Use the argument if given:
   - PR number: read it with `gh api repos/{owner}/{repo}/pulls/{n}` (`base.ref`), then `git fetch origin pull/{n}/head` and `git diff origin/<base>...FETCH_HEAD`.
   - Branch or base ref: diff it against `origin/main`, or the current branch against that base.
   - Default: `git diff origin/main...HEAD`.

   If there is no diff, report all three areas as pass and say there was no change.

2. **Read the policy** from `policies/compliance-policy.yml`.

3. **Personal data.** Look at changed code and configuration, not documentation.
   - Find added or changed code that collects, stores, logs or sends any category in `personal_data.categories`.
   - For each place, check every rule in `personal_data.required_handling` against the changed code and the code around it.
   - Each rule not met is a finding: name the file and line, the category, and the rule `id`.
   - The area fails if there is at least one finding.

4. **Licenses.**
   - Find added dependencies and changed versions in files matching `licenses.manifests`. Lockfiles only count when they change a version a manifest asks for.
   - Look up each dependency's license for that version, in this order: the license field in the lockfile or manifest, the package registry (for example `npm view <name>@<version> license`, the PyPI JSON API, crates.io), then the LICENSE file of the package source.
   - If no source states it, mark the license `unknown`. Do not guess from the name or from other versions.
   - A license not in `licenses.allowed` is a finding: name the dependency, the version, the license and the manifest file and line. An `unknown` license is a finding when `licenses.unknown` is `fail`.
   - The area fails if there is at least one finding.

5. **Secrets.** Look at every added or changed file, documentation included.
   - Each added or changed path matching `secrets.never_commit` and not `secrets.allowed_files` is a finding.
   - Each added line matching a pattern in `secrets.patterns` is a finding, unless the value is clearly a placeholder (for example `changeme`, `<token>`, `xxx`, `example`) or is read from the environment. Name the file, line and pattern `id`. Never print the secret itself: show at most its first 4 characters followed by `…`.
   - The area fails if there is at least one finding.

## Output

Keep it short, in this shape:

```text
Compliance: PR 42
Personal data: fail
- src/signup.ts:31 logs the email address in plain form (no-logs)
- db/users.sql:12 stores date of birth with no retention period (retention)
Licenses: fail
- left-pad-gpl 2.1.0: GPL-3.0-only, not allowed (package.json:18)
- tiny-util 0.3.0: unknown (package.json:19)
Secrets: pass
```

Every finding names the file and line (or the dependency, version and license) and the policy rule it breaks. An area with no findings is just `pass`.

## Examples

- A change that only edits `README.md` with no keys in it: all three areas `pass`.
- A change that adds a dependency licensed `GPL-3.0-only` when that is not in `licenses.allowed`: `Licenses: fail`, naming `GPL-3.0-only`.
- A change that adds `const apiKey = "sk-live-…"` or commits a `.env` file: `Secrets: fail`.
- A change that adds a sign-up form saving the email address, with no delete path: `Personal data: fail` with `deletion`.

These examples assume the shipped policy values. If the policy changes, recheck rather than trusting them.
