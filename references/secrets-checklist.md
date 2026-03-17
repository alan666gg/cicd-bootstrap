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

## docker-registry-only

### Required GitHub Secrets
- `REGISTRY_USERNAME`
- `REGISTRY_PASSWORD`

### Typical repo config defaults
- `image_registry`
- `runner`
- `test_environment`
- `prod_environment`

## ci-only

### Required GitHub Secrets
- none

### Required GitHub Variables
- none

## Notes

- `docker-ssh` assumes the remote host already knows how to run the service.
- `docker-registry-only` publishes images only. Another system is expected to deploy them.
- Teams should prefer `.github/cicd-bootstrap.json` for shared defaults instead of repeating values in every repository.
