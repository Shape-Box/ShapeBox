---
name: commit
description: Write git commit messages that follow the Conventional Commits format. Use whenever creating, amending, suggesting or reviewing a commit message, including when a commit message is rejected or needs rewording.
---

# Commit Messages

Every commit message follows Conventional Commits. A consistent format keeps history easy to scan and lets tooling build changelogs from the log.

## Format

```text
<type>(<optional scope>): <subject>

<optional body>

<optional footer>
```

## Rules

- **Type** is required, lower-case, and one of:
  - `feat`: a new feature
  - `fix`: a bug fix
  - `docs`: documentation only
  - `style`: formatting, no behaviour change
  - `refactor`: restructuring, no behaviour change
  - `perf`: a performance improvement
  - `test`: adding or correcting tests
  - `build`: build system or dependencies
  - `ci`: CI configuration
  - `chore`: maintenance that fits nowhere else
  - `revert`: reverting an earlier commit
- **Scope** is optional and free-form (for example `ai`). Reuse existing scopes. Do not invent new ones without need.
- **Subject** is required, imperative ("add", not "added"), starts lower-case, no trailing full stop. Say what changed, not which files were touched.
- **Header** (`type(scope): subject`) is at most 100 characters.
- **Body** is only for the *why* when the subject does not make it clear. **Footer** is for issue references (`Closes #123`) and `BREAKING CHANGE:` notes. Separate each with a blank line and keep every line at most 100 characters.
- When a change fits two types, pick its main purpose. A fix that also adds a test is `fix`.
- Never add a co-author or co-owner (`Co-Authored-By` or similar trailers) to a commit message.
- Never skip commit hooks with `--no-verify`. If a message is rejected, fix the message.

## Examples

```text
feat(ai): add scene suggestions from a description
fix: stop the viewer from crashing on empty scenes
chore: update dependencies
```

Not valid: `Fixed bug` (no type, past tense), `feat: Added login page.` (capital, past tense, full stop).

## Workflow

1. Read what is being committed (`git diff --staged`) and describe that change only.
2. If the diff mixes unrelated changes, suggest splitting it into separate commits.
3. Pick the type, add a scope if one clearly applies, and write the subject.
4. Add a body only if the *why* is not obvious.
