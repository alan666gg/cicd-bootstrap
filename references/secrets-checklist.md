# Secrets Checklist

## docker-ssh mode

### Test deploy

Required GitHub Secrets:
- `TEST_SSH_KEY`

Required GitHub Variables:
- `TEST_HOST`
- `TEST_USER`

Optional:
- `TEST_PORT`

### Production deploy

Required GitHub Secrets:
- `PROD_SSH_KEY`

Required GitHub Variables:
- `PROD_HOST`
- `PROD_USER`

Optional:
- `PROD_PORT`

## ci-only mode

### Test deploy

No fixed secrets are required by the generated placeholder workflow.

### Production deploy

No fixed secrets are required by the generated placeholder workflow.

## Notes

- `TEST_DOCKER_RUN_ARGS` and `PROD_DOCKER_RUN_ARGS` should include everything needed to run the service on the target host, for example:
  - `--restart unless-stopped -p 8008:8008 -v /srv/my-service/conf:/app/conf:ro -v /srv/my-service/log:/app/log`
- For `ci-only`, the generated deploy workflows are intentionally placeholders. Teams should replace them once the real deployment target is chosen.
