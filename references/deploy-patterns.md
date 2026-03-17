# Deploy Patterns

## docker-ssh

Use this mode when the repository is already Dockerized and the team wants GitHub Actions to switch a remote container over SSH.

Signals:
- `Dockerfile` exists
- there is already a test/prod host
- the team is comfortable passing runtime args via GitHub Variables

Advantages:
- simple to understand
- does not require Kubernetes or a dedicated deployment platform
- fits many internal services

Tradeoffs:
- remote host layout still matters
- rollback is usually still host-specific

## docker-registry-only

Use this mode when the repository already has a `Dockerfile`, but deployment is handled elsewhere.

Typical teams:
- Kubernetes / Helm
- ECS
- Cloud Run
- ArgoCD / GitOps
- any team that only needs CI to build and push images

Advantages:
- works well with platform teams
- separates image publishing from deployment
- easy to standardize across departments

Tradeoffs:
- this skill only pushes images, it does not roll them out

## ci-only

Use this mode when the repository needs CI now but deployment is not standardized yet.

Signals:
- no `Dockerfile`
- deployment target is still undecided
- the team only wants tests/build checks first

Advantages:
- gives teams immediate CI coverage
- avoids inventing a fragile deploy process too early
- easy to replace later

## Decision Rule

1. Use `docker-ssh` when the repo is Dockerized and you want GitHub Actions to switch the container directly.
2. Use `docker-registry-only` when the repo is Dockerized but deployment happens in another system.
3. Use `ci-only` when deployment is still undecided or the repo is not ready for release automation yet.
