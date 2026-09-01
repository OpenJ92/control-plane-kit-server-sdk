from __future__ import annotations

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RepositoryPolicyTests(unittest.TestCase):
    def test_agent_guide_records_repository_and_dependency_ownership(self) -> None:
        policy = self._read("AGENTS.md")

        for required in (
            "control-plane-kit-server-sdk",
            "control-plane-kit-core",
            "Core never imports the SDK",
            "ControlPlaneVariable",
            "operations",
            "products",
            "provider",
            "application truth",
        ):
            with self.subTest(required=required):
                self.assertIn(required, policy)

    def test_agent_guide_uses_accepted_protocol_and_replay_ownership_vocabulary(self) -> None:
        policy = self._read("AGENTS.md")

        self.assertIn(
            "ControlPlaneVariable[ReadResult, Command, TransitionResult]",
            policy,
        )
        self.assertIn("Issue #1150 owns replay", policy)
        self.assertNotIn("ControlPlaneVariable[State, Command, Result]", policy)
        self.assertIn("historical genesis metadata", policy)

    def test_agent_guide_records_issue_test_review_and_security_laws(self) -> None:
        policy = self._read("AGENTS.md")

        for required in (
            "cpk-agent-contract/v1",
            "Use this calibrated loop",
            "current behavior and public contract",
            "smallest bounded implementation and proportional tests",
            "authoritative Docker-backed ./test.sh",
            "focused target-red evidence only for an explicitly governed",
            "control-plane-kit-server-sdk -> pinned control-plane-kit-core",
            "GitHub issues, PRs, and material comments are durable project memory",
            "security",
            "dependent handoff",
            "broad Docker prune",
        ):
            with self.subTest(required=required):
                self.assertIn(required, policy)

    def test_git_flow_records_exact_branch_and_merge_topology(self) -> None:
        git_flow = self._read("GIT-FLOW.md")

        self.assertIn("main", git_flow)
        self.assertIn("develop", git_flow)
        self.assertIn("codex/<issue-id>-<slug>", git_flow)
        self.assertIn("pull request", git_flow.lower())
        self.assertIn("exact-head", git_flow)
        self.assertIn("checks", git_flow)
        self.assertIn("review", git_flow)

    def test_policy_decision_and_ignore_contract_are_present(self) -> None:
        decision = self._read("docs/decisions/0002-repository-policy.md")
        ignored = set(self._read(".gitignore").splitlines())

        for required in (
            "Status: Accepted",
            "#1484",
            "#1485",
            "No runtime",
            "No package",
        ):
            with self.subTest(required=required):
                self.assertIn(required, decision)
        self.assertTrue(
            {
                "__pycache__/",
                "*.py[cod]",
                ".venv/",
                "build/",
                "dist/",
                "*.egg-info/",
            }.issubset(ignored)
        )

    def _read(self, relative_path: str) -> str:
        path = REPOSITORY_ROOT / relative_path
        self.assertTrue(path.is_file(), f"missing policy artifact: {relative_path}")
        return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
