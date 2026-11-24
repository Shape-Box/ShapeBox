---
name: create-ticket
description: Write a well-formed GitHub issue (ticket) from a short description and publish it with the `gh` CLI. Use when the user or an agent asks to write, file or publish a ticket or issue, or says "turn this into a ticket".
argument-hint: "what the ticket is about"
---

# Create Ticket

Turn the description in `$ARGUMENTS` (or the conversation) into a GitHub issue. If there is nothing to describe, ask what the ticket is about and stop.

## Steps

1. **Check for duplicates.** `gh issue list --state open --search "<keywords>"`. If a similar ticket exists, show it and ask whether to extend it instead.
2. **Draft** the title and body in the format below. Fill only what you know. Ask the user about missing goals or acceptance criteria instead of inventing them.
3. **Show the exact title and body and wait for a clear yes.** Creating an issue is visible to others.
4. **Create it.** Use a heredoc with its own delimiter for the body:

   ```bash
   gh issue create --title "..." --body "$(cat <<'TICKET'
   ...
   TICKET
   )"
   ```

## Title

Short, imperative, no full stop, like a commit subject: "Add scene suggestions from a description".

## Body

```markdown
## Context
Why this matters, for whom.

## Goal
What should be true when it is done.

## Tasks
- [ ] Small, checkable steps

## Acceptance criteria
- Observable results someone can verify

## Out of scope
What this ticket does not cover (omit if nothing).
```

## Rules

- Plain language, no jargon. Ask: "Would someone without prior knowledge understand this?"
- One ticket, one outcome. If it covers two independent things, suggest splitting it.
- Acceptance criteria must be checkable by a person or a test, because the planner, implementer and reviewer agents work from them. "Works well" is not valid; "returns 3 suggestions within 5 seconds" is.
- Never put secrets or personal data in a ticket.
