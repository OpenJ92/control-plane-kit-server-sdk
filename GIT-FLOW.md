# Git Flow

This repository uses one integration branch and short-lived issue branches:

```text
main
  develop
    codex/<issue-id>-<slug>
```

## Branch Roles

- `main` contains coherent promoted SDK verticals.
- `develop` contains accepted issue work in topological order.
- `codex/<issue-id>-<slug>` contains one reviewable issue or smaller child.

Create each issue branch from the exact accepted `origin/develop` coordinate.
Open its pull request back to `develop`. Do not commit issue work directly to
`main` or use `main` as a feature base.

## Merge Gate

Before merging an issue pull request:

1. record the exact base and head;
2. preserve focused target-red evidence from before implementation;
3. run focused and affected validation at the exact-head commit;
4. wait for attached checks to reach a terminal result when they exist;
5. complete a skeptical review and security note;
6. publish the decision log and dependent handoff; and
7. use the repository normal merge method after acceptance.

Absent or delayed checks are not evidence of success. Never merge merely
because no check is attached. If a branch is rebased or amended, evidence from
the old head is historical and affected exact-head validation must be rerun.

Promotion from `develop` to `main` is a separate reviewed pull request after a
coherent vertical satisfies its parent acceptance laws.
