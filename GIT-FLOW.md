# Git Flow

`main` is the SDK's only long-lived integration branch. Start each temporary
`codex/<issue-id>-<slug>` branch from the accepted `origin/main` commit.
Keep the work issue-scoped and open a pull request into `main`.

## Merge Gate

1. Record the exact base and head commits on the pull request.
2. Follow the [agent guide](AGENTS.md) for source review and proportional tests.
   Preserve focused target-red evidence when the issue or the guide calls for it.
3. Validate the exact head using the owning Docker-backed `./test.sh`.
4. Verify the required checks passed and all attached checks reached a terminal result.
5. Complete an independent, skeptical review and record the security assessment.
6. Publish the decision log and dependent handoff.
7. After acceptance, use the repository's normal merge method.

Absent or delayed checks are not evidence of success. Never merge merely
because no check is attached. If a branch is rebased or amended, evidence from
the old head is historical and affected exact-head validation must be rerun.

Before retiring a temporary branch, verify its accepted merge and check for
dependent pull requests, attached worktrees and owner reservations.
