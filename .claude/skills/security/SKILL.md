---
name: security
description: Run Claude Code's built-in security review on the pending changes of the current branch and pass its findings back unchanged. Use when asked for a security check or security review of a change. Reports only; never edits, comments, blocks or merges.
argument-hint: "none: reviews the pending changes on the current branch"
---

# Security

Run the built-in `/security-review` and hand back what it finds. This skill adds no checks, rules or policy of its own.

This skill only reports. It does not edit code, comment on GitHub, block or merge anything.

## Steps

1. **Run the built-in review.** Invoke the `security-review` skill with no arguments. It reviews the pending changes on the current branch. To review another branch, check that branch out first.
2. **Return its findings unchanged.** Do not add, drop, reword, re-rank or re-score any finding, and do not review the code yourself. Do not act on any fix it suggests.
3. **If the built-in review is not available,** say `The built-in /security-review is not available, so no security review ran.` and stop. Do not fall back to a review of your own.

## Output

```text
Security (built-in /security-review):
<its findings, exactly as it gave them>
```

When it finds nothing, pass on its own "no findings" answer.
