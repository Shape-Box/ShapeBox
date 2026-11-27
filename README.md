# ShapeBox

This repository holds the agent skills and the PR agent that review, check and merge pull
requests.

## Skills

The skills live in `.claude/skills/`:

| Skill | What it does |
| --- | --- |
| `blast-radius` | Scores from 0 to 100 how much a change could break. |
| `commit` | Writes commit messages in the Conventional Commits format. |
| `compliance` | Checks a change for personal data, license and secrets problems. |
| `create-ticket` | Writes a GitHub issue from a short description. |
| `review` | Reviews a change against the ticket it belongs to. |
| `security` | Runs the built-in security review on a change. |

## PR agent

Every pull request is checked automatically. See [docs/pr-agent.md](docs/pr-agent.md).
