## ADDED Requirements

### Requirement: Verifiable immutable deployments
Production deployments SHALL build from a clean Git worktree, use an immutable Git-SHA image tag, and expose the deployed revision.

#### Scenario: Deploy clean revision
- **WHEN** a production deployment completes
- **THEN** the health endpoint and Cloud Run revision identify the expected full Git SHA

#### Scenario: Deploy dirty worktree
- **WHEN** the deployment script detects tracked or untracked worktree changes
- **THEN** it stops before building or deploying
