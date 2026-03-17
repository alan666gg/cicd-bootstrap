# Repo Config

The bootstrap flow can read an optional repository config file:

```text
.github/cicd-bootstrap.json
```

## Supported fields

Core:
- `app_name`
- `project_type`
- `deploy_strategy` or `deploy_mode`
- `service_path`
- `service_paths`

`app_name` is normalized to lowercase kebab-case before it is used in workflow output, image names, and generated artifact names. For example, `seers-sourceBinance` becomes `seers-source-binance`.
For `docker-registry-only`, `image_registry` is also trimmed and the workflow lowercases the final registry prefix at runtime before login and push.
If `app_name` is omitted for a monorepo service, the generator falls back to `<repo-name>-<service-slug>` to reduce image-name collisions in shared registries.

Branch defaults:
- `default_branch`
- `default_branches`
- `test_branch`
- `test_branches`

Organization defaults:
- `image_registry`
- `runner`
- `enable_security_scan`
- `enable_cache`
- `test_environment`
- `prod_environment`

Dockerfile generation:
- `generate_dockerfile`
- `dockerfile_kind`
- `docker_build_dir`
- `docker_start_command`
- `binary_name`

## Example

```json
{
  "app_name": "kairos-api",
  "deploy_strategy": "docker-registry-only",
  "service_paths": ["services/api", "services/worker"],
  "default_branch": "main",
  "test_branches": ["develop", "release/*"],
  "image_registry": "ghcr.io/acme-platform",
  "runner": "ubuntu-latest",
  "enable_security_scan": true,
  "enable_cache": true,
  "test_environment": "test",
  "prod_environment": "prod",
  "generate_dockerfile": true,
  "dockerfile_kind": "static-web",
  "docker_build_dir": "dist"
}
```

## Precedence

1. Explicit CLI flags
2. `.github/cicd-bootstrap.json`
3. Auto detection
