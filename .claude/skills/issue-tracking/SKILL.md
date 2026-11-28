---
name: issue-tracking
description: Rules for reading, assigning, linking and setting the project status of GitHub issues with the `gh` CLI. Use when working on an existing issue, for example from the implement-ticket skill.
---

# Issue tracking

How to keep a GitHub issue and its project board in sync. Writing a new ticket is covered by `create-ticket`.

## Implementing a ticket

1. **Read.** `gh issue view <number> --comments`. Comments can change or narrow the ticket, so read them before building.
2. **Assign.** `gh issue edit <number> --add-assignee @me`.
3. **Set the status.** Look up the ids each time, never reuse remembered ones:
   - Project and issue item: `gh issue view <number> --json projectItems`
   - Status field and option ids: `gh project field-list <project-number> --owner <owner> --format json`
   - Set it: `gh project item-edit --id <item-id> --project-id <project-id> --field-id <status-field-id> --single-select-option-id <option-id>`

   Statuses used: **In Progress** when work starts, **In review** when a PR waits for review, **Done** when the PR is open and every acceptance criterion is verified.
4. **Link.** The PR description contains `Closes #<number>`, so GitHub closes the issue on merge. Never close it by hand.
5. **Comment.** When finishing, leave a short comment on the issue: what changed and the PR link.

## Rules

- If the issue is not on a project board, or the board has no matching status, say so and ask. Do not guess or add it silently.
- If `gh` lacks the `project` scope, ask the user to run `gh auth refresh -s project`.
- Never mark an issue Done while acceptance criteria are open.
