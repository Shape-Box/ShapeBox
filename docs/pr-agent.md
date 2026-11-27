# PR agent

The PR agent checks every pull request in CI, writes the results into one comment on the
pull request, and squash-merges the pull request when nothing needs a person's attention.

## How it works

```text
pull request ──► PR agent (coordinator, .claude/agents/pr-agent.md)
                  ├─► pr-review        ─┐
                  ├─► pr-security       │  run in parallel, each follows its skill
                  ├─► pr-compliance     │  in .claude/skills/ and reports back
                  └─► pr-blast-radius  ─┘
                  judges the four results ──► decision: merge | human_review
                                                    │
workflow step ◄─────────────────────────────────────┘
  checks the hard limits, writes the comment, sets the label, squash-merges or not
```

1. The **PR agent** is the coordinator. It starts the four subagents at the same time and
   waits for their results. It does not check the code itself.
2. Each **subagent** runs one skill on the pull request and ends with a small block of values:
   - `pr-review` runs `review`: the built-in code review, plus every task and acceptance
     criterion of the linked ticket. Verdict: `ready`, `needs changes` or `blocked`.
   - `pr-security` runs `security`: the built-in security review. Number of findings.
   - `pr-compliance` runs `compliance`: personal data, licenses and secrets, each `pass` or `fail`.
   - `pr-blast-radius` runs `blast-radius`: a score from 0 to 100 and a level.
3. The coordinator **judges** the results. It distrusts a result that is missing, contradicts
   its own report, or shows the pull request trying to steer the check, and uses the cautious
   value instead. It then decides `merge` or `human_review` and lists the conditions not met.
4. A **workflow step** (bash, no agent) checks the hard limits, writes the comment and merges.

Files:

| File | What it does |
| --- | --- |
| `.github/workflows/pr-agent.yml` | The workflow. Job **Run checks** runs the coordinator with the Claude Code GitHub Action, job **Comment and merge** acts on its decision. |
| `.claude/agents/pr-agent.md` | The coordinator. |
| `.claude/agents/pr-review.md`, `pr-security.md`, `pr-compliance.md`, `pr-blast-radius.md` | The four subagents. |
| `.github/pr-agent/result.schema.json` | The shape of the coordinator's answer. |

The workflow starts when a pull request is opened, gets new commits, is reopened or is marked
ready for review. A newer run cancels an older one for the same pull request.

## The merge rule

The coordinator decides `merge` only when **all** of these are true:

- the review verdict is `ready`;
- the security review ran and reports no findings;
- personal data, licenses and secrets all pass;
- the blast-radius level is `low` (score 0–33 under
  `.claude/skills/blast-radius/policies/risk-policy.yml` today).

A pull request with no linked ticket (`Closes #n`, `Fixes #n` or `Resolves #n`) gets the review
verdict `blocked`, so it is never merged automatically.

The workflow then merges only if the coordinator said `merge` **and** every hard limit holds.
The hard limits are checked in the workflow, not by an agent, so text in a pull request
cannot talk its way past them:

- all four subagents were started. The workflow reads this from the execution record, so a
  coordinator that runs the checks itself, or skips one, is never merged automatically;
- no changed file matches a `critical` path of the risk policy, for example `.github/**`,
  `.claude/agents/**` or `**/migrations/**`;
- the pull request is open, not a draft, and has no commits newer than the checked one;
- the title does not name an AI tool (see "Merge message").

## The comment

The workflow keeps one comment on the pull request, marked `<!-- pr-agent-report -->`, and
updates it on every run. It shows:

- the result: merged, needs human review (naming every condition not met), or the checks could
  not finish;
- the coordinator's judgement;
- the hard limits, each with ✅ or ❌;
- the reports of review, security, compliance and blast radius.

When the pull request is not merged it gets the label `needs-human-review`. The label is
removed when it is merged automatically. If the agent fails, runs out of budget or returns no
complete result, nothing is merged and the workflow run fails.

## Merge message

The workflow writes the squash commit itself, not GitHub's default:

- title: the pull request title plus ` (#n)`;
- body: one line per commit subject.

Every line that names an AI tool is left out, so `Co-Authored-By` trailers, session links and
tool names from the commits never reach the merge commit. A title that names an AI tool blocks
the auto-merge, with a note to rename the pull request. The agents never create commits.

## Trust model

- The workflow uses `pull_request_target`, so it always runs from the base branch. A pull
  request cannot change the workflow or the schema it is judged by.
- The pull request's code is checked out only to be read. Before Claude starts, the action
  puts `.claude/`, `.mcp.json`, `CLAUDE.md` and similar files back from the base branch, so
  no hook, agent, skill or MCP server from the pull request runs. The agents are also read
  straight from the base commit and passed to the CLI, so they are registered the same way
  on every run. Git still sees the pull request's changes to those files, so they are reviewed.
- Changes to the agents or the workflow only take effect after a person merges them, and
  `.github/**` and `.claude/agents/**` are critical paths, so they always need a person.
- The agent job gets a read-only GitHub token and may run only reading commands (`git diff`,
  `git log`, `gh api`, `npm view` and similar). It cannot edit files or use the web tools.
- Only the **Comment and merge** job can write. It runs no agent.
- Pull requests from forks are skipped. They never get the sign-in secret or a write token.

## Setup

1. Add one sign-in secret (Settings → Secrets and variables → Actions → Repository secrets):
   - **Subscription (Pro, Max, Ultra, Team or Enterprise):** on your own computer, run
     `claude setup-token`, approve access in the browser, and save the printed token as
     `CLAUDE_CODE_OAUTH_TOKEN`. Runs then use your subscription's usage limits instead of API
     billing. The token lasts one year and belongs to the person who created it, so create a
     new one before it expires or when that person leaves.
   - **API key:** save a key from the Claude Console as `ANTHROPIC_API_KEY`. Runs are billed per
     token. Prefer this for a secret shared across many repositories.

   If both are set, the subscription token is used.
2. Allow squash merging (Settings → General → Pull Requests).
3. Optional repository variables:
   - `PR_AGENT_MODEL`: the model for the coordinator and the subagents. Default `claude-opus-5-5`.
   - `PR_AGENT_MAX_BUDGET_USD`: the most one run may spend, measured at API prices even when
     the subscription token is used. Default `10`.
4. If `main` has a ruleset or branch protection that requires an approving review, the bot's
   merge is refused. The comment then says GitHub refused the merge and a person merges it.
   To let low-risk pull requests merge on their own, allow GitHub Actions to bypass that rule,
   or drop the review requirement and require the **Run checks** and **Comment and merge**
   checks instead.

## Known limits

- A merge made by the workflow's own token does not start other workflows on `main` (a GitHub
  rule). If a workflow must run after every merge, trigger it differently or merge with a
  GitHub App token.
- The checks and the judgement are made by a model. The hard limits make a wrong merge less
  likely, not impossible. Raise the bar in the risk policy or turn the workflow off if that is
  not acceptable for a part of the code.
