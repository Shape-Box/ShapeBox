"""Tests for decide.py. Run with: python -m unittest discover -s .github/pr-agent"""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import decide

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / ".claude/skills/blast-radius/policies/risk-policy.yml"
HEAD = "a" * 40

CLEAN_RESULT = {
    "review": {"verdict": "ready", "ticket": "#9", "report": "Verdict: ready"},
    "security": {"ran": True, "finding_count": 0, "report": "No findings."},
    "compliance": {
        "personal_data": "pass",
        "licenses": "pass",
        "secrets": "pass",
        "report": "Personal data: pass\nLicenses: pass\nSecrets: pass",
    },
    "blast_radius": {"score": 10, "level": "low", "critical_paths": [], "report": "Blast radius: 10/100 (low)"},
}

OPEN_PR = {"number": 12, "title": "feat: add scene suggestions", "state": "open", "draft": False, "head": {"sha": HEAD}}


def clean():
    return copy.deepcopy(CLEAN_RESULT)


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        self.policy = decide.load_policy(str(POLICY_PATH))

    def decide(self, result=None, pr=None, files=("src/app.py",)):
        return decide.evaluate(result or clean(), self.policy, pr or dict(OPEN_PR), list(files), HEAD)

    def test_clean_low_risk_change_is_eligible(self):
        decision = self.decide()
        self.assertTrue(decision.eligible, decision.failed)

    def test_each_failing_check_blocks_and_is_named(self):
        cases = {
            'Review verdict is "ready"': lambda r: r["review"].update(verdict="needs changes"),
            "Security check reports no findings": lambda r: r["security"].update(finding_count=1),
            "All three compliance areas pass": lambda r: r["compliance"].update(licenses="fail"),
            'Blast radius level is "low"': lambda r: r["blast_radius"].update(score=35, level="medium"),
        }
        for name, change in cases.items():
            with self.subTest(name):
                result = clean()
                change(result)
                decision = self.decide(result)
                self.assertFalse(decision.eligible)
                self.assertEqual([c.name for c in decision.failed], [name])

    def test_security_that_did_not_run_blocks(self):
        result = clean()
        result["security"].update(ran=False)
        self.assertFalse(self.decide(result).eligible)

    def test_missing_ticket_blocks_through_review_verdict(self):
        result = clean()
        result["review"].update(verdict="blocked", ticket=None)
        decision = self.decide(result)
        self.assertEqual([c.name for c in decision.failed], ['Review verdict is "ready"'])

    def test_low_level_with_out_of_band_score_blocks(self):
        result = clean()
        result["blast_radius"].update(score=70, level="low")
        self.assertFalse(self.decide(result).eligible)

    def test_critical_path_blocks_even_if_agent_says_low(self):
        for path in (".github/workflows/ci.yml", "db/migrations/001.sql", "api/auth/login.py", ".env.local"):
            with self.subTest(path):
                decision = self.decide(files=["README.md", path])
                self.assertEqual([c.name for c in decision.failed], ["No critical path changed"])
                self.assertIn(path, decision.failed[0].detail)

    def test_draft_closed_or_moved_pr_blocks(self):
        for change in ({"draft": True}, {"state": "closed"}, {"head": {"sha": "b" * 40}}):
            with self.subTest(change):
                pr = dict(OPEN_PR, **change)
                self.assertFalse(self.decide(pr=pr).eligible)

    def test_title_naming_the_tool_blocks(self):
        pr = dict(OPEN_PR, title="feat: add Claude helper")
        decision = self.decide(pr=pr)
        self.assertEqual([c.name for c in decision.failed], ["Title can be used in the merge message"])


class GlobTest(unittest.TestCase):
    def test_patterns(self):
        cases = [
            (".github/**", ".github/workflows/ci.yml", True),
            (".github/**", "docs/.github", False),
            ("**/migrations/**", "migrations/001.sql", True),
            ("**/migrations/**", "app/db/migrations/001.sql", True),
            ("**/*.sql", "schema.sql", True),
            ("**/*.sql", "a/b/schema.sql", True),
            ("**/.env*", ".env", True),
            ("**/.env*", "config/.env.production", True),
            ("**/.env*", "src/environment.ts", False),
            ("**/payment*/**", "src/payments/charge.ts", True),
            ("package.json", "web/package.json", False),
        ]
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(bool(decide.glob_to_regex(pattern).match(path)), expected)


class ResultValidationTest(unittest.TestCase):
    def test_clean_result_is_valid(self):
        decide.validate_result(clean())

    def test_bad_results_are_rejected(self):
        bad = []
        r = clean(); del r["security"]; bad.append(r)
        r = clean(); r["review"]["verdict"] = "approve"; bad.append(r)
        r = clean(); r["security"]["finding_count"] = True; bad.append(r)
        r = clean(); r["blast_radius"]["score"] = 101; bad.append(r)
        r = clean(); r["compliance"]["secrets"] = "ok"; bad.append(r)
        bad.append([])
        for result in bad:
            with self.subTest(result=result):
                with self.assertRaises(decide.ResultError):
                    decide.validate_result(result)

    def test_missing_and_broken_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(decide.ResultError):
                decide.load_result(os.path.join(tmp, "nope.json"))
            broken = os.path.join(tmp, "broken.json")
            Path(broken).write_text("{not json", encoding="utf-8")
            with self.assertRaises(decide.ResultError):
                decide.load_result(broken)


class MergeMessageTest(unittest.TestCase):
    def test_tool_references_are_removed(self):
        messages = [
            "feat: add scene suggestions\n\nCloses #3\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_123",
            "fix: handle empty scenes",
            "chore: tweak prompt for Claude",
        ]
        title, body = decide.merge_message(OPEN_PR, messages)
        self.assertEqual(title, "feat: add scene suggestions (#12)")
        self.assertEqual(body, "* feat: add scene suggestions\n* fix: handle empty scenes")
        self.assertNotRegex(title + body, "(?i)claude|anthropic|session")


class CommentTest(unittest.TestCase):
    def test_comment_has_marker_four_sections_and_failed_condition(self):
        policy = decide.load_policy(str(POLICY_PATH))
        result = clean()
        result["compliance"]["secrets"] = "fail"
        decision = decide.evaluate(result, policy, dict(OPEN_PR), ["a.py"], HEAD)
        body = decide.render_comment(head_sha=HEAD, run_url="https://run", result=result, decision=decision)
        self.assertTrue(body.startswith(decide.MARKER))
        for heading in ("### Review", "### Security", "### Compliance", "### Blast radius"):
            self.assertIn(heading, body)
        self.assertIn("Not met: All three compliance areas pass", body)
        self.assertIn("❌ All three compliance areas pass: failed: secrets", body)

    def test_backticks_in_report_cannot_break_the_fence(self):
        text = decide.fenced("before\n```\nafter")
        self.assertTrue(text.startswith("````text\n"))
        self.assertTrue(text.endswith("\n````"))

    def test_failure_comment(self):
        body = decide.render_comment(head_sha=HEAD, run_url="https://run", failure="the agent wrote no result.")
        self.assertIn("the checks could not finish", body)
        self.assertIn("the agent wrote no result.", body)


class RunTest(unittest.TestCase):
    """End-to-end over run() with GitHub calls replaced."""

    def run_decide(self, result, analyze="success", pr=None, files=("src/app.py",), merge_error=None):
        calls = []

        def fake_gh(method, path, body=None):
            calls.append((method, path, body))
            if method == "GET" and path.endswith(f"/pulls/{OPEN_PR['number']}"):
                return pr or dict(OPEN_PR)
            if method == "GET" and "/files" in path:
                return [{"filename": f} for f in files]
            if method == "GET" and "/commits" in path:
                return [{"commit": {"message": "feat: add x\n\nCo-Authored-By: Claude <noreply@anthropic.com>"}}]
            if method == "GET" and "/comments" in path:
                return []
            if method == "PUT" and merge_error:
                raise decide.GitHubError(merge_error)
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            result_path = os.path.join(tmp, "result.json")
            if result is not None:
                Path(result_path).write_text(json.dumps(result), encoding="utf-8")
            args = decide.parse_args([
                "--repo", "o/r", "--pr", str(OPEN_PR["number"]), "--head-sha", HEAD,
                "--analyze-result", analyze, "--result", result_path, "--policy", str(POLICY_PATH),
                "--run-url", "https://run",
            ])
            with mock.patch.object(decide, "gh", side_effect=fake_gh), \
                 mock.patch("sys.stdout"), mock.patch("sys.stderr"):
                code = decide.run(args)
        return code, calls

    @staticmethod
    def find(calls, method, fragment):
        return [c for c in calls if c[0] == method and fragment in c[1]]

    def test_clean_change_is_squash_merged_with_clean_message(self):
        code, calls = self.run_decide(clean())
        self.assertEqual(code, 0)
        [merge] = self.find(calls, "PUT", "/merge")
        self.assertEqual(merge[2]["merge_method"], "squash")
        self.assertEqual(merge[2]["sha"], HEAD)
        self.assertNotRegex(merge[2]["commit_title"] + merge[2]["commit_message"], "(?i)claude|anthropic")
        [comment] = self.find(calls, "POST", "/comments")
        self.assertIn("squash-merged automatically", comment[2]["body"])
        self.assertTrue(self.find(calls, "DELETE", "/labels/"))

    def test_finding_means_no_merge_and_label(self):
        result = clean()
        result["security"]["finding_count"] = 2
        code, calls = self.run_decide(result)
        self.assertEqual(code, 0)
        self.assertFalse(self.find(calls, "PUT", "/merge"))
        [label] = self.find(calls, "POST", "/labels")
        self.assertEqual(label[2], {"labels": [decide.LABEL]})

    def test_failed_agent_job_means_no_merge(self):
        code, calls = self.run_decide(clean(), analyze="failure")
        self.assertEqual(code, 1)
        self.assertFalse(self.find(calls, "PUT", "/merge"))
        [comment] = self.find(calls, "POST", "/comments")
        self.assertIn("could not finish", comment[2]["body"])

    def test_missing_result_means_no_merge(self):
        code, calls = self.run_decide(None)
        self.assertEqual(code, 1)
        self.assertFalse(self.find(calls, "PUT", "/merge"))

    def test_refused_merge_is_reported(self):
        code, calls = self.run_decide(clean(), merge_error="Required status check is expected (HTTP 405)")
        self.assertEqual(code, 0)
        [comment] = self.find(calls, "POST", "/comments")
        self.assertIn("GitHub refused the merge", comment[2]["body"])
        self.assertTrue(self.find(calls, "POST", "/labels"))

    def test_existing_comment_is_updated(self):
        calls = []
        existing = [{"id": 7, "user": {"login": decide.BOT_LOGIN}, "body": decide.MARKER + "\nold"},
                    {"id": 8, "user": {"login": "someone"}, "body": decide.MARKER + "\nfake"}]
        with mock.patch.object(decide, "gh", side_effect=lambda m, p, b=None: calls.append((m, p, b)) or existing):
            decide.GitHub("o/r", 12, dry_run=False).upsert_comment("new")
        self.assertEqual([(m, p) for m, p, _ in calls][-1], ("PATCH", "repos/o/r/issues/comments/7"))


if __name__ == "__main__":
    unittest.main()
