---
name: docs-writer
description: Write or update project documentation as portable Markdown with Mermaid diagrams in the /docs folder: architecture, databases, decisions, runbooks. Use for any docs or diagram request.
---

# Docs Writer

Maintain a living knowledge base in the `/docs` folder using plain Markdown and Mermaid. The output must render in any common viewer (Obsidian, VS Code, GitHub, GitLab, MkDocs, Docusaurus). Never produce binary or proprietary formats.

## Before writing

1. Locate the docs root (default `/docs`). List it and read `index.md` and any `CLAUDE.md` rules first.
2. Search for an existing note on the topic. Update it instead of creating a duplicate.
3. Read the actual source (code, SQL schema, config, Terraform, OpenAPI) before documenting it. Never invent components, tables, endpoints or relationships. If something is unclear, mark it with a `> [!QUESTION]` callout instead of guessing.

## Folder layout (create only what is needed)

```text
docs/
  index.md            entry point, links to every note
  glossary.md
  pr-agent.md         existing notes stay where they are
  architecture/       overview.md, one note per component or service
  database/           schema.md, one note per major table group
  decisions/          ADRs: 0001-short-title.md
  runbooks/           how-to and operations
```

Use lowercase kebab-case file names. One topic per note. Notes that already sit directly in `docs/` stay there, because other files link to them. Put new notes in the folder that fits. If the project later uses a different structure, follow that one.

## Note format

Every note starts with YAML frontmatter:

```yaml
---
title: Order Service
type: component        # overview | component | database | decision | runbook | glossary
status: current        # draft | current | deprecated
updated: 2026-11-23
sources: [src/orders/, db/migrations/]
tags: [architecture, backend]
---
```

Then:

- One `# H1` matching the title, a 1-2 sentence summary, then sections with `##`.
- Link notes with standard relative Markdown links: `[Order Service](../architecture/order-service.md)` and anchors like `order-service.md#responsibilities`. Do not use `[[wiki-links]]` unless the project already does. Every note must link to at least one other note and be linked from `index.md` or a parent note.
- Use GitHub-style callouts, which render in Obsidian, GitHub and GitLab: `> [!NOTE]`, `> [!WARNING]`, `> [!QUESTION]`.
- Prefer short paragraphs, tables for comparisons and bullet lists for enumerations. Put code, SQL and config in fenced blocks with a language tag.
- Do not use HTML unless Markdown cannot express it.

## Diagrams (Mermaid only)

Put diagrams in fenced `mermaid` blocks directly in the note. Pick the type by purpose:

| Purpose | Mermaid type |
|---|---|
| System context, containers, data flow | `flowchart LR` or `flowchart TD` |
| C4 views | `C4Context`, `C4Container` (or flowchart with subgraphs) |
| Request or interaction over time | `sequenceDiagram` |
| Database tables | `erDiagram` |
| Lifecycles and statuses | `stateDiagram-v2` |
| Deployment and infra | `flowchart` with `subgraph` per environment |
| Timelines and plans | `gantt` or `timeline` |

Rules:

- One diagram answers one question. Keep it to about 15 nodes. Split larger systems into an overview plus per-component diagrams and link them.
- Give every node a short readable label. Use quoted labels when they contain spaces or punctuation: `A["Order Service"]`.
- Label edges with what flows (`-->|HTTP/JSON|`, `-->|publishes OrderCreated|`).
- Use `subgraph` for boundaries (service, network, team). Keep one consistent direction.
- For `erDiagram`, derive entities, columns, keys and cardinality from the real schema.
- Add a one-line caption under each diagram saying what it shows and which source it was derived from.
- Check syntax carefully: balanced brackets, no unescaped special characters, unique node IDs. A diagram that fails to render is worse than none. Avoid renderer-specific features so it works in every viewer.

## Architecture overview note

`architecture/overview.md` must contain: purpose, a system context diagram, a container/component diagram, the main data flows (sequence diagrams for the key ones), a table of components linking to their notes, and external dependencies.

## Decisions (ADRs)

Use `decisions/NNNN-title.md` with sections: Context, Decision, Consequences, Alternatives considered, Status. Never rewrite an accepted ADR. Supersede it with a new one and link both ways.

## Updating existing docs

- Make the smallest edit that makes the note correct. Keep the author's wording and structure where it is still accurate.
- Never delete human-written content without saying why. If something looks outdated, mark it with a `> [!WARNING]` callout ("Possibly outdated") and state what contradicts it.
- Bump `updated` in the frontmatter when content changes.
- If code and docs disagree, trust the code and fix the docs. Report the discrepancy.
- After changes, check for broken links and orphan notes, and fix them.

## Finish

Reply with a short list of the notes created or changed and any open `[!QUESTION]` items. Do not repeat the note contents.
