# PR agent

The PR agent checks every pull request in CI, writes the results into one comment on the
pull request, and squash-merges the pull request when nothing needs a person's attention.

Files:

| File | What it does |
| --- | --- |
| `.github/workflows/pr-agent.yml` | The workflow. Job **Run checks** runs the agent, job **Comment and merge** acts on its result. |
| `.github/pr-agent/prompt.md` | What the agent is asked to do. |
| `.github/pr-agent/result.schema.json` | The shape of the agent's answer. |
| `.github/pr-agent/decide.py` | Makes the merge decision, writes the comment, sets the label and merges. |
| `.github/pr-agent/test_decide.py` | Tests for `decide.py`. |

## What runs

The workflow starts when a pull request is opened, gets new commits, is reopened or is marked
ready for review. A newer run cancels an older one for the same pull request.

The agent runs four checks, each by following its skill in `.claude/skills/`:

1. **Review** (`review`): the built-in code review, plus every task and acceptance criterion
   of the linked ticket. Verdict: `ready`, `needs changes` or `blocked`.
2. **Security** (`security`): the built-in security review.
3. **Compliance** (`compliance`): personal data, licenses and secrets, each `pass` or `fail`.
4. **Blast radius** (`blast-radius`): a score from 0 to 100 and a level, from the risk policy.

The results go into one comment on the pull request, marked `<!-- pr-agent-report -->`.
Each run updates that comment instead of adding a new one.

## The auto-merge rule

The pull request is squash-merged automatically only when **all** of these are true:

- the review verdict is `ready`;
- the security check ran and reports no findings;
- all three compliance areas pass;
- the blast-radius level is `low`, and the score is inside the `low` band of
  `.claude/skills/blast-radius/policies/risk-policy.yml` (0–33 today);
- no changed file matches a `critical` path of that policy, for example `.github/**`. The
  decision script checks this itself from the changed files, whatever the agent reports;
- the pull request is open, not a draft, and has no commits newer than the checked one;
- the title does not name an AI tool (see "Merge message" below).

Otherwise nothing is merged. The comment lists every condition with ✅ or ❌, and the pull
request gets the label `needs-human-review`. The label is removed when the pull request is
merged automatically.

The rule lives in code (`decide.py`), not in the agent. The agent only reports, so text in a
pull request cannot talk it into a merge.

A pull request with no linked ticket (`Closes #n`, `Fixes #n` or `Resolves #n` in its body or
commits) gets the review verdict `blocked` and is never merged automatically.

If the agent fails, runs out of budget or returns no valid result, the comment says the checks
could not finish, the label is set, nothing is merged, and the workflow run fails.

## Merge message

The squash commit is written by `decide.py`, not by GitHub's default:

- title: the pull request title plus ` (#n)`;
- body: one line per commit subject.

Any line that names an AI tool is left out, so `Co-Authored-By` trailers, session links and
tool names from the commits never reach the merge commit. A title that names an AI tool blocks
the auto-merge, with a note to rename the pull request. The agent itself never creates commits.

## Trust model

- The workflow uses `pull_request_target`, so the workflow, the prompt, the decision script,
  the skills and the policies always come from the base branch. A pull request cannot change
  the rules it is judged by. Changes to them take effect only after a person merges them, and
  changes under `.github/` are critical paths, so they always need a person.
- The pull request's code is checked out only to be read. Its `.claude/` folders, `.mcp.json`
  and `CLAUDE.md` files are not written to disk, and the agent loads only user settings, so no
  hook, skill or MCP server from the pull request runs.
- The agent job gets a read-only GitHub token and may run only reading commands (`git diff`,
  `git log`, `gh api`, `npm view` and similar). It cannot edit files or use the web tools.
- Only the **Comment and merge** job can write. It runs no agent.
- Pull requests from forks are skipped. They never get the API key or a write token.

## Setup

1. Add the repository secret `ANTHROPIC_API_KEY` (Settings → Secrets and variables → Actions).
2. Allow squash merging (Settings → General → Pull Requests).
3. Optional repository variables:
   - `PR_AGENT_MODEL`: the model to use. Default `claude-opus-5-5`.
   - `PR_AGENT_MAX_BUDGET_USD`: the most one run may spend. Default `10`.
4. If `main` has a ruleset or branch protection that requires an approving review, the bot's
   merge is refused. The comment then says GitHub refused the merge and a person merges it.
   To let low-risk pull requests merge on their own, allow GitHub Actions to bypass that
   rule, or drop the review requirement and require the **Run checks** and
   **Comment and merge** checks instead.

## Known limits

- A merge made by the workflow's own token does not start other workflows on `main` (a
  GitHub rule). If a workflow must run after every merge, trigger it differently or merge with
  a GitHub App token.
- The checks are judgements by a model. The fixed rules above make a wrong merge less likely,
  not impossible. Raise the bar in the risk policy or turn the workflow off if that is not
  acceptable for a part of the code.

## Run the tests

```bash
python -m unittest discover -s .github/pr-agent
```
