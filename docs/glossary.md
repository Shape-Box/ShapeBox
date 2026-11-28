---
title: Glossary
type: glossary
status: current
updated: 2026-11-28
sources: [docs/pr-agent.md]
tags: [glossary, ci]
---

# Glossary

The terms used by the [PR agent](pr-agent.md). Back to the [index](index.md).

| Term | Meaning |
| --- | --- |
| PR agent | The coordinator that checks every pull request and decides whether it needs a person. |
| Subagent | One of the four helpers the PR agent starts: review, security, compliance, blast radius. |
| Blast radius | A score from 0 to 100 for how much could break if a change goes wrong. |
| Hard limit | A rule the workflow checks itself, whatever the agent decided. |
