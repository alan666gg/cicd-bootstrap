# Deploy Patterns

## docker-ssh

Use this mode when the repository is already Dockerized and the team wants a generic release path over SSH.

Signals:
- `Dockerfile` exists

Advantages:
- reusable across departments
- works for any Dockerized repo
- keeps release logic in GitHub Actions and SSH

Typical output:
- build image locally in the workflow
- save image tarball
- copy tarball to remote host over SSH
- load image and restart the container

## ci-only

Use this mode when the repository needs CI now but deployment is not standardized yet.

Signals:
- no `Dockerfile`
- deployment target is still undecided

Advantages:
- gives teams immediate CI coverage
- avoids inventing a fragile deploy process too early
- keeps the generated workflows easy to replace later

Typical output:
- `ci.yml` runs tests and build checks
- `deploy-test.yml` and `deploy-prod.yml` are manual placeholder workflows with setup guidance

## Decision Rule

1. Use `docker-ssh` when the repo is already Dockerized.
2. Use `ci-only` when the repo is not yet Dockerized or the release target is unclear.
