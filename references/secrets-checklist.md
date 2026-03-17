# Secrets Checklist

## docker-ssh

### Required GitHub Secrets
- `TEST_SSH_KEY`
- `PROD_SSH_KEY`

### Required GitHub Variables
- `TEST_HOST`
- `TEST_USER`
- `TEST_REMOTE_DIR`
- `TEST_CONTAINER_NAME`
- `TEST_DOCKER_RUN_ARGS`
- `PROD_HOST`
- `PROD_USER`
- `PROD_REMOTE_DIR`
- `PROD_CONTAINER_NAME`
- `PROD_DOCKER_RUN_ARGS`

### Optional Variables
- `TEST_PORT`
- `PROD_PORT`
- `TEST_HEALTHCHECK_URL`
- `PROD_HEALTHCHECK_URL`
- `TEST_HEALTHCHECK_TIMEOUT_SECONDS`
- `PROD_HEALTHCHECK_TIMEOUT_SECONDS`
- `TEST_ROLLBACK_ON_FAILURE`
- `PROD_ROLLBACK_ON_FAILURE`

## docker-registry-only

### Required GitHub Secrets
- `REGISTRY_USERNAME`
- `REGISTRY_PASSWORD`

### Typical repo config defaults
- `image_registry`
- `runner`
- `test_environment`
- `prod_environment`
- `enable_security_scan`
- `security_scan_blocking`

### Optional GitHub Variables
- `IMAGE_REGISTRY`

### Notes
- `IMAGE_REGISTRY` overrides the repo config registry prefix for registry-only workflows.
- The workflow lowercases the final registry prefix before login and push so GHCR-style naming stays valid.
- Bootstrap defaults security scans to non-blocking so transient Trivy/setup failures do not fail every first-run pipeline.
- Set `security_scan_blocking` to `true` if you want pushes to the default branch and `release` branches to fail on `HIGH` / `CRITICAL` findings.

## ci-only

### Required GitHub Secrets
- none

### Required GitHub Variables
- none

## Notes

- `docker-ssh` assumes the remote host already knows how to run the service.
- `docker-ssh` now creates the remote directory automatically before upload.
- `docker-ssh` generates `scripts/remote_deploy.sh` and uploads it during deploy.
- If you set a healthcheck URL, deploy waits for the service to come up before succeeding.
- Rollback defaults to enabled for docker-ssh deploys.
- `docker-registry-only` publishes images only. Another system is expected to deploy them.
- Teams should prefer `.github/cicd-bootstrap.json` for shared defaults instead of repeating values in every repository.
- Python services usually want `requirements.txt` or `pyproject.toml` committed so dependency install and cache hints stay stable.
- Java Gradle services should commit `gradlew` and `gradle/wrapper`; the CI template will repair execute permissions automatically.
- Rust services compile slower on the first run; keeping `Cargo.lock` checked in helps caching and reproducibility.
